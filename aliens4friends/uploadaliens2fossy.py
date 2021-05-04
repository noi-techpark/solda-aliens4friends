# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import os
import json
import tempfile
import logging
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.utils import bash, copy
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.commons.spdxutils import fix_spdxtv, spdxtv2rdf, parse_spdx_tv, write_spdx_tv
from typing import List, Tuple

logger = logging.getLogger(__name__)

class UploadAliens2FossyException(Exception):
	pass


class UploadAliens2Fossy:

	# Type hints for attributes not declared in __init__:
	fossy_internal_archive_path: str
	upload: Tuple[List[str], int]

	def __init__(
		self,
		alien_package: AlienPackage,
		alien_spdx_filename: str,
		fossy: FossyWrapper
	):
		if not alien_package.package_files:
			raise UploadAliens2FossyException(
				f"AlienPackage {alien_package.archive_fullpath} does not contain"
				"any files (is it a meta-package?), not uploading it"
			)
		if not alien_package.internal_archive_name:
			logger.warning(
				f"AlienPackage {alien_package.archive_fullpath} does not contain"
				" any internal archive"
			)
		self.fossy = fossy
		self.alien_package = alien_package
		m = alien_package.metadata
		self.uploadname = (f"{m['base_name']}@{m['version']}-{m['revision']}")
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

	def _convert_and_upload_spdx(self, alien_spdx_fullpath):
		tmpdir_obj = tempfile.TemporaryDirectory()
		tmpdir = tmpdir_obj.name
		spdxrdf_basename = f'{os.path.basename(alien_spdx_fullpath)}.rdf'
		spdxrdf = os.path.join(tmpdir, spdxrdf_basename)
		spdxtv2rdf(alien_spdx_fullpath, spdxrdf)
		bash(
			f"sed -i -E 's/fileName>\\.\\//fileName>{self.fossy_internal_archive_path}\\//g' {spdxrdf}"
		)
		# filepaths must match Fossology's internal filepaths otherwise
		# Fossology's reportImport apparently succeeds but does nothing
		self.fossy.report_import(self.upload, spdxrdf)


	def import_spdx(self):
		if not self.alien_package.internal_archive_name:
			logger.warning(
				f"[{self.upload.uploadname}] has no internal archive,"
				" we don't have any alien spdx to upload"
			)
			return
		if self.fossy.check_already_imported_report(self.upload):
			logger.info(
				f"[{self.upload.uploadname}] not uploading anything, spdx"
				" report already uploaded before"
			)
			return
		logger.info(f"[{self.uploadname}] Uploading alien SPDX")
		fix_spdxtv(self.alien_spdx_filename)
		uploadname = self.upload.uploadname
		archive_name = self.alien_package.internal_archive_name
		# handle fossology's inconsistent behaviour when unpacking archives:
		if (
			archive_name.endswith(".tar.gz")
			or archive_name.endswith(".tar.bz2")
			or archive_name.endswith(".tgz")
		):
			fossy_subfolder, _ = os.path.splitext(archive_name)
			archive_unpack_path = os.path.join(archive_name, fossy_subfolder)
		elif archive_name.endswith(".tar.xz") or archive_name.endswith(".zip"):
			# FIXME: actually, we don't have .zip support in Archive class
			archive_unpack_path = archive_name
		rootfolder = self.alien_package.internal_archive_rootfolder
		if rootfolder and rootfolder != "." and rootfolder != "./":
			archive_unpack_path = os.path.join(archive_unpack_path, rootfolder)
		self.fossy_internal_archive_path = os.path.join(
			uploadname, archive_unpack_path
		)
		self.fossy_internal_archive_path = self.fossy_internal_archive_path.replace('/', '\\/')

		if os.path.getsize(self.alien_spdx_filename) > 13000000:
			logger.info(
				f"[{self.upload.uploadname}] alien spdx is too big to be"
				" uploaded, splitting it in two files"
			)
			doc2split, _ = parse_spdx_tv(self.alien_spdx_filename)
			allfiles = doc2split.package.files
			splitpoint = int( len(allfiles) / 2 )
			tmpdir_obj = tempfile.TemporaryDirectory()
			tmpdir = tmpdir_obj.name
			part1 = f"part1_{os.path.basename(self.alien_spdx_filename)}"
			doc2split.package.files = allfiles[:splitpoint]
			doc2split.package.verif_code = doc2split.package.calc_verif_code()
			alien_spdx_fullpath = os.path.join(tmpdir, part1)
			write_spdx_tv(doc2split, alien_spdx_fullpath)
			self._convert_and_upload_spdx(alien_spdx_fullpath)
			part2 = f"part2_{os.path.basename(self.alien_spdx_filename)}"
			doc2split.package.files = allfiles[splitpoint:]
			doc2split.package.verif_code = doc2split.package.calc_verif_code()
			alien_spdx_fullpath = os.path.join(tmpdir, part2)
			write_spdx_tv(doc2split, alien_spdx_fullpath)
			self._convert_and_upload_spdx(alien_spdx_fullpath)
		else:
			self._convert_and_upload_spdx(self.alien_spdx_filename)
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
		# FIXME: add some control to log a message if no path is found
		# (pool.absglob doesn't return a list, and you can iterate it only once)
		for path in pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc"):
			package = f"{path.parts[-3]}-{path.parts[-2]}"
			try:
				apkg = AlienPackage(path)
				logger.info(
					f"[{package}] expanding alien package,"
					" it may require a lot of time"
				)
				apkg.expand()
				a = apkg.metadata
				apkg_fullname = f'{a["base_name"]}-{a["version"]}-{a["revision"]}'
				apkg_name = a["base_name"]
				apkg_version = f'{a["version"]}-{a["revision"]}'
			except Exception as ex:
				logger.error(f"[{package}] Unable to load aliensrc from {path},"
				f" got {ex.__class__.__name__}: {ex}")
				continue
			try:
				alien_spdx_filename = pool.abspath(
					"userland",
					apkg_name,
					apkg_version,
					f'{apkg.internal_archive_name}.alien.spdx'
				) if apkg.internal_archive_name else ""

				alien_fossy_json_filename = pool.abspath(
					"userland",
					apkg_name,
					apkg_version,
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
