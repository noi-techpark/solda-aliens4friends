# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
from typing import Any, Optional

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.alienmatcher import AlienMatcher
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.models.alienmatcher import AlienMatcherModel

logger = logging.getLogger(__name__)

class Match(Command):

	def __init__(self, session_id: str) -> None:
		super().__init__(session_id, processing=Processing.LOOP)
		self.alienmatcher = AlienMatcher(self.pool)

	def hint(self) -> str:
		return "add"

	def run(self, path: str) -> Optional[AlienMatcherModel]:
		return self.alienmatcher.match(path)

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
