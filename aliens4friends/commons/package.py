# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
import sys
import json
import logging
from typing import Union

from .archive import Archive, ArchiveError
from .version import Version

from aliens4friends.models.aliensrc import AlienSrc

logger = logging.getLogger(__name__)

class PackageError(Exception):
	pass

class Package:

	def __init__(
		self,
		name : str,
		version : Union[str, Version],
		archive_fullpath : str = None
	):
		super().__init__()

		if isinstance(name, list):
			self.alternative_names = name[1:]
			name = name[0]

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

	def __str__(self):
		return f"{self.name} v{self.version.str}"

	def __repr__(self):
		return self.__str__()

class DebianPackage(Package):

	SUPPORTED_DSC_FORMATS = [
		"1.0",
		"3.0 (quilt)",
		"3.0 (native)"
	]

	def __init__(self, name, version, debsrc_orig, debsrc_debian, dsc_format = None):

		if dsc_format and dsc_format not in self.SUPPORTED_DSC_FORMATS:
			raise PackageError(f"Unknown Debian Source Control File Format: {dsc_format}.")

		super().__init__(name, version)
		self.debsrc_orig = debsrc_orig
		self.debsrc_debian = debsrc_debian
		self.format = dsc_format


class AlienPackage(Package):

	ALIEN_MATCHER_JSON = "aliensrc.json"

	def __init__(self, full_archive_path):
		self.archive = Archive(full_archive_path)

		try:
			aliensrc = self.archive.readfile(self.ALIEN_MATCHER_JSON)
			aliensrc = json.loads("\n".join(aliensrc))
			aliensrc = AlienSrc.decode(aliensrc)
		except ArchiveError as ex:
			raise PackageError(f"Broken Alien Package: Error is {str(ex)}")

		if aliensrc.version != 1:
			raise PackageError(
				f"{self.ALIEN_MATCHER_JSON} with version {aliensrc.version} not supported"
			)

		super().__init__(
			aliensrc.source_package.name,
			aliensrc.source_package.version,
			full_archive_path
		)
		self.manager = aliensrc.source_package.manager
		self.metadata = aliensrc.source_package.metadata
		self.package_files = aliensrc.source_package.files
		self.expanded = False

	def expand(self):
		# We need this step only once for each instance...
		if self.expanded:
			return

		self.expanded = True
		checksums = self.archive.checksums("files/")

		if len(checksums) != len(self.package_files):
			raise PackageError(
				"We do not have the same number of archive-files and checksums"
				f" inside {self.ALIEN_MATCHER_JSON} of package {self.name}-{self.version.str}"
			)

		self.internal_archive_name = None
		self.internal_archive_checksums = None
		self.internal_archive_rootfolder = None
		self.internal_archive_src_uri = None
		self.internal_archives = []

		for src_file in self.package_files:
			try:
				if src_file.sha1 != checksums[src_file.name]:
					raise PackageError(
						f"{src_file.sha1} is not {checksums[src_file.name]} for {src_file.name}."
					)
			except KeyError:
				raise PackageError(
						f"{src_file.sha1} does not exist in checksums for {src_file.name}."
					)

			if '.tar.' in src_file.name or src_file.name.endswith('.tgz'):
				self.internal_archives.append(
					{
						"name" : src_file.name,
						"checksums" : self.archive.in_archive_checksums(f"files/{src_file.name}"),
						"rootfolder" : self.archive.in_archive_rootfolder(f"files/{src_file.name}"),
						"src_uri" : src_file.src_uri
					}
				)
				logger.debug(
					f"[{self.name}-{self.version.str}]"
					f" adding internal archive {src_file.name}")

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
					(("linux" in src_file["name"] or "kernel" in src_file["name"])
					and "name=machine" in src_file["src_uri"])
					or
					("perl" in src_file["name"] and "name=perl" in src_file["src_uri"])
					or
					("libxml2" in src_file["name"] and "name=libtar" in src_file["src_uri"])
				):
					primary = src_file
					break

		if primary:
			self.internal_archive_name = primary['name']
			self.internal_archive_checksums = primary['checksums']
			self.internal_archive_rootfolder = primary['rootfolder']
			self.internal_archive_src_uri = primary['src_uri']
			if len(self.internal_archives) > 1:
				logger.warning(
					f"[{self.name}-{self.version.str}]:"
					 " more than one internal archive, using just primary"
					f" archive '{primary['name']}' for comparison"
			)
		elif not primary and len(self.internal_archives) > 1:
			logger.warning(
				f"[{self.name}-{self.version.str}]: "
				"Too many internal archives for alien repository comparison,"
				" and no primary archive to use for comparison"
			)

	def has_internal_primary_archive(self):
		return self.internal_archive_name and len(self.internal_archive_name) > 0

	def internal_archive_count(self):
		return len(self.internal_archives)

	def calc_provenance(self):
		self.known_provenance = 0
		self.unknown_provenance = 0
		for f in self.package_files:
			src_uri = f.src_uri.split(";")[0] # remove bitbake params
			if src_uri.startswith("file:"):
				self.unknown_provenance += (f.files_in_archive or 1)
				# (files_in_archive == False) means that it's no archive, just a single file
			elif src_uri.startswith("http") or src_uri.startswith("git"):
				self.known_provenance += (f.files_in_archive or 1)
		self.total = self.known_provenance + self.unknown_provenance



	def print_info(self):
		print(f"| Package:")
		print(f"| - Name             : {self.name}")
		print(f"| - Alternative Names: {self.alternative_names}")
		print(f"| - Version          : {self.version.str}")
		print(f"| - Internal Archive : {self.internal_archive_name}")
