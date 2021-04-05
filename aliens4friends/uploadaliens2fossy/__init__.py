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
		upload = self.fossy.get_upload(
			self.alien_package.name,
			self.alien_package.version.str
		)
		if upload:
			logger.info(f"[{self.uploadname}] Package already uploaded")
			self.upload = upload
			return
		logger.info(f"[{self.uploadname}] Preparing package for upload")
		tmpdir_obj = tempfile.TemporaryDirectory()
		tmpdir = tmpdir_obj.name
		self.alien_package.archive.extract_raw(tmpdir)
		files_dir = os.path.join(tmpdir, "files")
		# use tar.xz because it's more fossology-friendly (no annoying
		# subfolders in unpacking)
		tar2upload = os.path.join(tmpdir, f"{self.uploadname}.tar.xz")
		bash(f"tar cJf {tar2upload} .", cwd=files_dir)
		logger.info(f"[{self.uploadname}] Uploading package")
		folder = self.fossy.get_or_create_folder('aliensrc') # FIXME do not hardcode it
		self.upload = self.fossy.upload(
			tar2upload,
			folder,
			'uploaded by aliens4friends'
		)
		self.fossy.rename_upload(
			self.upload,
			self.uploadname
		)
		self.upload.uploadname = self.uploadname

	def run_fossy_scanners(self):
			logger.info(f"[{self.uploadname}] Run fossy scanners")
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

	def get_metadata_from_fossology(self):
		"""get summary and license findings and conclusions from fossology"""
		logger.info(f"[{self.uploadname}] getting metadata from fossology")
		summary = self.fossy.get_summary(self.upload)
		licenses = self.fossy.get_license_findings_conclusions(self.upload)
		return {
			"origin": Settings.FOSSY_SERVER,
			"summary": summary,
			"licenses": licenses
		}

	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*"):
		fossy = FossyWrapper()
		for path in pool.absglob(f"{glob_name}/{glob_version}/*.alienmatcher.json"):
			package = f"{path.parts[-3]}-{path.parts[-2]}"
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"[{package}] Unable to load json from {path},"
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
				fossy_json = a2f.get_metadata_from_fossology()
				with open(alien_fossy_json_filename, "w") as f:
					json.dump(fossy_json, f)

			except Exception as ex:
				logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
