# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

from aliens4friends.commons.session import Session, SessionError
import os
import json
import tempfile
import logging
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.utils import bash, copy, log_minimal_error
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
		pool: Pool,
		alien_spdx_filename: str,
		fossy: FossyWrapper,
		fossy_folder: str
	):

		self.fossy = fossy
		self.alien_package = alien_package
		m = alien_package.metadata
		variant = f"-{m['variant']}" if m['variant'] else ""
		self.uploadname = (f"{m['base_name']}@{m['version']}-{m['revision']}{variant}")
		self.pool = pool
		self.alien_spdx_filename = pool.abspath(alien_spdx_filename)
		self.fossy_folder = fossy_folder

		if not alien_package.package_files:
			raise UploadAliens2FossyException(
				f"[{self.uploadname}] AlienPackage does not contain "
				"any files (is it a meta-package?), not uploading it"
			)
		if not alien_package.internal_archive_name:
			logger.warning(
				f"[{self.uploadname}] AlienPackage does not contain"
				" any internal archive"
			)

	def get_or_do_upload(self):
		upload = self.fossy.get_upload(self.uploadname)
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
		folder = self.fossy.get_or_create_folder(self.fossy_folder)
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
	def execute(
		pool: Pool,
		folder: str,
		glob_name: str = "*",
		glob_version: str = "*",
		session_id: str = ""
	) -> None:
		fossy = FossyWrapper()

		# Just take packages from the current session list
		# On error just return, error messages are inside load()
		if session_id:
			try:
				session = Session(pool, session_id)
				session.load()
				paths = session.package_list_paths(FILETYPE.ALIENSRC)
			except SessionError:
				return

		# ...without a session_id, take information directly from the pool
		else:
			paths = pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc")

		found = False
		for path in paths:
			found = True

			name, version = pool.packageinfo_from_path(path)

			cur_pckg = path.stem
			cur_path = pool.relpath(
				Settings.PATH_USR,
				name,
				version
			)

			try:
				apkg = AlienPackage(path)
				if not apkg.package_files:
					logger.info(
						f"[{cur_pckg}] package does not contain any files"
						" (is it a meta-package?), skipping"
					)
					continue
				logger.info(
					f"[{cur_pckg}] expanding alien package,"
					" it may require a lot of time"
				)
				apkg.expand(get_internal_archive_rootfolders=True)
			except Exception as ex:
				log_minimal_error(logger, ex, f"[{cur_pckg}] Unable to load aliensrc from {path} ")
				continue

			try:
				alien_spdx_filename = pool.abspath(
					cur_path,
					f'{apkg.internal_archive_name}.alien.spdx'
				) if apkg.internal_archive_name else ""

				a2f = UploadAliens2Fossy(apkg, pool, alien_spdx_filename, fossy, folder)
				a2f.get_or_do_upload()
				a2f.run_fossy_scanners()
				a2f.import_spdx()

				pool.write_json(
					a2f.get_metadata_from_fossology(),
					cur_path,
					f'{cur_pckg}.fossy.json'
				)

			except Exception as ex:
				log_minimal_error(logger, ex, f"[{cur_pckg}] ")

		if not found:
			logger.info(
				f"Nothing found for packages '{glob_name}' with versions '{glob_version}'. "
				f"Have you executed 'add' or 'spdxalien' for these packages?"
			)
