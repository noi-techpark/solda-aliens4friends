# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging

from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.utils import get_attr_names

logger = logging.getLogger(__name__)

class ListPool(Command):
    """list files in pool, for debugging"""

    def run(self, *args):
        print(*args)

    @staticmethod
    def execute(
        session_id: str = "",
        filetype: str = "TINFOILHAT",
        processing: str = "LOOP",
        testarg: str = "",
        testarg2: str = ""
    ) -> bool:
        try:
            cmd = ListPool(session_id, getattr(Processing, processing))
        except AttributeError:
            raise CommandError(f"unknown processing type: {processing}")
        
        try:
            args = [ getattr(FILETYPE, filetype), True ]
            if testarg and not testarg2:
                args.append(testarg)
            if not testarg and testarg2:
                args.append(testarg2)
            if testarg and testarg2:
                args.append([testarg, testarg2])

            return cmd.exec_with_paths(*args)
        except AttributeError:
            raise CommandError(f"unknown filetype: {filetype}")

