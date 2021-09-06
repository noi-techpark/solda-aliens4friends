# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import os
import sys
import json
import logging
from typing import Union, List, Optional, Dict, Any
from pathlib import Path

from .archive import Archive, ArchiveError
from .version import Version

from aliens4friends.models.aliensrc import AlienSrc, InternalArchive
from aliens4friends.models.common import SourceFile

logger = logging.getLogger(__name__)

class PackageError(Exception):
	pass

class Package:

	# type hints for attributes that are not defined inside __init__
	archive_name: Optional[str]
	archive_path: Optional[str]

	def __init__(
		self,
		name : Union[str, List[str]],
		version : Union[str, Version],
		archive_fullpath: Optional[str] = None
	) -> None:
		if isinstance(name, list):
			self.alternative_names = name[1:]
			name = name[0]
		else:
			self.alternative_names: List[str] = []

		if not name or not isinstance(name, str):
			raise PackageError("A package must have a valid name")

		self.name = name

		if isinstance(version, str):
			self.version = Version(version)
		elif isinstance(version, Version):
			self.version = version
		else:
			raise PackageError("A package must have a valid version")

		if archive_fullpath:
			self.archive_fullpath = os.path.normpath(archive_fullpath)
			self.archive_path = os.path.dirname(archive_fullpath)
			self.archive_name = os.path.basename(archive_fullpath)
		else:
			self.archive_fullpath = None
			self.archive_name = None
			self.archive_path = None

	def __str__(self) -> str:
		return f"{self.name} v{self.version.str}"

	def __repr__(self) -> str:
		return self.__str__()

class DebianPackage(Package):

	SUPPORTED_DSC_FORMATS = [
		"1.0",
		"3.0 (quilt)",
		"3.0 (native)"
	]

	def __init__(
		self,
		name: str,
		version: Union[str, Version],
		debsrc_orig: str,
		debsrc_debian: str,
		dsc_format: Optional[str] = None
	) -> None:

		if dsc_format and dsc_format not in self.SUPPORTED_DSC_FORMATS:
			raise PackageError(f"Unknown Debian Source Control File Format: {dsc_format}.")

		super().__init__(name, version)
		self.debsrc_orig = debsrc_orig
		self.debsrc_debian = debsrc_debian
		self.format = dsc_format


