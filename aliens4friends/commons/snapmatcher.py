# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import tempfile
import time
from typing import Any, List, Union

import requests
from debian.deb822 import Deb822
from urllib3.exceptions import NewConnectionError

from aliens4friends.commons.aliases import ALIASES
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import md5bin
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

	# DEBIAN_ARCHIVES are in order of priority
	DEBIAN_ARCHIVES = [
		"debian",
		"debian-backports",
		"debian-security",
		"debian-debug",
		"debian-archive",
		"debian-ports",
		"debian-volatile",
	]

	REQUEST_THROTTLE = 5

	def __init__(self, pool: Pool) -> None:
		AlienSnapMatcher.loadSources()
		logging.getLogger("urllib3").setLevel(logging.WARNING)
		self.pool = pool

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
	def match(self, apkg: AlienPackage, amm: AlienSnapMatcherModel) -> None:

		logger.debug(f"[{self.curpkg}] Find a matching package through Debian Snapshot API.")

		snap_match = False

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
				amm.errors.append(
					f"{int_arch_count} internal archives and no primary archive"
				)
				return
		elif int_arch_count == 0:
			logger.warning(
				f"[{apkg.name}-{apkg.version.str}] IGNORED: Alien Package has"
				 " no internal archive, nothing to compare!"
			)
			amm.errors.append("no internal archive")
			return

		snap_match = self._searchPackage(apkg, True)

		# if we found at least something, fetch sources
		if snap_match.score > 0:
			self.get_debian_source_files(snap_match)

			amm.match = snap_match

			# snapmatcher distance
			logger.info(
				f"[{self.curpkg}] MATCH: {snap_match.name} {snap_match.version}"
				f" (score: {snap_match.score})"
			)

		else:
			amm.errors.append("NO MATCH without errors")
			logger.info(f"[{self.curpkg}] NO MATCH")


	def get_file_info(self, filehash: str) -> Union[dict, bool]:
		uri = AlienSnapMatcher.API_URL_FILEINFO + filehash + "/info"
		try:
			fileinfo = self.get_data(uri)
			return fileinfo["result"]
		except Exception as e:
			raise AlienSnapMatcherError(
				f"can't get file info from Snapshot Debian for hash {filehash}:"
				f" got {e.__class__.__name__}: {e}"
			)

	def get_debian_source_files(self, snap_match: DebianSnapMatch) -> None:

		# ----------------------------------------------------------------------
		# READ THIS FIRST, if you want to understand the rationale behind the
		# following code.
		# ----------------------------------------------------------------------
		# Occasionally there may be source package variants also in Debian, i.e.
		# packages with the same name and version but with a different set of
		# source files depending on target arch or on other factors: more
		# precisely, there may be multiple file names for the same checksum (eg.
		# in perl 5.30.1~rc1-1) or multiple checksums for the same file name
		# (eg. in libaio 0.3.111-1).
		# This means that there may be even more than one .dsc file for the same
		# source package (eg. in libaio 0.3.111-1).
		# Moreover, while Snapshot Debian API use only sha1 checksums, some .dsc
		# files may contain only md5 checksums of source files.
		# So we need a slightly more complex logic that one may expect to
		# reliably collect all relevant source files and related metadata from
		# Snapshot Debian API even in "package variant" cases.
		
		snap_match.srcfiles = []
		uri = (
			AlienSnapMatcher.API_URL_ALLSRC
			+ snap_match.name +"/"
			+ snap_match.version +"/allfiles"
		)
		logger.info(f"[{self.curpkg}] Acquire package sources from " + uri)
		all_files = { 
			d["hash"]: self.get_file_info(d["hash"]) 
			for d in self.get_data(uri)["result"]["source"] 
		}
		# DEBIAN_ARCHIVES are in order of priority; if we find a .dsc file in a
		# higher priority debian archive, we skip the remainder (this is needed
		# in case of variants with multiple .dsc files)
		dsc_file = None
		for arch in AlienSnapMatcher.DEBIAN_ARCHIVES:
			for hash, infos in all_files.items():
				for i in infos:
					if i['name'].endswith('.dsc') and i["archive_name"] == arch:
						dsc_file = SourceFile(
							name=i['name'],
							sha1_cksum=hash,
							src_uri=AlienSnapMatcher.API_URL_FILES + hash,
							paths=[i["path"]]
						)
						break
				if dsc_file:
					break
			if dsc_file:
				break
		if not dsc_file:
			raise AlienSnapMatcherError(
				"Can't find any .dsc file for debian package"
				f" {snap_match.name} {snap_match.version}"
			)
		snap_match.srcfiles.append(dsc_file)
		self.download_to_debian_pool(snap_match, dsc_file)
		dsc_file_content = self.get_from_debian_pool(snap_match, dsc_file)
		debian_control = Deb822(dsc_file_content)
		if debian_control.get('Checksums-Sha1'):
			lines = debian_control['Checksums-Sha1'].split('\n')
			dsc_has_sha1 = True
		else:
			lines = debian_control['Files'].split('\n')
			# .dsc file contains only md5 checksums
			dsc_has_sha1 = False
		dsc_sha1_file = {}
		if not dsc_has_sha1:
			dsc_md5_file = {}
		for line in lines:
			elem = line.strip().split()
			# Format is triple: "chksum size filename"
			if len(elem) != 3:
				continue
			hash = elem[0]
			filename = elem[2]
			if dsc_has_sha1:
				dsc_sha1_file.update({hash: filename})
			else:
				dsc_md5_file.update({hash: filename})
		if not dsc_has_sha1:
			# .dsc file contains only md5 checksums :( we need some magic here
			# to match them with sha1 checksums in Snapshot Debian API
			for sha1, info in all_files.items():
				uri = AlienSnapMatcher.API_URL_FILES + sha1
				r = requests.get(uri)
				if r.status_code != 200:
					raise AlienSnapMatcherError(
						f"Error {r.status_code} in downloading {info[0].name}"
					)
				md5 = md5bin(r.content)
				if md5 in dsc_md5_file:
					dsc_sha1_file.update({sha1: dsc_md5_file[md5]})
			if len(dsc_sha1_file) != len(dsc_md5_file):
				raise AlienSnapMatcherError(
					"file/checksum mismatch in debian package"
					f" {snap_match.name} {snap_match.version}:"
					f" debian control md5 file list is {dsc_md5_file}"
					f" while in Snapshot Debian we found only {dsc_sha1_file}"
				)
		for hash, filename in dsc_sha1_file.items():
			found = False
			for info in all_files[hash]:
				if info["name"] == filename:
					srcfile = SourceFile(
						name=info['name'],
						sha1_cksum=hash,
						src_uri=AlienSnapMatcher.API_URL_FILES + hash,
						paths=[info["path"]]
					)
					found = True
					snap_match.srcfiles.append(srcfile)
					self.download_to_debian_pool(snap_match, srcfile)
					break
			if not found:
				raise AlienSnapMatcherError(
					"file/checksum mismatch in debian package"
					f" {snap_match.name} {snap_match.version}:"					
				)
		for srcfile in snap_match.srcfiles:
			if srcfile.name.endswith('.dsc') or srcfile.name.endswith(".asc"):
				continue
			debian_relpath = self.pool.relpath(
				Settings.PATH_DEB,
				snap_match.name,
				snap_match.version,
				srcfile.name
			)
			snap_match.dsc_format = debian_control['Format']
			if snap_match.dsc_format == "1.0":
				if '.orig.' in srcfile.name:
					snap_match.debsrc_orig = debian_relpath
				else: # XXX Assume archives without patterns in name are from Debian
					snap_match.debsrc_debian = debian_relpath
			elif snap_match.dsc_format == "3.0 (quilt)":
				if '.debian.' in srcfile.name:
					snap_match.debsrc_debian = debian_relpath
				elif '.orig.' in srcfile.name:
					snap_match.debsrc_orig = debian_relpath
			elif snap_match.dsc_format == "3.0 (native)":
				snap_match.debsrc_orig = debian_relpath

	def get_from_debian_pool(
		self,
		snap_match: DebianSnapMatch,
		srcfile: SourceFile,
	) -> bytes:
		return self.pool.get_binary(
			Settings.PATH_DEB,
			snap_match.name,
			snap_match.version,
			srcfile.name
		)

	def download_to_debian_pool(
		self, 
		snap_match: DebianSnapMatch, 
		srcfile: SourceFile
	) -> None:
		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError
			self.get_from_debian_pool(snap_match, srcfile)
			logger.debug(
				f"[{self.curpkg}] {srcfile.name} found in Debian cache pool."
			)
		except FileNotFoundError:
			logger.debug(
				f"[{self.curpkg}] {srcfile.name} not found in Debian cache pool."
			)
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

	def download_all_to_debian(self, snap_match: DebianSnapMatch) -> None:
		for srcfile in snap_match.srcfiles:
			self.download_to_debian_pool(snap_match, srcfile)

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
				distance = itemVersion.distance(
					apkg.version if apkg.name != "intel-microcode"
					else Version("3."+apkg.version.str)
					# FIXME upstream! workaround for missing major version in Yocto recipe
				)

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
