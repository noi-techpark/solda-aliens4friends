# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0

import csv
import logging
import os
from typing import Any, Optional

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.aliases import EXCLUSIONS
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE, PoolError
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.snapmatcher import AlienSnapMatcher
from aliens4friends.commons.version import Version
from aliens4friends.models.alienmatcher import (AlienSnapMatcherModel,
                                                AlienSrc, Tool)
from aliens4friends.models.base import ModelError

logger = logging.getLogger(__name__)

class SnapMatch(Command):

	def __init__(self, session_id: str, dryrun: bool) -> None:
		super().__init__(session_id, Processing.LOOP, dryrun)
		self.alienmatcher = AlienSnapMatcher(self.pool)

	def print_results(self, results: Any) -> None:
		for match in results:
			if match:
				print(match.to_json())

	def hint(self) -> str:
		return "add"

	@staticmethod
	def execute(session_id: str = "", dryrun: bool = False) -> bool:
		return SnapMatch(session_id, dryrun).exec_with_paths(
			FILETYPE.ALIENSRC,
			ignore_variant=True
		)

	def run(self, path) -> Optional[AlienSnapMatcherModel]:

		#FIXME Move this run code to the AlienSnapMatcher class

		# Return model in any case, we need to keep also "no match" results
		package = AlienPackage(path)
		self.alienmatcher.curpkg = f"{package.name}-{package.version.str}"
		logger.info(f"[{self.alienmatcher.curpkg}] Processing {os.path.basename(path)}...")
		amm = AlienSnapMatcherModel(
			tool=Tool(__name__, Settings.VERSION),
			aliensrc=AlienSrc(
				name = package.name,
				version = package.version.str,
				alternative_names = package.alternative_names,
				internal_archive_name = None,
				filename = package.archive_name,
				files = package.package_files
			)
		)

		resultpath = self.pool.relpath_typed(FILETYPE.SNAPMATCH, package.name, package.version.str)

		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError()
			amm = AlienSnapMatcherModel.from_file(self.pool.abspath(resultpath))
			if amm.match.score > 0:
				v1 = Version(amm.match.version)
				outcome = "MATCH"
			else:
				amm.errors.append("NO MATCH without errors")
				outcome = "NO MATCH"
			logger.debug(f"[{self.alienmatcher.curpkg}] Result already exists ({outcome}), skipping.")
			if outcome == "MATCH":
				self.alienmatcher.download_all_to_debian(amm.match)

		except (PoolError, ModelError, FileNotFoundError) as ex:
			if type(ex) == PoolError or type(ex) == ModelError:
				logger.warning(
					f"[{self.alienmatcher.curpkg}] Result file already exists but it is not readable: {ex}"
				)
			package.expand()
			amm.aliensrc.internal_archive_name = package.internal_archive_name
			if package.name in EXCLUSIONS:
				logger.info(f"[{self.alienmatcher.curpkg}] IGNORED: Known non-debian")
				amm.errors.append("IGNORED: Known non-debian")
			else:
				self.alienmatcher.match(package, amm) # pass amm and results by reference
			self.pool.write_json(amm, resultpath)

		return amm

