# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import os
import json
import logging
from uuid import uuid4

from spdx.file import File as SPDXFile
from spdx.utils import NoAssert
from spdx.creationinfo import Tool
from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.document import Document as SPDXDocument

from aliens4friends.commons.archive import Archive
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.utils import md5
from aliens4friends.commons.spdxutils import parse_spdx_tv, write_spdx_tv, EMPTY_FILE_SHA1

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

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

	def __init__(self,
			scancode_spdx: SPDXDocument,
			alien_package: AlienPackage,
			debian_spdx: SPDXDocument,
			deltacodeng_results: dict,
	):
		super().__init__(scancode_spdx, alien_package)
		self._debian_spdx = debian_spdx
		self.deltacodeng_results = deltacodeng_results

	def process(self):
		results = self.deltacodeng_results["body"]
		deb_files2copy = (
			results['same_files']
			+ results['changed_files_with_no_license_and_copyright']
			+ results['changed_files_with_same_copyright_and_license']
		)
		# TODO handle also moved_files and changed_files_with_updated_copyright_year_only
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
					alien_spdx_files.append(deb2alien_file)
				else:
					raise MakeAlienSPDXException(
						f"Something's wrong, can't find {alien_spdx_file} in SPDX doc"
					)
			elif scancode_spdx_files.get(alien_spdx_file):
				alien_file = scancode_spdx_files[alien_spdx_file]
				alien_file.spdx_id = f'SPDXRef-file-{md5(name)}'
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
		self.set_package_and_document_metadata()


class MakeAlienSPDX:

	def __init__(self):
		pass

	@staticmethod
	def execute(pool: Pool):

		for path in pool.absglob("*.alienmatcher.json"):
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"Unable to load json from {path}.")
				continue
			try:
				a = j["aliensrc"]
				alien_spdx_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{a["internal_archive_name"]}.alien.spdx'
				)
				if os.path.isfile(alien_spdx_filename) and Settings.POOLCACHED:
					logger.debug("{alien_spdx_filename} already found in cache, skipping")
					continue
				alien_package_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					a["filename"]
				)
				scancode_spdx_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{a["name"]}_{a["version"]}.scancode.spdx'
				)
				scancode_spdx, err = parse_spdx_tv(scancode_spdx_filename)
				alien_package = AlienPackage(alien_package_filename)

				if j.get("debian") and j["debian"].get("match"):
					m = j["debian"]["match"]
					deltacodeng_results_filename = pool.abspath(
						"userland",
						a["name"],
						a["version"],
						f'{a["name"]}_{a["version"]}.deltacode.json'
					)
					debian_spdx_filename = pool.abspath(
						"debian",
						m["name"],
						m["version"],
						f'{m["name"]}_{m["version"]}.debian.spdx'
					)
					if (os.path.isfile(deltacodeng_results_filename) and os.path.isfile(debian_spdx_filename)):
						logger.info(f"Applying debian spdx to package {a['name']}-{a['version']}")
						debian_spdx, err = parse_spdx_tv(debian_spdx_filename)
						with open(deltacodeng_results_filename, 'r') as f:
							deltacodeng_results = json.load(f)

						d2as = Debian2AlienSPDX(
							scancode_spdx,
							alien_package,
							debian_spdx,
							deltacodeng_results
						)
						d2as.process()
						write_spdx_tv(d2as.alien_spdx, alien_spdx_filename)
					else:
						logger.info(f"No debian spdx available, using scancode spdx for package {a['name']}-{a['version']}")
						s2as = Scancode2AlienSPDX(scancode_spdx, alien_package)
						s2as.process()
						write_spdx_tv(s2as.alien_spdx, alien_spdx_filename)
			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
