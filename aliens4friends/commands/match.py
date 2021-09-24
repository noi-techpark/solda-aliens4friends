# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import os
from typing import Any, Optional

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.alienmatcher import AlienMatcher
from aliens4friends.commons.package import AlienPackage, PackageError
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.models.alienmatcher import AlienMatcherModel

logger = logging.getLogger(__name__)

class Match(Command):

	def __init__(self, session_id: str) -> None:
		super().__init__(session_id, processing=Processing.LOOP)
		self.alienmatcher = AlienMatcher(session_id)

	def hint(self) -> str:
		return "add"

	def run(self, args) -> Optional[AlienMatcherModel]:
		path = args[0]

		#FIXME Move this run code to the AlienMatcher class, some for other commands
		try:
			package = AlienPackage(path)
			self.alienmatcher.curpkg = f"{package.name}-{package.version.str}"
			logger.info(f"[{self.alienmatcher.curpkg}] Processing {os.path.basename(path)}...")
			package.expand()
			amm = self.alienmatcher.match(package)
		except PackageError as ex:
			raise CommandError(f"[{self.alienmatcher.curpkg}] ERROR: {ex}")

		debsrc_debian = amm.match.debsrc_debian
		debsrc_debian = os.path.basename(debsrc_debian) if debsrc_debian else ''

		debsrc_orig = amm.match.debsrc_orig
		debsrc_orig = os.path.basename(debsrc_orig) if debsrc_orig else ''

		outcome = 'MATCH' if debsrc_debian or debsrc_orig else 'NO MATCH'
		if not debsrc_debian and not debsrc_orig and not amm.errors:
			amm.errors = 'NO MATCH without errors'
		logger.info(
			f"[{self.alienmatcher.curpkg}] {outcome}:"
			f" {debsrc_debian} {debsrc_orig} {'; '.join(amm.errors)}"
		)
		return amm

	def print_results(self, results: Any) -> None:
		for match in results:
			if match:
				print(match.to_json())

	@staticmethod
	def execute(session_id: str = "") -> bool:
		return Match(session_id).exec_with_paths(
			FILETYPE.ALIENSRC,
			ignore_variant=True
		)
