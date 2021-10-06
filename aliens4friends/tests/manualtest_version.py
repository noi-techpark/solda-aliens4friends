# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import csv

from aliens4friends.commons.version import Version, VersionError

results = []

if __name__ == '__main__':

	with open('matchResults.csv') as f:
		reader = csv.reader(f)
		c = 0
		for rec in reader:
			c += 1
			if c == 1:
				continue
			alien_version = rec[5]
			match_version = rec[6]

			error = ""
			try:
				v1 = Version(alien_version)
				v2 = Version(match_version)
				sim = v1.similarity(v2, simplified=True)
			except VersionError as ex:
				error = str(ex)
				continue

			results.append(
				[
					rec[0],
					v1.str_simple if v1 else "",
					v2.str_simple if v2 else "",
					sim,
					rec[12],
					error
				]
			)
			v1 = None
			v2 = None
			sim = 0
			# if c == 40:
			# 	break

	for r in results:
		print(f"{r[0]:<45}{r[1]:<12}{r[2]:<12}{r[3]:<12}{r[4]:<12}{r[5]}")
