import os
import sys
import json
import logging
from typing import Union

from .archive import Archive, ArchiveError
from .version import Version

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
			info_lines = self.archive.readfile(self.ALIEN_MATCHER_JSON)
		except ArchiveError as ex:
			raise PackageError(f"Broken Alien Package: Error is {str(ex)}")

		self._info_json = json.loads("\n".join(info_lines))

		self.spec_version = self._info_json['version']
		if self.spec_version != 1 and self.spec_version != "1":
			raise PackageError(
				f"{self.ALIEN_MATCHER_JSON} with version {self.spec_version} not supported"
			)

		super().__init__(
			self._info_json['source_package']['name'],
			self._info_json['source_package']['version'],
			full_archive_path
		)

		self.manager = self._info_json['source_package'].get('manager')
		self.metadata = self._info_json['source_package'].get('metadata')

		self.package_files = self._info_json['source_package']['files']

	def expand(self):
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
		for rec in self.package_files:
			try:
				if rec['sha1'] != checksums[rec['name']]:
					raise PackageError(
						f"{rec['sha1']} is not {checksums[rec['name']]} for {rec['name']}."
					)
			except KeyError:
				raise PackageError(
						f"{rec['sha1']} does not exist in checksums for {rec['name']}."
					)

			if '.tar.' in rec['name']:
				self.internal_archives.append(
					{
						"name" : rec["name"],
						"checksums" : self.archive.in_archive_checksums(f"files/{rec['name']}"),
						"rootfolder" : self.archive.in_archive_rootfolder(f"files/{rec['name']}"),
						"src_uri" : rec["src_uri"]
					}
				)

		primary = None
		if len(self.internal_archives) == 1:
			primary = self.internal_archives[0]
		elif len(self.internal_archives) > 1:
			# WARNING: If we have more than one internal archive, it is not defined
			# which one gets taken as primary internal archive, we should better
			# always check if it is only one, when a subcommand needs the internal
			# archive
			logger.warning(
				f"{self._info_json['source_package']['name']}/{self._info_json['source_package']['version']}: " \
				"Too many internal archives for alien repository comparison"
			)

			# Special rules to find the primary archive
			for rec in self.internal_archives:
				# yocto-kernel (linux mostly)
				if (
					("linux" in rec["name"] or "kernel" in rec["name"])
					and "name=machine" in rec["src_uri"]
				):
					primary = rec
					break

		if primary:
			self.internal_archive_name = primary['name']
			self.internal_archive_checksums = primary['checksums']
			self.internal_archive_rootfolder = primary['rootfolder']
			self.internal_archive_src_uri = primary['src_uri']

	def has_internal_primary_archive(self):
		return self.internal_archive_name and len(self.internal_archive_name) > 0

	def internal_archive_count(self):
		return len(self.internal_archives)

	def print_info(self):
		print(f"| Package:")
		print(f"| - Name             : {self.name}")
		print(f"| - Alternative Names: {self.alternative_names}")
		print(f"| - Version          : {self.version.str}")
		print(f"| - Internal Archive : {self.internal_archive_name}")
