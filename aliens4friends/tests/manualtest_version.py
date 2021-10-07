# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import csv
from aliens4friends.commons.calc import Calc

from aliens4friends.commons.version import Version, VersionError

results = []

if __name__ == '__main__':

	with open('matchResults.csv') as f:
		reader = csv.reader(f)
		c = 0
		for rec in reader:
			c += 1
			if c == 1:
				header = [
					rec[0],
					"v1",
					"v2",
					"v_score",
					"p_score",
					"score",
					rec[12],
					"error"
				]
				continue
			alien_version = rec[5]
			match_version = rec[6]

			error = ""
			try:
				v1 = Version(alien_version)
				v2 = Version(match_version)
				version_score = v1.similarity(v2)
			except VersionError as ex:
				error = str(ex)
				#continue

			package_score = Calc.fuzzy_package_score(rec[0], rec[1])

			results.append(
				[
					rec[0],
					v1.str_simple if v1 else "",
					v2.str_simple if v2 else "",
					version_score,
					package_score,
					Calc.overallScore(package_score, version_score),
					rec[12],
					error
				]
			)
			v1 = None
			v2 = None
			version_score = 0
			package_score = 0
			# if c == 40:
			# 	break

	print(f"{header[0]:<45}{header[1]:<12}{header[2]:<12}{header[3]:<12}{header[4]:<12}{header[5]:<12}{header[6]:<12}{header[7]}")
	for r in sorted(results):
		print(f"{r[0]:<45}{r[1]:<12}{r[2]:<12}{r[3]:<12}{r[4]:<12}{r[5]:<12}{r[6]:<12}{r[7]}")
