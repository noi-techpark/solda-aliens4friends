# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import random

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.models.session import SessionModel
from aliens4friends.models.common import Tool

logger = logging.getLogger(__name__)

class SessionError(Exception):
	pass

# FIXME Create a Session utility class and move important functions there
class Session:

	@staticmethod
	def _random_string(length: int = 16):
		ranstr = ''
		for _ in range(length):
			ranstr += chr(random.randint(ord('a'), ord('z')))
		return ranstr

	@staticmethod
	def execute(pool: Pool, session_id: str = "") -> None:

		# Use an existing session ID, or use a predefined one and create relevant
		# files and folders from it.
		if session_id:
			file_path = pool.relpath(Settings.PATH_SES, f"{session_id}.json")
		else:
			# Create a new session with random ID. Repeat this until we find a
			# session.json that has not already been taken by a former run.
			while True:
				session_id = Session._random_string()
				file_path = pool.relpath(Settings.PATH_SES, f"{session_id}.json")
				if not pool.exists(file_path):
					break

		session = SessionModel(
			Tool(__name__, Settings.VERSION),
			session_id
		)

		pool.write_json(session, file_path)

		logger.debug(f"Session started with data in '{file_path}'.")

		print(session_id)


