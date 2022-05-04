# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.models.tinfoilhat import TinfoilHatModel

from aliens4friends.commons.mirror import Mirror2pg
# FIXME this class need to be implemented

logger = logging.getLogger(__name__)

class Mirror(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool, dryrun: bool):
		super().__init__(session_id, Processing.MULTI, dryrun)

	def hint(self) -> str:
		return "mirror with db"

	@staticmethod
	def execute(
		session_id: str = "",
		dryrun: bool = True
	) -> bool:

		cmd = Mirror(session_id, dryrun)
		return cmd.exec_with_paths(FILETYPE.TINFOILHAT)

	def run(self, path: str) -> Union[str, bool]:
		mirror2pg = Mirror2pg(path)
		mirror2pg.do_stuff()
		return
