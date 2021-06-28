import collections as col
import json
import os
import sys
import logging
import copy

import numpy

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.version import Version

from urllib.parse import quote as url_encode
from multiprocessing import Pool as MultiProcessingPool

from enum import Enum
from typing import Union, Any, Optional

import requests

from aliens4friends.commons.package import AlienPackage, Package, PackageError, DebianPackage
from aliens4friends.models.alienmatcher import (
	AlienMatcherModel,
	Tool,
	AlienSrc,
	DebianMatch,
	DebianMatchContainer,
	VersionCandidate
)

logger = logging.getLogger(__name__)

class AlienSnapMatcherError(Exception):
	pass

class AlienSnapMatcher:

	API_URL_ALLSRC = "https://snapshot.debian.org/mr/package/"

	def __init__(self) -> None:
		super().__init__()
		self.errors = []
		AlienSnapMatcher.loadSources()
		logging.getLogger("urllib3").setLevel(logging.WARNING)

	def _reset(self) -> None:
		self.errors = []

	@staticmethod
	def get_data(uri : str) -> Any:
		name = "a4f.snap_match-" + uri.split("://")[1].replace("/",".") + "json"

		pool = Pool(Settings.POOLPATH)
		api_response_cached = pool.relpath(Settings.PATH_TMP, name)

		try:
			response = pool.get(api_response_cached)
			logger.debug(f"API call result found in cache at {api_response_cached}.")
		except FileNotFoundError:
			logger.debug(f"API call result not found in cache. Making an API call...")
			response = requests.get(uri)
			if response.status_code != 200:
				raise AlienSnapMatcherError(
					f"Cannot get API response, got error {response.status_code}"
					f" from {uri}")
				return json.loads("{}")
			with open(Settings.POOLPATH + "/" + api_response_cached, "w") as f:
				f.write(response.text)
			response = response.text
		return json.loads(response)

	# name & version-match for debian packages.
	def match(self, apkg: AlienPackage) -> AlienMatcherModel:
		res = self._searchPackage(apkg, True)

		logger.info(f"[{self.curpkg}] Matching: Package version { apkg.name } has a resulting score of { res['score'] }")

		# if we find at least something, fetch and download sources
		if res['score'] > 0:
			uri = AlienSnapMatcher.API_URL_ALLSRC + res['package_slug'] +"/"+ res['version_slug'] +"/srcfiles"
			sources = self.get_package_sourcefiles(uri)
			self.download_sources(sources)

		return score

	def download_sourcefiles(self, sources):
		logger.info(f"[{self.curpkg}] Download package sources")

	def get_package_sourcefiles(self, uri):
		logger.info(f"[{self.curpkg}] Acquire package sources from " + uri)
		hashes = self.get_data(uri)
		print(hashes["result"])
		return hashes["result"]

	def run(self, package_path: str) -> Optional[AlienMatcherModel]:
		try:

			package = AlienPackage(package_path)
			self.curpkg = f"{package.name}-{package.version.str}"
			package.expand()

			resultScore = self.match(package)

		except (AlienSnapMatcherError, PackageError) as ex:
			if str(ex) == "No internal archive":
				logger.warning(f"[{self.curpkg}] IGNORED: {ex}")
			elif str(ex) == "Can't find a similar package on Debian repos":
				logger.warning(f"[{self.curpkg}] NO MATCH: {ex}")
			else:
				logger.error(f"[{self.curpkg}] ERROR: {ex}")
			return None

	# search for package string, if found check version and return an overall matching score
	def _searchPackage(self, apkg : AlienPackage, altSearch = True) -> int:
		logger.debug(f"Searching for {apkg.name} v {apkg.version.str} @ snapshot.debian.org/mr/package")

		# TODO: Model (?)
		res = {
			"name" : apkg.name,
			"package_slug" : "",
			"version_slug" : "",
			"score" : 0,
		}

		alt_res = res

		name_needle = apkg.name

		major = apkg.version.package_version.major

		# if major version > 1, try to find exact package name with appended version number, preventing false-positive package detection provoking version mismatches
		if major > 1 and altSearch == True:
			altpkg = copy.deepcopy(apkg)
			altpkg.name = name_needle + str(major)
			alt_res = self._searchPackage(altpkg, False)

		for pkg in SNAP_ALL_SOURCES["result"]:
			similarity = Calc.levenshtein(name_needle, pkg["package"])
			fuzzy_score = Calc.fuzzyScore(name_needle, pkg["package"])

			# exact package match
			if similarity == 0:
				versionMatch = self._searchVersion(apkg)
				logger.debug(f"Exact match { name_needle } vs { pkg['package'] }")
				res['score'] = 100 + versionMatch["score"]
				res['package_slug'] = name_needle
				res['version_slug'] = versionMatch["slug"]
				break

			# guessing packages
			elif fuzzy_score > 0:
				versionMatch = self._searchVersion(apkg)
				logger.debug(f"Fuzzy match { name_needle } vs { pkg['package'] }")
				res['score'] = fuzzy_score + versionMatch["score"]
				res['package_slug'] = name_needle
				res['version_slug'] = versionMatch["slug"]
				break

		if alt_res['score'] > res['score']:
			logger.debug(f"Alternative match { altpkg.name } has better score ({ alt_res['score'] }) than { apkg.name } ({ res['score'] }) ")
			res = alt_res
			res['name'] = apkg.name

		return res

	# search for package version and return a matching score. score can be negative in order that score-sum can invalidate any positive package score
	def _searchVersion(self, apkg : AlienPackage) -> Any:

		logger.debug(f"  Searching for package version { apkg.name } { apkg.version.str }")

		res = {
			"slug" : "",
			"score" : 0,
		}

		res['score']

		slug = ""
		score = 0

		# TODO: complete invalidation = ok || should the package still be valid?
		if apkg.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			res['score'] = -100

		data = AlienSnapMatcher.get_data(AlienSnapMatcher.API_URL_ALLSRC + apkg.name + '/')

		bestVersion = {
			"version" : "",
			"distance" : Version.MAX_DISTANCE,
		}

		if data["result"]:
			for item in data["result"]:
				itemVersion = Version(item["version"])

				# ident
				similarity = Calc.levenshtein(apkg.version.str, item["version"])

				# zero distance
				distance = itemVersion.distance(apkg.version)

				if similarity == 0:
					logger.debug(f"  Exact version match (ident) { apkg.version.str } vs { item['version'] } is { similarity }")
					res['score'] = 100
					res['slug'] = item['version']

				if distance == 0:
					logger.debug(f"  Exact version match (distance) { apkg.version.str } vs { item['version'] } is { distance }")
					res['score'] = 100
					res['slug'] = item['version']

				if distance < Version.MAX_DISTANCE and bestVersion["distance"] > distance:
					bestVersion["version"] = itemVersion
					bestVersion["distance"] = distance

				# TODO: sometimes the major-version is missing: intel-microcode
		else:
			# should not be the case, cause if we find a package by name there should be at least 1 available version
			res['score'] = -100
			logger.debug(f"  Can not find any version for {apkg.version.str}")

		if bestVersion["distance"] < Version.MAX_DISTANCE:
			logger.debug(f"  Fuzzy version match { apkg.version.str } vs { bestVersion['version'].str }: { bestVersion['distance'] }")
			res['slug'] = bestVersion['version'].str

			if bestVersion["distance"] < Version.KO_DISTANCE:
				res['score'] = 50
			else:
				res['score'] = 10

		return res

	def loadSources() -> None:
		if 'SNAP_ALL_SOURCES' not in globals():
			global SNAP_ALL_SOURCES
			SNAP_ALL_SOURCES = AlienSnapMatcher.get_data(AlienSnapMatcher.API_URL_ALLSRC)

	@staticmethod
	def execute(glob_name: str = "*", glob_version: str = "*") -> None:
		AlienSnapMatcher.loadSources()

		pool = Pool(Settings.POOLPATH)

		multiprocessing_pool = MultiProcessingPool()

		packages = pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc")

		results = multiprocessing_pool.map(AlienSnapMatcher._execute, packages)

		if Settings.PRINTRESULT:
			for match in results:
				print(json.dumps(match, indent=2))
		if not results:
			logger.info(
				f"Nothing found for packages '{glob_name}' with versions '{glob_version}'. "
				f"Have you executed 'add' for these packages?"
			)

	@staticmethod
	def _execute(path: str) -> None:
		return AlienSnapMatcher().run(path)
