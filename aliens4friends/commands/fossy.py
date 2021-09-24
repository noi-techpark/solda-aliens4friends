# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import os

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.fossydownload import (GetFossyData,
                                                  GetFossyDataException)
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import get_prefix_formatted
from aliens4friends.models.fossy import FossyModel

logger = logging.getLogger(__name__)

class Fossy(Command):

	def __init__(self, session_id: str) -> None:
		super().__init__(session_id, processing=Processing.LOOP)
		self.fossywrapper = FossyWrapper()

	def hint(self) -> str:
		return "add/match"

	@staticmethod
	def execute(session_id: str = "") -> bool:
		cmd = Fossy(session_id)
		return cmd.exec_with_paths(FILETYPE.ALIENSRC)

	def run(self, args) -> bool:
		path = args
		name, version, _, _ = self.pool.packageinfo_from_path(path)

		cur_pckg = f"{name}-{version}"
		cur_path = os.path.join(
			Settings.PATH_USR,
			name,
			version
		)

		out_spdx_filename = self.pool.relpath(cur_path, f'{cur_pckg}.final.spdx')
		if self.pool.cached(out_spdx_filename, debug_prefix=f"[{cur_pckg}] "):
			return True

		try:
			apkg = AlienPackage(path)
		except Exception as ex:
			raise CommandError(f"[{cur_pckg}] Unable to load aliensrc from {path}: ERROR: {ex}")

		if not apkg.package_files:
			logger.debug(f"[{cur_pckg}] This is a metapackage with no files, skipping")
			return True

		try:
			alien_spdx = [
				p for p in self.pool.absglob(f"{cur_path}/*.alien.spdx")
			]
			if len(alien_spdx) == 0:
				alien_spdx_filename = None
			elif len(alien_spdx) == 1:
				alien_spdx_filename = alien_spdx[0]
				logger.info(f"[{cur_pckg}] using {self.pool.clnpath(alien_spdx_filename)}")
			else:
				raise GetFossyDataException(
					f"[{cur_pckg}] Something's wrong, more than one alien spdx"
					f" file found in pool: {alien_spdx}"
				)
			alien_fossy_json_filename = self.pool.relpath(cur_path, f'{cur_pckg}.{FILETYPE.FOSSY}')
			logger.info(f"[{cur_pckg}] Getting spdx and json data from Fossology")
			gfd = GetFossyData(self.fossywrapper, apkg, alien_spdx_filename)
			doc = gfd.get_spdx()
			self.pool.write_spdx_with_history(doc, get_prefix_formatted(), out_spdx_filename)
			fossy_json = gfd.get_metadata_from_fossology()

			fossy_json['metadata'] = {
				"name": apkg.name,
				"version": apkg.metadata['version'],
				"revision": apkg.metadata['revision'],
				"variant": apkg.variant
			}

			fossy_data = FossyModel.decode(fossy_json)
			self.pool.write_json_with_history(
				fossy_data, get_prefix_formatted(), alien_fossy_json_filename
			)

		except Exception as ex:
			raise CommandError(f"[{cur_pckg}] ERROR: {ex}")

		return True

