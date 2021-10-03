# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import json
import logging
import os
from typing import List

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.scancode import Scancode
from aliens4friends.commons.settings import Settings
from aliens4friends.models.alienmatcher import (AlienMatcherModel,
                                                AlienSnapMatcherModel)

logger = logging.getLogger(__name__)

class Scan(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool):
		super().__init__(session_id, processing=Processing.LOOP)
		self.use_oldmatcher = use_oldmatcher
		self.scancode = Scancode(self.pool)

	def hint(self) -> str:
		return "match/snapmatch"

	@staticmethod
	def execute(
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> bool:
		cmd = Scan(session_id, use_oldmatcher)
		return cmd.exec_with_paths(
			FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH,
			ignore_variant=False
		)

	def run(self, path: str) -> List[str]: 
		name, version, _, _ = self.pool.packageinfo_from_path(path)
		package = f"{name}-{version}"
		result = []

		try:
			if self.use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception as ex:
			raise CommandError(f"[{package}] Unable to load json from {self.pool.clnpath(path)}.")

		logger.debug(f"[{package}] Files determined through {self.pool.clnpath(path)}")

		try:
			to_scan = model.match.debsrc_orig or model.match.debsrc_debian # support for Debian Format 1.0 native
			archive = Archive(self.pool.relpath(to_scan))
			result.append(
				self.scancode.run(archive, model.match.name, model.match.version)
			)
		except KeyError:
			logger.info(f"[{package}] no debian match, no debian package to scan here")
		except TypeError as ex:
			if not to_scan:  #pytype: disable=name-error
				logger.info(f"[{package}] no debian orig archive to scan here")
			else:
				raise CommandError(f"[{package}] {ex}.")

		except Exception as ex:
			raise CommandError(f"[{package}] {ex}.")

		try:
			archive = Archive(
				self.pool.relpath(
					Settings.PATH_USR,
					model.aliensrc.name,
					model.aliensrc.version,
					model.aliensrc.filename
				)
			)
			result_file = self.scancode.run(
				archive,
				model.aliensrc.name,
				model.aliensrc.version,
				os.path.join("files", model.aliensrc.internal_archive_name)
			)
			if result_file and Settings.PRINTRESULT:
				with open(result_file) as r:
					result.append(json.load(r))
		except TypeError as ex:
			if not model.aliensrc.internal_archive_name:
				logger.info(f"[{package}] no internal archive to scan here")
			else:
				raise CommandError(f"[{package}] {ex}.")

		except Exception as ex:
			raise CommandError(f"[{package}] {ex}.")

		# Return a non-empty list, if we got no results but also no errors,
		# otherwise correct runs which skip all files would fail!
		return [ True ] if not result else result
