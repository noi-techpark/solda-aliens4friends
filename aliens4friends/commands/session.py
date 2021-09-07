# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging

from aliens4friends.commons.session import Session
from aliens4friends.commons.pool import Pool

logger = logging.getLogger(__name__)

class SessionCommand:

	@staticmethod
	def execute(pool: Pool, session_id: str = "") -> None:
		session = Session(pool, session_id)
		session.create()
		print(session.session_id)


