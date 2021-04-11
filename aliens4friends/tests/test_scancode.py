# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
from pathlib import Path
import json

from aliens4friends.scancode import Scancode
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.archive import Archive

CLEAN = True

def test_single():
	pool = Pool(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	)

	package_name = "acl"
	package_version_str = "2.2.53-2"
	debsrc_debian = "acl_2.2.53-2.debian.tar.xz"

	archive_path = pool.abspath("debian", package_name, package_version_str, debsrc_debian)

	archive = Archive(archive_path)

	res = Scancode.execute(archive, package_name, package_version_str)

	print(res)

def test_single_from_matcheroutput():
	pool = Pool(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	)

	Scancode.execute(pool.absglob("*.alienmatcher.json"))
