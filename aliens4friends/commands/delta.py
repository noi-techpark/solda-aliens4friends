# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
from typing import Union, List

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.deltacodeng import DeltaCodeNG
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.models.alienmatcher import (AlienMatcherModel,
                                                AlienSnapMatcherModel)
from aliens4friends.models.deltacode import DeltaCodeModel	

logger = logging.getLogger(__name__)

class Delta(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool):
		super().__init__(session_id, processing=Processing.MULTI)
		self.use_oldmatcher = use_oldmatcher

	def hint(self) -> str:
		return "match/snapmatch"

	def print_results(self, results: List[Union[DeltaCodeModel, bool]]) -> None:
		for res in results:
			if isinstance(res, DeltaCodeModel):
				print(res.to_json())
			else:
				print(res)

	@staticmethod
	def execute(
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> bool:

		cmd = Delta(session_id, use_oldmatcher)
		return cmd.exec_with_paths(
			FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH,
			ignore_variant=True
		)

	def run(self, path: str) -> Union[DeltaCodeModel, bool]:

		name, version, _, _ = self.pool.packageinfo_from_path(path)
		package = f"{name}-{version}"

		try:
			if self.use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception:
			raise CommandError(f"[{package}] Unable to load json from {self.pool.clnpath(path)}.")

		logger.debug(f"[{package}] Files determined through {self.pool.clnpath(path)}")

		alien = model.aliensrc
		match = model.match
		if not match.name:
			logger.info(f"[{package}] no debian match to compare here")
			return True

		result_path = self.pool.relpath_typed(FILETYPE.DELTACODE, alien.name, alien.version)
		if self.pool.cached(result_path, debug_prefix=f"[{package}] "):
			return True

		logger.info(
			f"[{package}] calculating delta between debian package"
			f" {match.name}-{match.version} and alien package"
			f" {alien.name}-{alien.version}"
		)
		deltacode = DeltaCodeNG(
			self.pool,
			self.pool.abspath_typed(FILETYPE.SCANCODE, match.name, match.version, in_userland=False),
			self.pool.abspath_typed(FILETYPE.SCANCODE, alien.name, alien.version),
			self.pool.abspath(result_path)
		)
		dcmodel = deltacode.compare()
		deltacode.write_results()
		logger.debug(f'[{package}] Results written to {result_path}')
		for stat in deltacode.get_stats():
			logger.debug(f'[{package}] Stats: {stat}')
		return dcmodel
