# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import os
from typing import Any, List

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.harvester import Harvester
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class Harvest(Command):

	def __init__(self, session_id: str, add_missing: bool, use_oldmatcher: bool):
		super().__init__(session_id, processing=Processing.SINGLE)
		self.use_oldmatcher = use_oldmatcher
		self.add_missing = add_missing
		result_path = self.pool.relpath(Settings.PATH_STT)
		self.pool.mkdir(result_path)
		result_file = 'report.harvest.json'
		self.output = os.path.join(result_path, result_file)

	def get_filelist(self) -> List[str]:
		files = []
		for filetype in Harvester.SUPPORTED_FILES:
			if (
				filetype == FILETYPE.ALIENMATCHER and not self.use_oldmatcher
				or
				filetype == FILETYPE.SNAPMATCH and self.use_oldmatcher
			):
				continue

			files += self.session.package_list_paths(filetype, only_selected=False)
		return files

	def print_results(self, results: Any) -> None:
		print(results.to_json())

	@staticmethod
	def execute(
		add_missing: bool,
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> bool:
		cmd = Harvest(session_id, add_missing, use_oldmatcher)
		return cmd.exec(cmd.get_filelist())

	def run(self, files: List[str]) -> str:
		harvest = Harvester(
			self.pool,
			files,
			self.output,
			self.add_missing,
			self.use_oldmatcher,
			session=self.session
		)
		harvest.readfile()
		harvest.write_results()
		logger.info(f'Results written to {self.pool.clnpath(self.output)}.')
		return self.output