class AlienPackage(Package):

	# type hints
	archive: Archive
	manager: str
	metadata: Dict[str, Any]
	package_files: List[SourceFile]
	expanded: bool

	ALIEN_MATCHER_JSON = "aliensrc.json"
	SUPPORTED_ALIENSRC_VERSIONS = [ 1, 2 ]

	def __init__(self, full_archive_path: Union[Path, str]) -> None:
		self.archive = Archive(full_archive_path)

		try:
			aliensrc = self.archive.readfile(self.ALIEN_MATCHER_JSON)
			aliensrc = json.loads("\n".join(aliensrc))
			aliensrc = AlienSrc.decode(aliensrc)
		except ArchiveError as ex:
			raise PackageError(f"Broken Alien Package: Error is {str(ex)}")

		if aliensrc.version not in self.SUPPORTED_ALIENSRC_VERSIONS:
			raise PackageError(
				f"{self.ALIEN_MATCHER_JSON} with version {aliensrc.version} not supported"
			)

		super().__init__(
			aliensrc.source_package.name,
			aliensrc.source_package.version,
			full_archive_path
		)
		self.variant = aliensrc.source_package.metadata['variant']
		self.manager = aliensrc.source_package.manager
		self.metadata = aliensrc.source_package.metadata
		self.package_files = aliensrc.source_package.files
		self.expanded = False
		self.aliensrc = aliensrc

	def expand(
			self,
			check_checksums: Optional[bool] = False,
			get_internal_archive_checksums: Optional[bool] = False,
			get_internal_archive_rootfolders: Optional[bool] = False,
		) -> None:
		# We need this step only once for each instance...
		if self.expanded:
			return

		self.expanded = True
		if check_checksums:
			logger.debug(f"[{self.name}-{self.version.str}] checking checksums")
			checksums = self.archive.checksums("files/")
			archive_checksum_set = sorted(list(set([ fsha1 for fpath, fsha1 in checksums.items() ])))
			metadata_checksum_set = sorted(list(set([ p.sha1_cksum for p in self.package_files ])))


			if archive_checksum_set != metadata_checksum_set:
				raise PackageError(
					f"File checksum mismatch between {self.ALIEN_MATCHER_JSON} and actual files"
					f" in package {self.name}-{self.version.str}"
				)

		self.internal_archive_name = None
		self.internal_archive_checksums = None
		self.internal_archive_rootfolder = None
		self.internal_archive_src_uri = None
		self.internal_archives = []

		count_files = 0
		for src_file in self.package_files:

			if src_file.paths:
				paths = [ os.path.join(path, src_file.name) for path in src_file.paths ]
			else:
				paths = [ src_file.name ]

			if check_checksums:
				logger.debug(
					f"[{self.name}-{self.version.str}]"
					f" checking match between path(s) and checksum for source file {src_file.name}"
					)
				for path in paths:
					try:
						if src_file.sha1_cksum != checksums[path]:
							raise PackageError(
								f"{src_file.sha1_cksum} is not {checksums[path]} for {path}."
							)
						count_files += 1
					except KeyError:
						raise PackageError(
								f"{src_file.sha1_cksum} does not exist in checksums for {path}."
							)

			if '.tar.' in src_file.name or src_file.name.endswith('.tgz'):
				files_path = os.path.join("files", paths[0])
				self.internal_archives.append(
					InternalArchive(
						name = src_file.name,
						checksums = (
							self.archive.in_archive_checksums(files_path) 
							if get_internal_archive_checksums 
							else None
						),
						rootfolder = (
							self.archive.in_archive_rootfolder(files_path)
							if get_internal_archive_rootfolders
							else None
						),
						src_uri = src_file.src_uri
					)
				)
				logger.debug(
					f"[{self.name}-{self.version.str}]"
					f" adding internal archive {src_file.name}")

		if check_checksums and len(checksums) != count_files:
			raise PackageError(
				"We do not have the same count of files and checksums"
				f" inside {self.ALIEN_MATCHER_JSON} of package {self.name}-{self.version.str}"
			)

		primary = None
		if len(self.internal_archives) == 1:
			primary = self.internal_archives[0]
		elif len(self.internal_archives) > 1:
			# WARNING: If we have more than one internal archive, it is not defined
			# which one gets taken as primary internal archive, we should better
			# always check if it is only one, when a subcommand needs the internal
			# archive

			# Special rules to find the primary archive
			for src_file in self.internal_archives:
				if (
					(("linux" in src_file.name or "kernel" in src_file.name)
					and "name=machine" in src_file.src_uri)
					or
					("perl" in src_file.name and "name=perl" in src_file.src_uri)
					or
					("libxml2" in src_file.name and "name=libtar" in src_file.src_uri)
				):
					primary = src_file
					break

		if primary:
			self.internal_archive_name = primary.name
			self.internal_archive_checksums = primary.checksums
			self.internal_archive_rootfolder = primary.rootfolder
			self.internal_archive_src_uri = primary.src_uri
			if len(self.internal_archives) > 1:
				logger.warning(
					f"[{self.name}-{self.version.str}]"
					 " more than one internal archive, using just primary"
					f" archive '{primary.name}' for comparison"
			)
		elif not primary and len(self.internal_archives) > 1:
			logger.warning(
				f"[{self.name}-{self.version.str}] "
				"Too many internal archives for alien repository comparison,"
				" and no primary archive detected"
			)

	def has_internal_primary_archive(self) -> bool:
		return self.internal_archive_name and len(self.internal_archive_name) > 0  #pytype: disable=bad-return-type

	def internal_archive_count(self) -> int:
		return len(self.internal_archives)

	def calc_provenance(self) -> None:
		self.known_provenance = 0
		self.unknown_provenance = 0
		for f in self.package_files:
			if f.src_uri.startswith("file:"):
				self.unknown_provenance += (f.files_in_archive or 1)
				# (files_in_archive == False) means that it's no archive, just a single file
			elif f.src_uri.startswith("http") or f.src_uri.startswith("git"):
				self.known_provenance += (f.files_in_archive or 1)
		self.total = self.known_provenance + self.unknown_provenance



	def print_info(self) -> None:
		print(f"| Package:")
		print(f"| - Name             : {self.name}")
		print(f"| - Alternative Names: {self.alternative_names}")
		print(f"| - Version          : {self.version.str}")
		print(f"| - Internal Archive : {self.internal_archive_name}")
