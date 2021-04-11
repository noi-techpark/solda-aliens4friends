# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

from aliens4friends.debian2spdx import Debian2SPDX
import os

def test():
	root = os.path.join(
		os.getcwd(),
		"tmp",
		"pool",
		"debian",
		"alsa-lib",
		"1.2.4-1.1"
	)
	print(root)
	debsrc_orig = f"{root}/alsa-lib_1.2.4.orig.tar.bz2"
	debsrc_debian = f"{root}/alsa-lib_1.2.4-1.1.debian.tar.xz"
	d2s = Debian2SPDX(debsrc_orig, debsrc_debian)
	d2s.generate_SPDX()
	d2s.write_SPDX("/tmp/peter_test.spdx")
