# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
from typing import Union

from aliens4friends.commons.fossyupload import UploadAliens2Fossy
from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.fossywrapper import FossyWrapper

logger = logging.getLogger(__name__)

class Upload(Command):

	def __init__(self, session_id: str, folder: str, dryrun: bool):
		# Each run updates the session model! Change that, if you want to
		# switch to multi-processing
		super().__init__(session_id, Processing.LOOP, dryrun)
		self.folder = folder
		self.fossywrapper = FossyWrapper()

	def hint(self) -> str:
		return "add/spdxalien"

	@staticmethod
	def execute(
		folder: str,
		session_id: str = "",
		dryrun: bool = False
	) -> bool:
		cmd = Upload(session_id, folder, dryrun)
		results = cmd.exec_with_paths(FILETYPE.ALIENSRC)
		cmd.session.write_package_list()
		return results


	def run(self, path: str) -> Union[int, bool]:
		name, version, variant, _ = self.pool.packageinfo_from_path(path)

		cur_pckg = f"{name}-{version}"
		cur_path = self.pool.relpath(
			Settings.PATH_USR,
			name,
			version
		)

		# Skip the package, if it has been already uploaded in this run (True)
		# or has been previously uploaded (False) in another job.
		# Upload the package, if the current upload status is unknown (None).
		session_pckg = self.session.get_package(name, version, variant)
		if isinstance(session_pckg.uploaded, bool):
			return True

		try:
			apkg = AlienPackage(path)
			if not apkg.package_files:
				msg = "package does not contain any files (is it a meta-package?)"
				logger.info(f"[{cur_pckg}] {msg}, skipping")
				# De-select package in session if it's a metapackage
				# This is OK, because we are in a loop and not multiprocessing environment
				# FIXME Shouldn't this be done earlier?
				self.session.set_package(
					{
						"selected": False,
						"selected_reason": msg
					},
					apkg.name,
					apkg.version.str,
					apkg.variant
				)
				return True

			logger.info(
				f"[{cur_pckg}] expanding alien package,"
				" it may require a lot of time"
			)
			apkg.expand(get_internal_archive_rootfolders=True)
		except Exception:
			raise CommandError(f"[{cur_pckg}] Unable to load aliensrc from {path} ")

		alien_spdx_filename = self.pool.abspath(
			cur_path,
			f'{apkg.internal_archive_name}.alien.spdx'
		) if apkg.internal_archive_name else ""

		a2f = UploadAliens2Fossy(
			apkg,
			self.pool,
			alien_spdx_filename,
			self.fossywrapper,
			self.folder
		)
		upload_id = a2f.get_or_do_upload()
		# if exists, a2f.uploaded is False
		a2f.run_fossy_scanners()
		a2f.import_spdx()

		self.pool.write_json(
			a2f.get_metadata_from_fossology(),
			cur_path,
			f'{cur_pckg}.fossy.json'
		)

		# This is OK, because we are in a loop and not multiprocessing environment
		self.session.set_package(
			{
				"uploaded": a2f.uploaded,
				"uploaded_reason": a2f.uploaded_reason
			},
			apkg.name,
			apkg.version.str,
			apkg.variant
		)

		return upload_id
