# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import os
import json
import tempfile
import logging
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.utils import bash, copy
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.commons.spdxutils import fix_spdxtv, spdxtv2rdf

logger = logging.getLogger(__name__)

class UploadAliens2FossyException(Exception):
	pass


class UploadAliens2Fossy:

	def __init__(
		self,
		alien_package: AlienPackage,
		alien_spdx_filename: str,
		fossy: FossyWrapper
	):
		self.fossy = fossy
		if not alien_package.internal_archive_name:
			raise UploadAliens2FossyException(
				"AlienPackage {alien_package.archive_fullpath} does not contain"
				" any internal archive"
			)
		self.alien_package = alien_package
		m = alien_package.metadata
		self.uploadname = (f"{m['name']}@{m['version']}-{m['revision']}")
		self.alien_spdx_filename = alien_spdx_filename

	def get_or_do_upload(self):
		self.uploadname = f'{self.alien_package.name}-{self.alien_package.version.str}'
		upload = self.fossy.check_already_uploaded(self.uploadname)
		if upload:
			self.upload = upload
			return
		apath = self.alien_package.archive_fullpath
		copy(f'{apath}', f'{apath}.tar')
		folder = self.fossy.get_or_create_folder('aliensrc') # FIXME do not harcode it
		self.upload = self.fossy.upload(
			f'{apath}.tar',
			folder,
			'uploaded by aliens4friends'
		)
		self.fossy.rename_upload(
			self.upload,
			self.uploadname
		)
		self.upload.uploadname = self.uploadname
		os.remove(f'{apath}.tar')

	def run_fossy_scanners(self):
			self.fossy.schedule_fossy_scanners(self.upload)

	def import_spdx(self):
		fix_spdxtv(self.alien_spdx_filename)
		tmpdir_obj = tempfile.TemporaryDirectory()
		tmpdir = tmpdir_obj.name
		spdxrdf_basename = f'{os.path.basename(self.alien_spdx_filename)}.rdf'
		spdxrdf = os.path.join(tmpdir, spdxrdf_basename)
		spdxtv2rdf(self.alien_spdx_filename, spdxrdf)
		uploadname = self.upload.uploadname
		archive_name = self.alien_package.internal_archive_name
		rootfolder = self.alien_package.internal_archive_rootfolder
		n, e = os.path.splitext(archive_name)
		if e and n.endswith('.tar'):
			archive_name = os.path.join(archive_name, n)
		fossy_internal_archive_path = os.path.join(uploadname, 'files', archive_name, rootfolder)
		fossy_internal_archive_path = fossy_internal_archive_path.replace('/', '\\/')
		bash(
			f"sed -i -E 's/fileName>\\.\\//fileName>{fossy_internal_archive_path}\\//g' {spdxrdf}"
		)
		# filepaths must match Fossology's internal filepaths otherwise
		# Fossology's reportImport apparently succeeds but does nothing
		self.fossy.report_import(self.upload, spdxrdf)
		# FIXME: add schedule reuser here (optional?)

	def get_fossy_json(self):
		"""get license findings and conclusions from fossology"""
		return self.fossy.get_license_findings_conclusions(self.upload)

	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*"):

		fossy = FossyWrapper()

		for path in pool.absglob(f"{glob_name}/{glob_version}/*.alienmatcher.json"):
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
					f'{a["internal_archive_name"]}.alien.spdx'
				)
				apkg = AlienPackage(alien_package_filename)
				apkg.expand()
				m = apkg.metadata
				apkg_fullname = f'{m["name"]}-{m["version"]}-{m["revision"]}'
				alien_fossy_json_filename = pool.abspath(
					"userland",
					a["name"],
					a["version"],
					f'{apkg_fullname}.fossy.json'
				)
				a2f = UploadAliens2Fossy(apkg, alien_spdx_filename, fossy)
				a2f.get_or_do_upload()
				a2f.run_fossy_scanners()
				a2f.import_spdx()
				fossy_json = a2f.get_fossy_json()
				with open(alien_fossy_json_filename, "w") as f:
					json.dump(fossy_json, f)

			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
