# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import csv

from aliens4friends.commons.version import Version, VersionError


def test(v1str, v2str):
	try:
		v1 = Version(v1str)
		v2 = Version(v2str)
		print(v1.similarity(v2))
	except VersionError:
		print("")


if __name__ == '__main__':

	with open('matchResults.csv') as f:
		reader = csv.reader(f)
		for rec in reader:
			alien_version = rec[5]
			match_version = rec[6]
			# print(rec[0], end=" ")
			test(alien_version, match_version)
