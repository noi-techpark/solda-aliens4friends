# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import re

from debian.debian_support import Version as DebVersion
from packaging.version import Version as PkgVersion, parse, InvalidVersion
from typing import Union, Any, Optional, TypeVar

_TVersion = TypeVar('_TVersion', bound='Version')

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

	MAX_DISTANCE = 10000000000000
	OK_DISTANCE = 0
	KO_DISTANCE = 100000

	def __init__(self, version_str: str, remove_epoc: bool = True) -> None:
		super().__init__()
		self.str = version_str
		if remove_epoc:
			self.str = self._remove_epoc(self.str)
		self.version_conversion = 0
		self.str_simple = self._version_simplify()
		self.package_version = None
		self.debian_version = None
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

	def distance(self, other_version: Union[_TVersion, Any]) -> int:

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
		# only if the level above is equal.
		return (
			dist_major * 10000 +
			(dist_minor * 1000 if dist_major == 0 else 0) +
			(dist_micro * 100 if dist_major == 0 and dist_minor == 0 else 0) +
			((dist_revision1 + dist_revision2 + dist_post) * 10 if dist_major == 0 and dist_minor == 0 and dist_micro == 0 else 0)
		)

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
