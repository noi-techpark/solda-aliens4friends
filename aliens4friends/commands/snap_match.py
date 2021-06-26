import collections as col
import json
import os
import sys
import logging

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

	def search(self, package: Package) -> Package:
		packages = self._searchPackage(package)
		versions = self._searchVersion(package)
		return package

	def match(self, apkg: AlienPackage) -> AlienMatcherModel:
		logger.debug(f"Searching for {apkg.name} v {apkg.version.str} @ snapshot.debian.org/mr/package")

		score = 0

		for pkg in SNAP_ALL_SOURCES["result"]:
			similarity = Calc.levenshtein(apkg.name, pkg["package"])

			# exact package match
			if similarity == 0:
				logger.debug(f"Exact match { apkg.name } vs { pkg['package'] }")
				self._searchVersion(apkg)

		logger.info(f"[{self.curpkg}] COMPLETE: Package version {apkg.name} has a resulting score of {score}")

		return score

	def run(self, package_path: str) -> Optional[AlienMatcherModel]:
		try:
			package = AlienPackage(package_path)
			self.curpkg = f"{package.name}-{package.version.str}"
			package.expand()

			resultScore = self.match(package)


		except (AlienSnapMatcherError, PackageError) as ex:
			if str(ex) == "No internal archive":
				#logger.warning(f"[{self.curpkg}] IGNORED: {ex}")
				logger.warning(f"{ex}")
			elif str(ex) == "Can't find a similar package on Debian repos":
				#logger.warning(f"[{self.curpkg}] NO MATCH: {ex}")
				logger.warning(f"{ex}")
			else:
				#logger.error(f"[{self.curpkg}] ERROR: {ex}")
				logger.warning(f"{ex}")
			return None

	def _searchPackage(self, apkg : AlienPackage) -> str:
		return "todo"

	def _searchVersion(self, apkg : AlienPackage) -> str:
		logger.debug(f"  Searching for { apkg.name } { apkg.version.str }")

		if apkg.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			raise AlienMatcherError(
				f"  No parseable debian version: {package.version.str}."
			)

		logger.debug(f"  [{self.curpkg}] Package version {apkg.version.str} has a valid Debian versioning format.")

		data = AlienSnapMatcher.get_data(AlienSnapMatcher.API_URL_ALLSRC + apkg.name + '/')

		if data["result"]:
			for item in data["result"]:
				itemVersion = Version(item["version"])

				# ident
				similarity = Calc.levenshtein(apkg.version.str, item["version"])

				# zero distance
				distance = itemVersion.distance(apkg.version)

				if similarity == 0:
					logger.debug(f"  Exact version match { apkg.version.str } vs { item['version'] } is { similarity }")
					return True

				if distance == 0:
					logger.debug(f"  0 distance version match { apkg.version.str } vs { item['version'] } is { similarity }")
					return True

				# TODO: fuzzy detection

				# if major version changes, sometimes the name is appended with version-number: gnupg => gnupg2 / gnupg-2
				# sometimes the major-version is missing: intel-microcode
		else:
			logger.debug(f"  Can not find any version for {apkg.version.str}")

		return False

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
