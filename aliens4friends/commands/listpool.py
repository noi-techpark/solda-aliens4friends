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
        testarg: str = ""
    ) -> bool:
        try:
            cmd = ListPool(session_id, getattr(Processing, processing))
        except AttributeError:
            raise CommandError(f"unknown processing type: {processing}")
        
        try:
            args = [ getattr(FILETYPE, filetype), True ]
            if testarg:
                args.append(testarg)
            return cmd.exec_with_paths(*args)
        except AttributeError:
            raise CommandError(f"unknown filetype: {filetype}")

