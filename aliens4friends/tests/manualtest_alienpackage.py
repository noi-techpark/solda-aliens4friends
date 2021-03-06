# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import os

from aliens4friends.commons.package import AlienPackage

def test1():
	ap_path = os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA2",
		"alien-acl-2.2.53.aliensrc"
	)

	ap = AlienPackage(ap_path)
	ap.expand()
	ap.print_info()
