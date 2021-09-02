# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0
#
# FIXME This method will replace match in short time, which involves some cleanup.
#   - Remove all match vs snapmatch csv outputs and comparisons
#   - Remove the old match command
#   - Move this into the "match" subcommand: cleanup also docs and the help text

import collections as col
import json
import os
import sys
import logging
import copy
import csv
import time
import numpy

from pathlib import Path

from aliens4friends.commons.pool import Pool, PoolError
from aliens4friends.models.base import ModelError
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.version import Version
from urllib.parse import quote as url_encode
from multiprocessing import Pool as MultiProcessingPool

from enum import Enum
from typing import Union, Any, Optional, List, Tuple

import requests
from debian.deb822 import Deb822

from urllib3.exceptions import NewConnectionError

from aliens4friends.commons.package import AlienPackage, Package, PackageError, DebianPackage
from aliens4friends.models.alienmatcher import (
	AlienSnapMatcherModel,
	Tool,
	AlienSrc,
	DebianSnapMatch,
	SourceFile
)

logger = logging.getLogger(__name__)

class AlienSnapMatcherError(Exception):
	pass

class AlienSnapMatcher:

	API_URL_ALLSRC = "https://snapshot.debian.org/mr/package/"
	API_URL_FILES = "https://snapshot.debian.org/file/"
	API_URL_FILEINFO = "https://snapshot.debian.org/mr/file/"

	REQUEST_THROTTLE = 5

	def __init__(self) -> None:
		super().__init__()
		self.pool = Pool(Settings.POOLPATH)
		AlienSnapMatcher.loadSources()
		self._load_aliases_exclusions()
		logging.getLogger("urllib3").setLevel(logging.WARNING)


	@staticmethod
	def get_data(uri : str) -> Any:

		# handling snapshot.debian trailing slash inconsistencies
		name = uri.split("://")[1].replace("/",".").replace(":",".")
		if not name.endswith("."):
			name = name + "."
		name = "a4f.snap_match-" + name + "json"

		pool = Pool(Settings.POOLPATH)
		api_response_cached = pool.relpath(Settings.PATH_TMP, name)

		try:
			response = pool.get(api_response_cached)
		except FileNotFoundError:
			logger.debug(f"API call result not found in cache. Making an API call...")
			try:
				time.sleep(AlienSnapMatcher.REQUEST_THROTTLE)
				response = requests.get(uri)
				if response.status_code != 200:
					raise AlienSnapMatcherError(
						f"Cannot get API response, got error {response.status_code}"
						f" from {uri}")
					return json.loads("{}")
				with open(Settings.POOLPATH + "/" + api_response_cached, "w") as f:
					f.write(response.text)
				response = response.text
			except NewConnectionError:
				logger.error(f"Target temporarily not reachable {uri}")

		return json.loads(response)

	# name & version-match for debian packages.
	def match(self, apkg: AlienPackage, amm: AlienSnapMatcherModel, results: List[Union[int, str]]) -> None:

		logger.debug(f"[{self.curpkg}] Find a matching package through Debian Snapshot API.")

		pool = Pool(Settings.POOLPATH)

		main_match = False
		snap_match = False

		main_match_path = pool.relpath(
			Settings.PATH_USR,
			apkg.name,
			apkg.version.str,
			f"{apkg.name}-{apkg.version.str}.alienmatcher.json"
		)

		try:
			main_match = pool.get_json(main_match_path)
			main_match = main_match['debian']['match']
			results.append(main_match['name'] or '-')
			results.append(main_match['version'] or '-')
			results.append('found' if main_match['debsrc_orig'] or main_match['debsrc_debian'] else '-')
			# matcher distance
			v1 = Version(main_match['version'])
			distance = apkg.version.distance(v1)
			results.append(distance)

		except Exception as ex:
			results.append('-')
			results.append('-')
			results.append('missing')
			results.append('-')
			logger.warning(
				f"[{self.curpkg}] Unable to load current alienmatch from {main_match_path}."
			)

		resultpath = pool.relpath(
			Settings.PATH_USR,
			apkg.name,
			apkg.version.str,
			f"{apkg.name}-{apkg.version.str}.snapmatch.json"
		)

		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError()
			amm = AlienSnapMatcherModel.from_file(pool.abspath(resultpath))
			if amm.match.score > 0:
				results.append(amm.match.name)
				results.append(amm.match.version)
				results.append('found')
				v1 = Version(amm.match.version)
				distance = apkg.version.distance(v1)
				results.append(distance)
				results.append(amm.match.score)
				results.append(amm.match.package_score)
				results.append(amm.match.version_score)
				outcome = "MATCH"
			else:
				results.append('-')
				results.append('-')
				results.append('missing')
				results.append('-')
				results.append(amm.match.score)
				results.append('-')
				results.append('-')
				amm.errors.append("NO MATCH without errors")
				outcome = "NO MATCH"
			logger.debug(f"[{self.curpkg}] Result already exists ({outcome}), skipping.")
			return
		except FileNotFoundError:
			pass
		except (PoolError, ModelError) as ex:
			logger.warning(
				f"[{self.curpkg}] Result file already exists but it is not readable: {ex}"
			)

		int_arch_count = apkg.internal_archive_count()
		if int_arch_count > 1:
			if apkg.internal_archive_name:
				logger.warning(
					f"[{self.curpkg}] The Alien Package"
					f" {apkg.name}-{apkg.version.str} has more than one"
					 " internal archive, using just primary archive"
					f" '{apkg.internal_archive_name}' for comparison"
				)
			else:
				logger.warning(
					f"[{apkg.name}-{apkg.version.str}] IGNORED: Alien Package has"
					f" {int_arch_count} internal archives and no primary archive."
					 " We support comparison of one archive only at the moment!"
				)
				results.append('-')
				results.append('-')
				results.append('no primary archive')
				results.append('-')
				amm.errors.append(
					f"{int_arch_count} internal archives and no primary archive"
				)
				return
		elif int_arch_count == 0:
			logger.warning(
				f"[{apkg.name}-{apkg.version.str}] IGNORED: Alien Package has"
				 " no internal archive, nothing to compare!"
			)
			results.append('-')
			results.append('-')
			results.append('no internal archive')
			results.append('-')
			amm.errors.append("no internal archive")
			return

		snap_match = self._searchPackage(apkg, True)

		# if we found at least something, fetch sources
		if snap_match.score > 0:
			self.get_all_sourcefiles(snap_match) # pass snap_match by reference
			self.download_all_to_debian(snap_match)

			amm.match = snap_match

			results.append(amm.match.name)
			results.append(amm.match.version)

			results.append('found')

			pool.write_json(amm, resultpath)

			# snapmatcher distance
			v1 = Version(amm.match.version)
			distance = apkg.version.distance(v1)
			results.append(distance)

			results.append(snap_match.score)
			results.append(snap_match.package_score)
			results.append(snap_match.version_score)
			logger.info(
				f"[{self.curpkg}] MATCH: {snap_match.name} {snap_match.version}"
				f" (score: {snap_match.score})"
			)

		else:
			results.append('-')
			results.append('-')
			results.append('missing')
			results.append('-')
			results.append(snap_match.score)
			results.append('-')
			results.append('-')
			amm.errors.append("NO MATCH without errors")
			logger.info(f"[{self.curpkg}] NO MATCH")


	def get_file_info(self, filehash: str) -> Union[dict, bool]:
		uri = AlienSnapMatcher.API_URL_FILEINFO + filehash + "/info"
		fileinfo = self.get_data(uri)
		if fileinfo["result"] and len(fileinfo["result"]) > 0:
			return fileinfo["result"][0]
		return False

	def download_all_to_debian(self, snap_match: DebianSnapMatch) -> None:
		for srcfile in snap_match.srcfiles:
			logger.debug(
				f"[{self.curpkg}] Retrieving file from Debian:"
				f" '{srcfile.name}'."
			)
			try:
				if not Settings.POOLCACHED:
					raise FileNotFoundError
				response = self.pool.get_binary(
					Settings.PATH_DEB,
					snap_match.name,
					snap_match.version,
					srcfile.name
				)
				logger.debug(f"[{self.curpkg}] Found in Debian cache pool.")
			except FileNotFoundError:
				logger.debug(f"[{self.curpkg}] Not found in Debian cache pool.")
				logger.debug(
					f"[{self.curpkg}] Trying to download deb source {srcfile.name}"
					f" from {srcfile.src_uri}."
				)
				r = requests.get(srcfile.src_uri)
				if r.status_code != 200:
					raise AlienSnapMatcherError(
						f"Error {r.status_code} in downloading {srcfile.name}"
					)
				local_path = self.pool.write(
					r.content,
					Settings.PATH_DEB,
					snap_match.name,
					snap_match.version,
					srcfile.name
				)
				logger.debug(f"[{self.curpkg}] Result cached in {local_path}.")
	def get_all_sourcefiles(self, snap_match, bin_files = False) -> None:
		uri = AlienSnapMatcher.API_URL_ALLSRC + snap_match.name +"/"+ snap_match.version +"/allfiles"
		logger.info(f"[{self.curpkg}] Acquire package sources from " + uri)
		hashes = self.get_data(uri)

		snap_match.srcfiles = []

		if bin_files:
			for binary in hashes["result"]["binaries"]:
				for file in binary["files"]:
					info = self.get_file_info(file["hash"])
					source = SourceFile(
						name=info["name"],
						sha1_cksum=file["hash"],
						src_uri=AlienSnapMatcher.API_URL_FILES + file["hash"],
						paths=[info["path"]]
					)
					snap_match.srcfiles.append(source)
		else:
			for file in hashes["result"]["source"]:
				info = self.get_file_info(file["hash"])
				source = SourceFile(
					name=info["name"],
					sha1_cksum=file["hash"],
					src_uri=AlienSnapMatcher.API_URL_FILES + file["hash"],
					paths=[info["path"]]
				)
				snap_match.srcfiles.append(source)


	@staticmethod
	def clearDiff():
		pool = Pool(Settings.POOLPATH)

		compare_csv = pool.abspath(
			Settings.PATH_USR,
			f"match_vs_snapmatch.csv"
		)

		with open(compare_csv, 'w+') as csvfile:
			csvwriter = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
			csvwriter.writerow(["alien name", "alien version", "name match", "version match", "match status", "version match distance", "name snapmatch", "version snapmatch", "snapmatch status", "version snapmatch distance", "snapscore", "package match info", "version match info"])

	def _load_aliases_exclusions(self) -> None:
		# check for aliases and exclusions
		dir_path = os.path.dirname(os.path.realpath(__file__))
		with open(dir_path + '/../commons/aliases.json', 'r') as aliasfile:
			data=aliasfile.read()
		jsona = json.loads(data)
		self.exclusions = jsona["exclude"]
		self.aliases = jsona["aliases"]


	def run(self, package_path: Union[str, Path]) -> Optional[AlienSnapMatcherModel]:

		try:
			# Return model in any case, we need to keep also "no match" results
			package = AlienPackage(package_path)
			self.curpkg = f"{package.name}-{package.version.str}"
			amm = AlienSnapMatcherModel(
				tool=Tool(__name__, Settings.VERSION),
				aliensrc=AlienSrc(
					name = package.name,
					version = package.version.str,
					alternative_names = package.alternative_names,
					internal_archive_name = None,
					filename = package.archive_name,
					files = package.package_files
				)
			)
			results = []
			results.append(package.name)
			results.append(package.version.str)

			if package.name in self.exclusions:
				logger.warning(f"[{self.curpkg}] IGNORED: Known non-debian")
				amm.errors.append("IGNORED: Known non-debian")
			else:
				package.expand()
				amm.aliensrc.internal_archive_name = package.internal_archive_name

				self.match(package, amm, results) # pass amm and results by reference

				compare_csv = self.pool.abspath(
					Settings.PATH_USR,
					f"match_vs_snapmatch.csv"
				)

				with open(compare_csv, 'a+') as csvfile:
					csvwriter = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
					csvwriter.writerow(results)

		except (AlienSnapMatcherError, PackageError) as ex:
				logger.error(f"[{self.curpkg}] ERROR: {ex}")

		return amm

	# search for package string, if found check version and return an overall matching score
	def _searchPackage(self, apkg : AlienPackage, altSearch = True) -> DebianSnapMatch:
		logger.info(f"[{self.curpkg}] Searching for {apkg.name} v {apkg.version.str} @ snapshot.debian.org/mr/package")

		name_needle = apkg.name
		res = DebianSnapMatch()

		for pkg in SNAP_ALL_SOURCES["result"]:

			if apkg.name in self.aliases:
				if pkg["package"] == self.aliases[apkg.name]:
					fuzzy_score = 100
					similarity = 0
				else:
					continue
			else:
				similarity = Calc.levenshtein(name_needle, pkg["package"])
				fuzzy_score = Calc.fuzzy_package_score(name_needle, pkg["package"], {})

			# logger.debug(f"[{apkg.name}] vs { pkg['package'] } / { fuzzy_score }")

			# guessing packages
			if fuzzy_score > 0:
				logger.info(f"[{self.curpkg}] Fuzzy package match { name_needle } vs { pkg['package'] }: { fuzzy_score }")
				versionMatch = self._searchVersion(apkg, pkg['package'])
				fuzzy_overall = Calc.overallScore(fuzzy_score, versionMatch["score"])

				# best scoring package wins
				if res.score == 0 or fuzzy_overall >= res.score:
					versionMatch = self._searchVersion(apkg, pkg['package'])
					logger.info(f"[{apkg.name}] = { pkg['package'] } / Best score { fuzzy_overall }")
					res.package_score = fuzzy_score
					res.package_score_ident = Calc.package_score_ident(int(res.package_score))
					res.version_score = versionMatch["score"]
					res.version_score_ident = Calc.version_score_ident(int(res.version_score))
					res.score = Calc.overallScore(fuzzy_score, versionMatch["score"])

					res.name = versionMatch["package"]
					res.version = versionMatch["slug"]
					res.distance = similarity

		return res

	# search for package version and return a matching score. score can be negative in order that score-sum can invalidate any positive package score
	def _searchVersion(self, apkg : AlienPackage, altname = False) -> Any:

		logger.debug(f"[{self.curpkg}]  Searching for package version { apkg.name } { apkg.version.str }")

		needle = apkg.name
		if altname:
			needle = altname

		res = {
			"package" : needle,
			"slug" : "",
			"score" : 0,
		}

		# TODO: complete invalidation = ok || should the package still be valid?
		if apkg.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			res['score'] = -100

		data = AlienSnapMatcher.get_data(AlienSnapMatcher.API_URL_ALLSRC + needle + '/')

		bestVersion = {
			"version" : "",
			"distance" : Version.MAX_DISTANCE,
		}

		if data["result"]:
			# higher priority for newer package versions - first check lower ones
			for item in reversed(data["result"]):
				itemVersion = Version(item["version"])

				# ident
				similarity = Calc.levenshtein(apkg.version.str, item["version"])

				# zero distance
				distance = itemVersion.distance(apkg.version)

				# logger.debug(f"[{needle}]  { apkg.version } vs { itemVersion }")

				# this does not happen, cause the cat bites its own tail
				if similarity == 0:
					logger.debug(f"[{self.curpkg}] {needle}: Exact version match (ident) { apkg.version.str } vs { item['version'] } is { similarity }")
					res['score'] = 100
					res['slug'] = item['version']
					return res

				elif distance <= 10:
					logger.debug(f"[{self.curpkg}] {needle}: Exact version match (distance) { apkg.version.str } vs { item['version'] } is { distance }")
					res['score'] = 99
					res['slug'] = item['version']
					return res

				if distance < Version.MAX_DISTANCE and bestVersion["distance"] >= distance:
					bestVersion["version"] = item['version']
					bestVersion["distance"] = distance

				# TODO: sometimes the major-version is missing: intel-microcode
		else:
			# should not be the case, cause if we find a package by name there should be at least 1 available version
			res['score'] = -99
			logger.debug(f"[{self.curpkg}] {needle}: Can not find any version for {apkg.version.str}")

		if bestVersion["distance"] < Version.MAX_DISTANCE:
			logger.debug(f"[{self.curpkg}] {needle}:  Fuzzy version match { apkg.version.str } vs { bestVersion['version'] }: { bestVersion['distance'] }")
			res['slug'] = bestVersion['version']
			if bestVersion["distance"] != Version.OK_DISTANCE:
				if bestVersion["distance"] < Version.KO_DISTANCE:
					res['score'] = 50
				else:
					res['score'] = 10

		# TODO: normalized distance as score
		return res

	@staticmethod
	def loadSources() -> None:
		if 'SNAP_ALL_SOURCES' not in globals():
			global SNAP_ALL_SOURCES
			SNAP_ALL_SOURCES = AlienSnapMatcher.get_data(AlienSnapMatcher.API_URL_ALLSRC)

	@staticmethod
	def execute(glob_name: str = "*", glob_version: str = "*") -> None:
		AlienSnapMatcher.loadSources()
		AlienSnapMatcher.clearDiff()

		pool = Pool(Settings.POOLPATH)
		results = [ 
			AlienSnapMatcher._execute(a) 
			for a in pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc")
		]

		if Settings.PRINTRESULT:
			for match in results:
				if match:
					print(match.to_json(indent=2))
		if not results:
			logger.info(
				f"Nothing found for packages '{glob_name}' with versions '{glob_version}'. "
				f"Have you executed 'add' for these packages?"
			)

	@staticmethod
	def _execute(path: Union[str, Path]) -> Optional[AlienSnapMatcherModel]:
		return AlienSnapMatcher().run(path)
