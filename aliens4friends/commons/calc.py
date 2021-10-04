# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

import numpy

from .aliases import ALIASES

class Calc:

	# share of package valuation
	# the smaller, the more likely the version distance determines the best match
	# identical package names != best match (example: gnutls => gnutls28)
	PACKAGE_WEIGHT = 0.5
	SCORES = {
		"s100" : "Ident or alias match",
		"s95" : "Removed '-' from package name",
		"s90" : "Removed numbers and '-' from package name or prefixed with the abbreviation isc-",
		"s85" : "Some libraries may lack a lib prefix",
		"s80" : "python without '3'",
		"s70" : "python without 'python' or fonts that start with 'fonts-' in Debian",
		"s60" : "Library/API version at the end of the package name",
		"s0" : "Not matching at all"
	}

	VSCORES = {
		"s100" : "Ident",
		"s99" : "Version distance <= 10",
		"s-100" : "Package match invalidation: FLAG_DEB_VERSION_ERROR",
		"s-99" : "Package match invalidation: 0 versions found",
		"s50" : "Version distance < KO_DISTANCE (10000)",
		"s10" : "Version distance < MAX_DISTANCE (10000000)",
		"s0" : "Not matching at all",
	}

	@staticmethod
	def levenshtein(first, second):

		if first == second:
			return 0

		dist = numpy.zeros((len(first) + 1, len(second) + 1))

		for f in range(len(first) + 1):
			dist[f][0] = f

		for s in range(len(second) + 1):
			dist[0][s] = s

		insert = 0
		delete = 0
		replace = 0

		for f in range(1, len(first)+1):
			for s in range(1, len(second)+1):
				if (first[f-1] == second[s-1]):
					dist[f][s] = dist[f-1][s-1]
				else:
					insert = dist[f][s-1]
					delete = dist[f-1][s]
					replace = dist[f-1][s-1]

					if (insert <= delete and insert <= replace):
						dist[f][s] = insert+1
					elif (delete <= insert and delete <= replace):
						dist[f][s] = delete+1
					else:
						dist[f][s] = replace+1

		res = dist[len(first)][len(second)]

		return res

	@staticmethod
	def _clean_name(name: str) -> str:
		return name.rstrip("0123456789.~+").replace("-v", "").replace("-", "")

	@staticmethod
	def overallScore(packageScore, versionScore) -> int:
		packageScore = packageScore * Calc.PACKAGE_WEIGHT
		versionScore = versionScore * (1 - Calc.PACKAGE_WEIGHT)
		return max(0, packageScore + versionScore)

	# TODO: score version distance between 0-100
	@staticmethod
	def fuzzy_version_score(distance) -> int:
		return 0

	@staticmethod
	def version_score_ident(score) -> str:
		return Calc.VSCORES["s" + str(score)]

	@staticmethod
	def package_score_ident(score) -> str:
		return Calc.SCORES["s" + str(score)]

	@staticmethod
	def fuzzy_package_score(given: str, new: str) -> int:

		if given == new:
			return 100

		# Rename known packages to their Debian counterpart
		if given in ALIASES:
			given = ALIASES[given]

		# We are sure that hardcoded aliases match perfectly
		if given == new:
			return 100

		# (glib-2.0 => glib2.0)
		if given.replace("-", "") == new:
			return 95

		g = Calc._clean_name(given)
		n = Calc._clean_name(new)

		# cleaned package names
		if n == g:
			return 90

		# Prefixed with the abbreviation isc- (Internet Software Consortium)
		# Possibly postfixed with -client or -server
		if n.startswith(f"isc{g}"):
			return 90

		# Some libraries may lack a lib prefix
		if (
			(g.startswith("lib") or n.startswith("lib"))
			and g.replace("lib", "") == n.replace("lib", "")
		):
			return 85

		# Major Python version mismatch: python3-iniparse vs. python-iniparse
		# Some python packages do not have a python[23]- prefix
		if (
			n.startswith("python3")
			or g.startswith("python3")
		):
			nn = n.replace("python3", "python")
			gg = g.replace("python3", "python")
			if nn == gg:
				return 80
			if nn.replace("python", "") == gg.replace("python", ""):
				return 70

		# Fonts may start with "fonts-" in Debian
		if g.replace("fonts", "") == n.replace("fonts", ""):
			return 70

		# Library/API version at the end of the package name
		if n.startswith(g):
			return 60

		# --> Not matching at all
		return 0
