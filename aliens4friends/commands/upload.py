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
		return cmd.exec_with_paths(FILETYPE.ALIENSRC)

	def run(self, path: str) -> Union[int, bool]:
		name, version, _, _ = self.pool.packageinfo_from_path(path)

		cur_pckg = f"{name}-{version}"
		cur_path = self.pool.relpath(
			Settings.PATH_USR,
			name,
			version
		)
		# TODO: check session file if already uploaded (True) or previously uploaded (False) -> skip, go only only il unknown (none/null)

		try:
			apkg = AlienPackage(path)
			if not apkg.package_files:
				logger.info(
					f"[{cur_pckg}] package does not contain any files"
					" (is it a meta-package?), skipping"
				)
				return True
				# TODO: de-select package in session if it's a metapackage

			logger.info(
				f"[{cur_pckg}] expanding alien package,"
				" it may require a lot of time"
			)
			apkg.expand(get_internal_archive_rootfolders=True)
		except Exception as ex:
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

		self.session.package_list_set(
			{
				"uploaded": a2f.uploaded,
				"uploaded_reason": a2f.uploaded_reason
			},
			apkg.name,
			apkg.version.str,
			apkg.variant
		)

		return upload_id
