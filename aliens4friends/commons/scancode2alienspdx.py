# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging
from uuid import uuid4
from typing import List, Any

from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.creationinfo import Tool
from spdx.document import Document as SPDXDocument, License as SPDXLicense
from spdx.file import File as SPDXFile
from spdx.utils import NoAssert, SPDXNone

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.spdxutils import EMPTY_FILE_SHA1
from aliens4friends.commons.utils import md5
from aliens4friends.models.deltacode import DeltaCodeModel
from aliens4friends.commons.debian2spdx import SPDX_LICENSE_IDS

logger = logging.getLogger(__name__)

# proximity2debian levels
FULL_PROXIMITY = 1.0
NEARLY_FULL_PROXIMITY = 0.92
MIN_ACCEPTABLE_PROXIMITY = 0.3

class MakeAlienSPDXException(Exception):
	pass

class Scancode2AlienSPDX:

	def __init__(
		self,
		scancode_spdx: SPDXDocument,
		alien_package: AlienPackage,
		skip_scancode_licenses: bool = False
	):
		self._scancode_spdx = scancode_spdx
		self.alien_package = alien_package
		self.skip_scancode_licenses = skip_scancode_licenses

	def set_package_and_document_metadata(self):
		self.alien_spdx.package.name = self.alien_package.name
		self.alien_spdx.package.version = self.alien_package.version.str
		self.alien_spdx.package.file_name = self.alien_package.archive_name
		self.alien_spdx.package.supplier = None
		self.alien_spdx.package.comment = self.alien_package.metadata.get('comment')
		self.alien_spdx.package.download_location = self.alien_package.internal_archive_src_uri
		self.alien_spdx.package.verif_code = self.alien_spdx.package.calc_verif_code()
		self.alien_spdx.package.spdx_id = f"SPDXRef-{self.alien_package.name}-{self.alien_package.version.str}"
		self.alien_spdx.namespace = (
			f"http://spdx.org/spdxdocs/{self.alien_package.name}-{self.alien_package.version.str}-{uuid4()}"
		)
		self.alien_spdx.name = f"{self.alien_package.name}-{self.alien_package.version.str}"
		self.alien_spdx.creation_info.creators = []
		self.alien_spdx.creation_info.add_creator(Tool(__name__))
		self.alien_spdx.creation_info.set_created_now()
		# remove extracted (non-SPDX) licenses from SPDX doc
		self.alien_spdx.extracted_licenses = []

	def process(self):
		self.alien_spdx = self._scancode_spdx
		for f in self.alien_spdx.files:
			if not f.chk_sum:
				f.chk_sum = SPDXAlgorithm("SHA1", EMPTY_FILE_SHA1)
			elif not f.chk_sum.value:
				f.chk_sum.value = EMPTY_FILE_SHA1
			if self.skip_scancode_licenses:
				f.licenses_in_file = [ NoAssert(), ]
			else:
				# remove non-standard SPDX licenses from scancode
				f.licenses_in_file = Scancode2AlienSPDX.remove_non_spdx_lics(
					f.licenses_in_file
				)
		self.set_package_and_document_metadata()

	@staticmethod
	def remove_non_spdx_lics(licenses_in_file: List[Any]) -> List[Any]:
		"""remove non-standard SPDX licenses from licenses_in_file list"""
		if (
			licenses_in_file
			and licenses_in_file[0] not in [ NoAssert, SPDXNone, type(None) ]
		):
			return [
				l for l in licenses_in_file
				if isinstance(l, SPDXLicense)
				and
				SPDX_LICENSE_IDS.get(l.identifier.lower())
			]
		return licenses_in_file


