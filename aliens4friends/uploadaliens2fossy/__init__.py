# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import os
import json
import tempfile
import logging
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.utils import bash
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.commons.spdxutils import fix_spdxtv, spdxtv2rdf

logger = logging.getLogger(__name__)

class AlienSPDX2FossyException(Exception):
	pass


class AlienSPDX2Fossy:

	def __init__(
		self,
		alien_package: AlienPackage,
		alien_spdx_filename: str,
		fossy: FossyWrapper
	):
		self.fossy = fossy
		if not alien_package.internal_archive_name:
			raise AlienSPDX2FossyException(
				"AlienPackage {alien_package.archive_fullpath} does not contain"
				" any internal archive"
			)
		self.alien_package = alien_package
		m = alien_package.metadata
		self.upload = fossy.get_upload(m['name'], m['version'], m['revision'])
		self.alien_spdx_filename = alien_spdx_filename

	def do_import(self):
		fix_spdxtv(self.alien_spdx_filename)
		tmpdir_obj = tempfile.TemporaryDirectory()
		tmpdir = tmpdir_obj.name
		spdxrdf_basename = f'{os.path.basename(self.alien_spdx_filename)}.rdf'
		spdxrdf = os.path.join(tmpdir, spdxrdf_basename)
		spdxtv2rdf(self.alien_spdx_filename, spdxrdf)
		uploadname = self.upload.uploadname
		rootfolder = self.alien_package.internal_archive_rootfolder
		bash(
			f"sed -i -E 's/fileName>\\.\\//fileName>{uploadname}\\/{rootfolder}\\//g' {spdxrdf}"
		)
		# filepaths must match Fossology's internal filepaths otherwise
		# Fossology's reportImport apparently succeeds but does nothing
		self.fossy.report_import(self.upload, spdxrdf)
		# FIXME: add schedule reuser here (optional?)

	def get_fossy_json(self):
		"""get license findings and conclusions from fossology"""
		return self.fossy.get_license_findings_conclusions(self.upload)

	@staticmethod
	def execute(alienmatcher_json_list):

		pool = Pool(Settings.POOLPATH)

		fossy = FossyWrapper()

		for path in alienmatcher_json_list:
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"Unable to load json from {path},"
				f" got {ex.__class__.__name__}: {ex}")
				continue
			try:
				a = j["aliensrc"]
				alien_package_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					a["filename"]
				)
				alien_spdx_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{a["internal_archive_name"]}.spdx'
				)
				apkg = AlienPackage(alien_package_filename)
				m = apkg.metadata
				apkg_fullname = f'{m["name"]}-{m["version"]}-{m["revision"]}'
				alien_fossy_json_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{apkg_fullname}.fossy.json'
				)
				a2f = AlienSPDX2Fossy(apkg, alien_spdx_filename, fossy)
				a2f.do_import()
				fossy_json = a2f.get_fossy_json()
				with open(alien_fossy_json_filename, "w") as f:
					json.dump(fossy_json, f)

			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
