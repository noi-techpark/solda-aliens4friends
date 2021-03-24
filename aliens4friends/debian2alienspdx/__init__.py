# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

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
from aliens4friends.commons.spdxutils import parse_spdx_tv, write_spdx_tv

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class Debian2AlienSPDXException:
	pass

class Debian2AlienSPDX:

	def __init__(self,
			debian_spdx: SPDXDocument,
			deltacodeng_results: dict,
			alien_package: AlienPackage
	):
		# TODO: add type checks
		self.debian_spdx = debian_spdx
		self.deltacodeng_results = deltacodeng_results
		self.alien_package = alien_package

	def process(self):
		results = self.deltacodeng_results["body"]
		deb_files2copy = (
			results['same_files']
			+ results['changed_files_with_no_license_and_copyright']
			+ results['changed_files_with_same_copyright_and_license']
		)
		# TODO handle also moved_files and changed_files_with_updated_copyright_year_only
		deb_spdx_files = { f.name[2:]: f for f in self.debian_spdx.package.files }
			# f.name[2:] strips initial './'
		alien_spdx_files = []
		alien_files_sha1s = self.alien_package.internal_archive_checksums
		for alien_spdx_file, alien_file_sha1 in alien_files_sha1s.items():
			if alien_spdx_file in deb_files2copy:
				if alien_spdx_file in deb_spdx_files:
					deb2alien_file = deb_spdx_files[alien_spdx_file]
					deb2alien_file.chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1)
					alien_spdx_files.append(deb2alien_file)
				else:
					raise Exception(
						f"Something's wrong, can't find {alien_spdx_file} in SPDX doc"
					)
			else:
				name = f'./{alien_spdx_file}'
				alien_file = SPDXFile(
					name = name,
					chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1),
					spdx_id=f'SPDXRef-file-{md5(name)}',
				)
				alien_file.conc_lics=NoAssert()
				alien_file.licenses_in_file=[NoAssert(),]
				alien_file.copyright=NoAssert()
				alien_spdx_files.append(alien_file)
		alien_spdx = self.debian_spdx
		alien_spdx.package.files = alien_spdx_files
		alien_spdx.package.name = self.alien_package.name
		alien_spdx.package.version = self.alien_package.version.str
		alien_spdx.package.file_name = self.alien_package.archive_name
		alien_spdx.package.supplier = None
		alien_spdx.package.comment = self.alien_package.metadata.get('comment')
		alien_spdx.package.download_location = self.alien_package.internal_archive_src_uri
		alien_spdx.package.verif_code = alien_spdx.package.calc_verif_code()
		alien_spdx.package.spdx_id = f"SPDXRef-{self.alien_package.name}-{self.alien_package.version.str}"
		alien_spdx.namespace = (
			f"http://spdx.org/spdxdocs/{self.alien_package.name}-{self.alien_package.version.str}-{uuid4()}"
		)
		alien_spdx.name = f"{self.alien_package.name}-{self.alien_package.version.str}"
		alien_spdx.creation_info.creators = []
		alien_spdx.creation_info.add_creator(Tool(__name__))
		alien_spdx.creation_info.set_created_now()
		self.alien_spdx = alien_spdx

	@staticmethod
	def execute(alienmatcher_json_list):

		pool = Pool(Settings.POOLPATH)

		for path in alienmatcher_json_list:
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"Unable to load json from {path}.")
				continue
			try:
				m = j["debian"]["match"]
				a = j["aliensrc"]
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
					f'{m["name"]}_{m["version"]}.spdx'
				)
				alien_package_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'alien-{a["name"]}-{a["version"]}.aliensrc'	 #FIME: the alienpackage name should be added to alienmatcher!
				)
				alien_spdx_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{a["internal_archive_name"]}.spdx'
				)
			except Exception as ex:
				logger.error(f"{path} --> {ex}")

			try:
				debian_spdx, err = parse_spdx_tv(debian_spdx_filename)
				with open(deltacodeng_results_filename, 'r') as f:
					deltacodeng_results = json.load(f)
				alien_package = AlienPackage(alien_package_filename)
				d2as = Debian2AlienSPDX(
					debian_spdx,
					deltacodeng_results,
					alien_package
				)
				d2as.process()
				write_spdx_tv(d2as.alien_spdx, alien_spdx_filename)
			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
