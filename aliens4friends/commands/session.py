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

class Session:

	@staticmethod
	def _random_string(length: int = 16):
		ranstr = ''
		for _ in range(length):
			ranstr += chr(random.randint(ord('a'), ord('z')))
		return ranstr

	@staticmethod
	def execute(pool: Pool) -> None:


		session_id = Session._random_string()

		session = SessionModel(
			Tool(__name__, Settings.VERSION),
			session_id
		)

		full_path = pool.write_json(
			session,
			Settings.PATH_SES,
			f"{session_id}.json"
		)

		logger.debug(f"Session started with data in '{full_path}/{session_id}.json'.")

		print(session_id)


