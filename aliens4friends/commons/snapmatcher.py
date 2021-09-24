# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0

import csv
import json
import logging
import time
from typing import Any, List, Union

import requests
from debian.deb822 import Deb822
from urllib3.exceptions import NewConnectionError

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.aliases import ALIASES
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import md5sum
from aliens4friends.commons.version import Version
from aliens4friends.models.alienmatcher import (AlienSnapMatcherModel,
                                                DebianSnapMatch, SourceFile)

logger = logging.getLogger(__name__)

class AlienSnapMatcherError(Exception):
	pass

class AlienSnapMatcher:

	API_URL_ALLSRC = "https://snapshot.debian.org/mr/package/"
	API_URL_FILES = "https://snapshot.debian.org/file/"
	API_URL_FILEINFO = "https://snapshot.debian.org/mr/file/"

	REQUEST_THROTTLE = 5

	def __init__(self) -> None:
		AlienSnapMatcher.loadSources()
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

		main_match = False
		snap_match = False

		main_match_path = self.pool.relpath_typed(
			FILETYPE.ALIENMATCHER,
			apkg.name,
			apkg.version.str
		)

		try:
			main_match = self.pool.get_json(main_match_path)
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
			self.get_format_orig_debian(snap_match)

			amm.match = snap_match

			results.append(amm.match.name)
			results.append(amm.match.version)

			results.append('found')

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

	def get_format_orig_debian(self, snap_match: DebianSnapMatch) -> None:
		for srcfile in snap_match.srcfiles:
			if srcfile.name.endswith('.dsc'):
				dsc_file = self.pool.abspath(
					Settings.PATH_DEB,
					snap_match.name,
					snap_match.version,
					srcfile.name
				)
				with open(dsc_file) as f:
					dsc_file_content = f.read()
				debian_control = Deb822(dsc_file_content)
				break
		debian_control_files = []

		if debian_control.get('Checksums-Sha1'):
			dsc_chksums = debian_control['Checksums-Sha1'].split('\n')
			sha1 = True
		else:
			dsc_chksums = debian_control['Files'].split('\n')
			sha1 = False

		for line in dsc_chksums:
			elem = line.strip().split()
			# Format is triple: "chksum size filename"
			if len(elem) != 3:
				continue
			debian_control_files.append(f"{elem[0]} {elem[2]}")

		srcfiles = []
		for srcfile in snap_match.srcfiles:
			if srcfile.name.endswith('.dsc'):
				continue
			if sha1:
				chksum = srcfile.sha1_cksum
			else:
				filepath = self.pool.abspath(
					Settings.PATH_DEB,
					snap_match.name,
					snap_match.version,
					srcfile.name
				)
				chksum = md5sum(filepath)
			srcfiles.append(f"{chksum} {srcfile.name}")

		if sorted(debian_control_files) != sorted(srcfiles):
			raise AlienSnapMatcherError(
				f"checksum mismatch in debian package {snap_match.name} {snap_match.version}:"
				f" debian control files are {debian_control_files} while snap match srcfiles"
				f" are {srcfiles}"
			)
		for srcfile in snap_match.srcfiles:
			if srcfile.name.endswith('.dsc'):
				continue
			debian_relpath = self.pool.relpath(
				Settings.PATH_DEB,
				snap_match.name,
				snap_match.version,
				srcfile.name
			)
			snap_match.dsc_format = debian_control['Format']
			if snap_match.dsc_format == "1.0":
				if 'orig' in srcfile.name:
					snap_match.debsrc_orig = debian_relpath
				else: # XXX Assume archives without patterns in name are from Debian
					snap_match.debsrc_debian = debian_relpath
			elif snap_match.dsc_format == "3.0 (quilt)":
				if 'debian' in srcfile.name:
					snap_match.debsrc_debian = debian_relpath
				elif 'orig' in srcfile.name:
					snap_match.debsrc_orig = debian_relpath
			elif snap_match.dsc_format == "3.0 (native)":
				snap_match.debsrc_orig = debian_relpath


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

	# search for package string, if found check version and return an overall matching score
	def _searchPackage(self, apkg : AlienPackage, altSearch = True) -> DebianSnapMatch:
		logger.info(f"[{self.curpkg}] Searching for {apkg.name} v {apkg.version.str} @ snapshot.debian.org/mr/package")

		name_needle = apkg.name
		res = DebianSnapMatch()

		for pkg in SNAP_ALL_SOURCES["result"]:

			if apkg.name in ALIASES:
				if pkg["package"] == ALIASES[apkg.name]:
					fuzzy_score = 100
					similarity = 0
				else:
					continue
			else:
				similarity = Calc.levenshtein(name_needle, pkg["package"])
				fuzzy_score = Calc.fuzzy_package_score(name_needle, pkg["package"])

			# logger.debug(f"[{apkg.name}] vs { pkg['package'] } / { fuzzy_score }")

			# guessing packages
			if fuzzy_score > 0:
				logger.debug(f"[{self.curpkg}] Fuzzy package match { name_needle } vs { pkg['package'] }: { fuzzy_score }")
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

				# zero distance
				distance = itemVersion.distance(apkg.version)

				logger.debug(f"[{needle}]  { apkg.version } vs { itemVersion }")

				if distance == 0:
					logger.debug(f"[{self.curpkg}] {needle}: Exact version match (ident) { apkg.version.str } vs { item['version'] } is 0")
					res['score'] = 100
					res['slug'] = item['version']
					return res

				if distance <= 10:
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
			res['distance'] = Version.MAX_DISTANCE
			logger.debug(f"[{self.curpkg}] {needle}: Cannot find any version for {apkg.version.str}")

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