class Debian2AlienSPDX(Scancode2AlienSPDX):

	proximity: float  # pytype hint to resolve attribute-errors

	def __init__(self,
			scancode_spdx: SPDXDocument,
			alien_package: AlienPackage,
			debian_spdx: SPDXDocument,
			deltacodeng_results: DeltaCodeModel,
			apply_debian_full: bool,
			skip_scancode_licenses: bool = False
	):
		super().__init__(scancode_spdx, alien_package, skip_scancode_licenses)
		self._debian_spdx = debian_spdx
		self.deltacodeng_results = deltacodeng_results
		self.apply_debian_full = apply_debian_full

	def process(self):
		curpkg = f"{self.alien_package.name}-{self.alien_package.version.str}"
		results = self.deltacodeng_results.body
		deb_files2copy = (
			results.same_files
			+results.changed_files_with_no_license_and_copyright
			+results.changed_files_with_same_copyright_and_license
			+list(results.changed_files_with_updated_copyright_year_only.keys())
		)
		proximity = self.deltacodeng_results.header.stats.calc_proximity()
		if proximity < MIN_ACCEPTABLE_PROXIMITY:
			logger.warning(
				f"[{curpkg}] proximity with debian package"
				f" {self._debian_spdx.package.name}"
				f"-{self._debian_spdx.package.version}"
				f" is too low ({int(proximity*100)}%),"
				 " using scancode spdx instead"
			)
			super().process()
			return
		# TODO handle also moved_files
		deb_spdx_files = {
			f.name[2:]: f for f in self._debian_spdx.package.files
		}
		scancode_spdx_files = {
			f.name[2:]: f for f in self._scancode_spdx.package.files
		}
		# f.name[2:] strips initial './'
		alien_spdx_files = []
		alien_files_sha1s = self.alien_package.internal_archive_checksums
		for alien_spdx_file, alien_file_sha1 in alien_files_sha1s.items():
			name = f'./{alien_spdx_file}'
			if alien_spdx_file in deb_files2copy:
				if not alien_spdx_file in deb_spdx_files:
					raise MakeAlienSPDXException(
						f"Something's wrong, can't find {alien_spdx_file}"
						" in SPDX doc"
					)
				deb2alien_file = deb_spdx_files[alien_spdx_file]
				deb2alien_file.chk_sum = SPDXAlgorithm(
					"SHA1", alien_file_sha1
				)
				# there should be no licenseInfoInFile in SPDX generated
				# from Debian, but just in case, we delete everything:
				deb2alien_file.licenses_in_file = [ NoAssert(), ]
				scancode_spdx_file = scancode_spdx_files.get(alien_spdx_file)
				if not scancode_spdx_file:
					raise MakeAlienSPDXException(
						 "Something's wrong, can't find"
						f" {alien_spdx_file} in scancode spdx file"
					)
				if alien_spdx_file in results.changed_files_with_updated_copyright_year_only:
					deb2alien_file.copyright = scancode_spdx_file.copyright
				deb2alien_file.licenses_in_file = (
					[ NoAssert(), ] if self.skip_scancode_licenses
					else scancode_spdx_file.licenses_in_file
				)
				if type(scancode_spdx_file.licenses_in_file[0]) in [
					NoAssert, SPDXNone, type(None)
				]:
					deb2alien_file.conc_lics = NoAssert()
					# if there are no copyright/license statements in
					# file, do not apply decisions from debian/copyright
					# otherwise it would mess up audit work on fossology
				if not self.apply_debian_full:
					# apply debian results only if they match scancode results
					licenses_in_file_ids = [
						l.identifier
						for l in scancode_spdx_file.licenses_in_file
						if isinstance(l, SPDXLicense)
					]
					conc_lics_ids = (
						(
							deb2alien_file.conc_lics.identifier
							.replace("(", "").replace(")","")
							.replace("AND","").replace("OR","")
							.split()
						)
						if isinstance(
							deb2alien_file.conc_lics, SPDXLicense
						)
						else []
					)
					if licenses_in_file_ids and conc_lics_ids:
						same_lics = []
						for conc_lic_id in conc_lics_ids:
							if conc_lic_id in licenses_in_file_ids:
								same_lics.append(conc_lic_id)
						if len(same_lics) != len(licenses_in_file_ids):
							deb2alien_file.conc_lics = NoAssert()
							# if conc_lics (debian) do not match
							# all licenses_in file (scancode)
							# do not apply it
				deb2alien_file.licenses_in_file = (
					Scancode2AlienSPDX.remove_non_spdx_lics(
						deb2alien_file.licenses_in_file
					)
				)
				alien_spdx_files.append(deb2alien_file)
			elif scancode_spdx_files.get(alien_spdx_file):
				alien_file = scancode_spdx_files[alien_spdx_file]
				alien_file.spdx_id = f'SPDXRef-file-{md5(name)}'
				if (
					alien_file.licenses_in_file
					and type(alien_file.licenses_in_file[0]) not in [
						NoAssert, SPDXNone, type(None)
					]
				):
					alien_file.licenses_in_file = (
						Scancode2AlienSPDX.remove_non_spdx_lics(
							alien_file.licenses_in_file
						)
					) if not self.skip_scancode_licenses else [ NoAssert(), ]
				alien_spdx_files.append(alien_file)
			else:
				alien_file = SPDXFile(
					name = name,
					chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1),
					spdx_id=f'SPDXRef-file-{md5(name)}',
				)
				alien_file.conc_lics=NoAssert()
				alien_file.licenses_in_file=[NoAssert(),]
				alien_file.copyright=NoAssert()
				alien_spdx_files.append(alien_file)
		self.alien_spdx = self._debian_spdx
		self.alien_spdx.package.files = alien_spdx_files

		if proximity < NEARLY_FULL_PROXIMITY:
			logger.info(
				f"[{curpkg}] proximity is not ~100%, do not apply main package"
				 " license(s) from debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
			)
			# do not apply debian main license and copyright
			# if proximity is not ~100%
			self.alien_spdx.package.license_declared = NoAssert()
			self.alien_spdx.package.conc_lics = NoAssert()
		if proximity < FULL_PROXIMITY:
			logger.info(
				f"[{curpkg}] proximity is not ==100%, do not apply global package"
				" license and copyright metadata from debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
			)
			# TODO the following metadata would need to be regenerated
			# we set them to NOASSERTION for now
			self.alien_spdx.package.licenses_from_files = [NoAssert(),]
			self.alien_spdx.package.cr_text = NoAssert()
		self.set_package_and_document_metadata()
