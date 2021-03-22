import os
import sys
import yaml
from typing import Union

from .archive import Archive
from .version import Version


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

	ALIEN_MATCHER_YAML = "aliensrc.yml"

	def __init__(self, full_archive_path):
		archive = Archive(full_archive_path)
		info_lines = archive.readfile(self.ALIEN_MATCHER_YAML)
		info_yaml = yaml.load("\n".join(info_lines), Loader = yaml.SafeLoader)

		self.spec_version = info_yaml['version']
		if self.spec_version != 1 and self.spec_version != "1":
			raise PackageError(
				f"{self.ALIEN_MATCHER_YAML} with version {self.spec_version} not supported"
			)

		super().__init__(
			info_yaml['source_package']['name'],
			info_yaml['source_package']['version'],
			full_archive_path
		)

		self.manager = info_yaml['source_package'].get('manager')
		self.metadata = info_yaml['source_package'].get('metadata')

		self.package_files = info_yaml['source_package']['files']

		checksums = archive.checksums("files/")

		if len(checksums) != len(self.package_files):
			raise PackageError(
				f"We do not have the same number of archive-files and checksums inside {self.ALIEN_MATCHER_YAML}."
			)

		arch_count = 0
		self.internal_archive_name = None
		for idx, rec in enumerate(self.package_files):
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
				# Better maybe? --> just add the tar archive that should be checked and
				# leave other files out, sharpen the tool and create another for other
				# files?
				if arch_count > 1:
					raise PackageError(
						"Too many internal archives for alien repository comparison. " \
						"Only one is supported at the moment..."
					)
				arch_count += 1
				self.internal_archive_name = rec['name']
				self.internal_archive_checksums = (
					archive.in_archive_checksums(f'files/{self.internal_archive_name}')
				)
				self.internal_archive_src_uri = rec['src_uri']
	
	def has_internal_archive(self):
		return self.internal_archive_name and len(self.internal_archive_name) > 0

	def print_info(self):
		print(f"| Package:")
		print(f"| - Name             : {self.name}")
		print(f"| - Alternative Names: {self.alternative_names}")
		print(f"| - Version          : {self.version.str}")
		print(f"| - Internal Archive : {self.internal_archive_name}")
