# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import re
from typing import Any, Optional, TypeVar, Union

from debian.debian_support import Version as DebVersion
from packaging.version import Version as PkgVersion

_TVersion = TypeVar('_TVersion', bound='Version')

class VersionError(Exception):
	pass

class Version:

	# type hints
	package_version: PkgVersion
	debian_version: DebVersion

	FLAG_DEB_VERSION_ORIG = 1<<0
	FLAG_DEB_VERSION_SIMPLIFIED = 1<<1
	FLAG_DEB_VERSION_ERROR = 1<<2
	FLAG_PKG_VERSION_ORIG = 1<<3
	FLAG_PKG_VERSION_SIMPLIFIED = 1<<4
	FLAG_PKG_VERSION_ERROR = 1<<5

	MAX_DISTANCE = 10000000000
	OK_DISTANCE = 0
	KO_DISTANCE = 100000

	def __init__(self, version_str: str, remove_epoc: bool = True) -> None:
		super().__init__()
		self.str = version_str.strip()
		if not self.str:
			raise VersionError(f"Invalid version string given: '{version_str}'")
		if remove_epoc:
			self.str = self._remove_epoc(self.str)
		self.version_conversion = 0
		self.str_simple = self._version_simplify()
		self.package_version = None
		self.debian_version = None
		self.is_semver = Version._is_semver(self.str)
		self._make_debian_version()
		self._make_package_version()

	def _make_package_version(self) -> None:
		try:
			self.package_version = PkgVersion(self.str)
			self.version_conversion |= Version.FLAG_PKG_VERSION_ORIG
		except Exception:
			try:
				self.package_version = PkgVersion(self.str_simple)
				self.version_conversion |= Version.FLAG_PKG_VERSION_SIMPLIFIED
			except Exception:
				self.version_conversion |= Version.FLAG_PKG_VERSION_ERROR

	def _make_debian_version(self) -> None:
		try:
			self.debian_version = DebVersion(self.str)
			self.version_conversion |= Version.FLAG_DEB_VERSION_ORIG
		except Exception:
			try:
				self.debian_version = DebVersion(self.str_simple)
				self.version_conversion |= Version.FLAG_DEB_VERSION_SIMPLIFIED
			except Exception:
				self.version_conversion |= Version.FLAG_DEB_VERSION_ERROR

	def _version_simplify(self) -> str:
		result = self._remove_epoc(self.str)
		result = self._fix_tcp_wrappers_version(result) #FIXME generalize
		countdots = 0
		for i, ch in enumerate(result):
			if ch.isalpha() or ch in "+-~":
				return result[:i]
			if ch == ".":
				countdots += 1
				if countdots > 2:
					return result[:i]

		return result

	def has_flag(self, flag: int) -> bool:
		return (self.version_conversion & flag) != 0

	def distance(self, other_version: Union[_TVersion, Any], simplified: bool = False) -> int:

		if not isinstance(other_version, Version):
			return Version.MAX_DISTANCE

		if self.has_flag(Version.FLAG_DEB_VERSION_ERROR | Version.FLAG_PKG_VERSION_ERROR):
			return Version.MAX_DISTANCE

		if other_version.has_flag(Version.FLAG_DEB_VERSION_ERROR | Version.FLAG_PKG_VERSION_ERROR):
			return Version.MAX_DISTANCE

		# https://packaging.pypa.io/en/latest/version.html
		dist_major = Version._safe_abs_dist(self.package_version.major, other_version.package_version.major)
		dist_minor = Version._safe_abs_dist(self.package_version.minor, other_version.package_version.minor)
		dist_micro = Version._safe_abs_dist(self.package_version.micro, other_version.package_version.micro)
		dist_post = Version._safe_abs_dist(self.package_version.post, other_version.package_version.post)

		dist_revision1 = 0
		if self.has_flag(Version.FLAG_DEB_VERSION_SIMPLIFIED | Version.FLAG_PKG_VERSION_SIMPLIFIED):
			dist_revision1 = 1

		dist_revision2 = 0
		if other_version.has_flag(Version.FLAG_DEB_VERSION_SIMPLIFIED | Version.FLAG_PKG_VERSION_SIMPLIFIED):
			dist_revision2 = 1

		# Defensive hierarchical distance, that is, consider subsequent versioning levels
		# only if the level above is equal. This is the simple version, that is we ignore
		# anything below the minor level
		if simplified:
			return int(
				Version.clamp(dist_major * 10000, 0, 50000)
				+ Version.clamp((dist_minor * 100 if dist_major == 0 else 0), 0, 5000)
				+ Version.clamp((dist_micro if dist_major == 0 and dist_minor == 0 else 0), 0, 50)
			)

		# Defensive hierarchical distance, that is, consider subsequent versioning levels
		# only if the level above is equal.
		return (
			dist_major * 10000 +
			(dist_minor * 1000 if dist_major == 0 else 0) +
			(dist_micro * 100 if dist_major == 0 and dist_minor == 0 else 0) +
			((dist_revision1 + dist_revision2 + dist_post) * 10 if dist_major == 0 and dist_minor == 0 and dist_micro == 0 else 0)
		)

	@staticmethod
	def clamp(n: Union[float, int], n_min: Union[float, int], n_max: Union[float, int]) -> Union[float, int]:
		if n < n_min:
			return n_min
		if n > n_max:
			return n_max
		return n

	def similarity(self, other_version: Union[_TVersion, Any]) -> float:
		dist = self.distance(other_version, True)

		if dist == 0:
			return 100

		# At least one major version bump
		# we use a linear decrease here... 20% down for each major version difference
		if dist >= 10000:
			step = 20
			bound = [0, 80]

		# We have changes only in the minor version number
		# we use a linear decrease of much smaller steps (2% each)
		# The smallest possible value is 80% here, since we did not
		# change the major number, which has a lower threshold at 80
		elif dist >= 100:
			step = 2.0
			bound = [82, 99]

		# We have only changes in the micro version number
		else:
			step = 0.2
			bound = [99, 100]

		return Version.clamp(100 - dist / (step * 2500) * 100, bound[0], bound[1])


	def __lt__(self, other: _TVersion) -> bool:
		return self.debian_version < other.debian_version

	def __eq__(self, other: _TVersion) -> bool:
		return self.str == other.str

	def __str__(self) -> str:
		simple = ""
		if (self.has_flag(Version.FLAG_DEB_VERSION_SIMPLIFIED | Version.FLAG_PKG_VERSION_SIMPLIFIED)):
			simple = " -> " + self.str_simple
		return f"{self.str}{simple} ({self.version_conversion:06b})"

	def __repr__(self) -> str:
		return self.__str__()

	@staticmethod
	def _safe_abs_dist(a: Optional[int], b: Optional[int]) -> int:
		if not a:
			a = 0
		if not b:
			b = 0
		return abs(a - b)

	@staticmethod
	def _remove_epoc(vers_str: str) -> str:
		for i in range(len(vers_str)):
			if not vers_str[i].isdigit():
				break
		if i > 0 and i + 1 < len(vers_str) and vers_str[i] == ':':
			return vers_str[i+1:]
		return vers_str

	@staticmethod
	def _fix_tcp_wrappers_version(vers_str: str) -> str:
		p = re.compile('(\d+\.\d+\.)q-(\d+)')
		m = p.match(vers_str)
		if m:
			return ''.join(m.groups())
		return vers_str

	@staticmethod
	def _is_semver(vers_str: str) -> bool:
		# Taken from https://semver.org/
		p = re.compile("^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
		m = p.match(vers_str)
		return True if m else False
