# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import os
from typing import Any, List, Optional

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.harvester import Harvester
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings
from aliens4friends.models.harvest import HarvestModel

logger = logging.getLogger(__name__)

class Harvest(Command):

	def __init__(
		self,
		session_id: str,
		add_missing: bool,
		with_binaries: List[str],
		use_oldmatcher: bool,
		dryrun: bool,
		filter_snapshot: Optional[str] = None,
		output_file: Optional[str] = None,
		report_name: Optional[str] = None
	) -> None:
		super().__init__(session_id, Processing.SINGLE, dryrun)
		self.use_oldmatcher = use_oldmatcher
		self.add_missing = add_missing
		self.with_binaries = with_binaries
		self.inside_pool = False if output_file else True

		if output_file:
			self.output = output_file
		else:
			result_path = self.pool.relpath(Settings.PATH_STT)
			result_file = report_name or 'report.harvest.json'
			self.pool.mkdir(result_path)
			self.output = os.path.join(result_path, result_file)
		self.filter_snapshot = filter_snapshot

	def get_filelist(self) -> List[str]:
		files = []
		for filetype in Harvester.SUPPORTED_FILES:
			if (
				filetype == FILETYPE.ALIENMATCHER and not self.use_oldmatcher
				or
				filetype == FILETYPE.SNAPMATCH and self.use_oldmatcher
			):
				continue

			files += self.session.package_list_paths(filetype)
		return files

	def print_results(self, results: Any) -> None:
		print(results[0].to_json(indent=2))

	@staticmethod
	def execute(
		add_missing: bool,
		with_binaries: List[str],
		use_oldmatcher: bool = False,
		session_id: str = "",
		dryrun: bool = False,
		filter_snapshot: Optional[str] = None,
		output_file: Optional[str] = "",
		report_name: Optional[str] = None
	) -> bool:
		cmd = Harvest(session_id, add_missing, with_binaries, use_oldmatcher, dryrun, filter_snapshot, output_file)
		return cmd.exec(cmd.get_filelist())

	def run(self, files: List[str]) -> Optional[HarvestModel]:
		harvest = Harvester(
			self.pool,
			files,
			self.output,
			self.inside_pool,
			self.add_missing,
			self.with_binaries,
			self.use_oldmatcher,
			session=self.session
		)
		harvest.readfile()
		if self.filter_snapshot:
			harvest.filter_snapshot(self.filter_snapshot)
		harvest.write_results()
		if self.inside_pool:
			logger.info(f'Results written to the POOL with history: {self.pool.clnpath(self.output)}.')
		else:
			logger.info(f'Results written to: {self.output}.')
		return harvest.result
