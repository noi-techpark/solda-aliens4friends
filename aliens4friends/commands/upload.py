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
from aliens4friends.commons.utils import get_prefix_formatted
from aliens4friends.models.fossy import FossyModel

logger = logging.getLogger(__name__)

class Upload(Command):

	def __init__(self, session_id: str, dryrun: bool):
		# Each run updates the session model! I would not be possible if we used
		# multi-processing, but we never use multiprocessing when dealing with
		# Fossology API
		super().__init__(session_id, Processing.LOOP, dryrun)
		self.fossywrapper = FossyWrapper()

	def hint(self) -> str:
		return "add/spdxalien"

	@staticmethod
	def execute(
		folder: str,
		session_id: str = "",
		description: str = "uploaded by aliens4friends",
		dryrun: bool = False
	) -> bool:
		cmd = Upload(session_id, dryrun)
		return cmd.exec_with_paths(
			FILETYPE.ALIENSRC, False, folder, description)

	def run(self, path: str, folder:str, description: str) -> Union[int, bool]:
		name, version, variant, _, _ = self.pool.packageinfo_from_path(path)

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
		if not session_pckg:
			msg = "Can't find package is session file"
			logger.warning(f"[{cur_pckg}] {msg}, skipping")
			return False
		if isinstance(session_pckg.uploaded, bool):
			msg = "Package already processed in this session"
			logger.info(f"[{cur_pckg}] {msg}, skipping")
			return True

		try:
			apkg = AlienPackage(path)
			if not apkg.package_files:
				msg = "Package does not contain any files (is it a meta-package?)"
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
				self.session.write_package_list()
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
			folder,
			description
		)
		upload_id = a2f.get_or_do_upload() # if exists, a2f.uploaded is False

		# we try to run scanners and to import spdx also if package has already
		# been uploaded, just in case there has been an error after upload the
		# previous time; the called methods (run_fossy_scanners and import_spdx)
		# already check if such tasks have already been run and in the positive
		# case they do not run them again, so we don't need to bother about it
		# here
		a2f.run_fossy_scanners()
		a2f.import_spdx()

		alien_fossy_json_path = self.pool.relpath_typed(
			FILETYPE.FOSSY,
			name,
			version,
			variant
		)
		fossy_json = a2f.get_metadata_from_fossology()

		fossy_json['metadata'] = {
			"name": apkg.name,
			"version": apkg.metadata['version'],
			"revision": apkg.metadata['revision'],
			"variant": apkg.variant
		}

		fossy_data = FossyModel.decode(fossy_json)
		self.pool.write_json_with_history(
			fossy_data, get_prefix_formatted(), alien_fossy_json_path
		)

		# This is OK, because we are in a loop and not in a multiprocessing
		# environment (we never use multiprocessing when dealing with fossology
		# API)
		self.session.set_package(
			{
				"uploaded": a2f.uploaded,
				"uploaded_reason": a2f.uploaded_reason
			},
			apkg.name,
			apkg.version.str,
			apkg.variant
		)
		self.session.write_package_list()

		return upload_id
