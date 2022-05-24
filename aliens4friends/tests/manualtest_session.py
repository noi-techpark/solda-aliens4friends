# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import os

from aliens4friends.commons.session import Session
from aliens4friends.commons.pool import Pool

def test_single():
	pool = Pool(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	)

	session = Session(pool, "test")
	session.lock("abc")
	print(session.get_lock())
	print(session.is_accessible())
	session.unlock(force=True)
	session.unlock()


if __name__ == "__main__":
	test_single()
