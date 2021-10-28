# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging
from uuid import uuid4

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

	def __init__(self, scancode_spdx: SPDXDocument, alien_package: AlienPackage):
		self._scancode_spdx = scancode_spdx
		self.alien_package = alien_package

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

	def process(self):
		self.alien_spdx = self._scancode_spdx
		for f in self.alien_spdx.files:
			if not f.chk_sum:
				f.chk_sum = SPDXAlgorithm("SHA1", EMPTY_FILE_SHA1)
			elif not f.chk_sum.value:
				f.chk_sum.value = EMPTY_FILE_SHA1
		self.set_package_and_document_metadata()


class Debian2AlienSPDX(Scancode2AlienSPDX):

	proximity: float  # pytype hint to resolve attribute-errors

	def __init__(self,
			scancode_spdx: SPDXDocument,
			alien_package: AlienPackage,
			debian_spdx: SPDXDocument,
			deltacodeng_results: DeltaCodeModel,
	):
		super().__init__(scancode_spdx, alien_package)
		self._debian_spdx = debian_spdx
		self.deltacodeng_results = deltacodeng_results

	def process(self):
		curpkg = f"{self.alien_package.name}-{self.alien_package.version.str}"
		results = self.deltacodeng_results.body
		deb_files2copy = (
			results.same_files
			+ results.changed_files_with_no_license_and_copyright
			+ results.changed_files_with_same_copyright_and_license
			+ list(results.changed_files_with_updated_copyright_year_only.keys())
		)
		proximity = self.deltacodeng_results.header.stats.calc_proximity()
		if proximity < MIN_ACCEPTABLE_PROXIMITY:
			logger.warning(
				f"[{curpkg}] proximity with debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
				f" is too low ({int(proximity*100)}%),"
				 " using scancode spdx instead"
			)
			super().process()
			return
		# TODO handle also moved_files
		deb_spdx_files = { f.name[2:]: f for f in self._debian_spdx.package.files }
		scancode_spdx_files = { f.name[2:]: f for f in self._scancode_spdx.package.files }
		# f.name[2:] strips initial './'
		alien_spdx_files = []
		alien_files_sha1s = self.alien_package.internal_archive_checksums
		for alien_spdx_file, alien_file_sha1 in alien_files_sha1s.items():
			name = f'./{alien_spdx_file}'
			if alien_spdx_file in deb_files2copy:
				if alien_spdx_file in deb_spdx_files:
					deb2alien_file = deb_spdx_files[alien_spdx_file]
					deb2alien_file.chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1)
					# there should be no licenseInfoInFile in SPDX generated 
					# from Debian, but just in case, we delete everything:
					deb2alien_file.licenses_in_file = [ NoAssert(), ] 
					scancode_spdx_file = scancode_spdx_files.get(alien_spdx_file)
					if scancode_spdx_file:
						if alien_spdx_file in results.changed_files_with_updated_copyright_year_only:
							deb2alien_file.copyright = scancode_spdx_file.copyright
						deb2alien_file.licenses_in_file = scancode_spdx_file.licenses_in_file
						if type(scancode_spdx_file.licenses_in_file[0]) in [ NoAssert, SPDXNone, type(None) ]:
							deb2alien_file.conc_lics = NoAssert()
							# if there are no copyright/license statements in
							# file, do not apply decisions from debian/copyright
						else:
							licenses_in_file_ids = [ 
								l.identifier 
								for l in deb2alien_file.licenses_in_file 
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
								e = deb2alien_file.conc_lics.identifier
								is_and_expr = not any([ 
									"(" in e, ")" in e, " OR " in e 
								]) and " AND " in e
								is_or_expr = not any([ 
									"(" in e, ")" in e, " AND " in e 
								]) and " OR " in e
								same_lics = []
								for conc_lic_id in conc_lics_ids:
									if conc_lic_id in licenses_in_file_ids:
										same_lics.append(conc_lic_id)
								if is_and_expr and same_lics:
									deb2alien_file.conc_lics = " AND ".join(same_lics)
									# if conc_lics is an AND-only expression,
									# add as conc_lics only licenses that match
									# some scancode finding
								elif is_or_expr and same_lics:
									deb2alien_file.conc_lics = " OR ".join(same_lics)
									# if conc_lics is an OR-only expression, 
									# add as conc_lics only licenses that match
									# some scancode finding
								elif len(same_lics) != len(conc_lics_ids):
									deb2alien_file.conc_lics = NoAssert()
									# if conc_lics (debian) do not match
									# all licenses_in file (scancode)
									# do not apply it
							if licenses_in_file_ids:
								deb2alien_file.licenses_in_file = [ 
									l for l in deb2alien_file.licenses_in_file 
									if isinstance(l, SPDXLicense) 
									and 
									SPDX_LICENSE_IDS.get(l.identifier.lower())
								]
								# remove non-standard SPDX licenses from 
								# scancode
					else:
						raise MakeAlienSPDXException(
							 "Something's wrong, can't find"
							f" {alien_spdx_file} in scancode spdx file"
						)

					alien_spdx_files.append(deb2alien_file)
				else:
					raise MakeAlienSPDXException(
						f"Something's wrong, can't find {alien_spdx_file} in SPDX doc"
					)
			elif scancode_spdx_files.get(alien_spdx_file):
				alien_file = scancode_spdx_files[alien_spdx_file]
				alien_file.spdx_id = f'SPDXRef-file-{md5(name)}'
				if (
					alien_file.licenses_in_file 
					and type(alien_file.licenses_in_file[0]) not in [ 
						NoAssert, SPDXNone, type(None) 
					]
				):
					alien_file.licenses_in_file = [ 
						l for l in alien_file.licenses_in_file 
						if isinstance(l, SPDXLicense) 
						and 
						SPDX_LICENSE_IDS.get(l.identifier.lower())
					]
					# remove non-standard SPDX licenses from 
					# scancode
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

		
