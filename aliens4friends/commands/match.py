# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import json
import os
import logging
from multiprocessing import Pool as MultiProcessingPool

from typing import Tuple, Any, Optional

import requests
from debian.deb822 import Deb822

from aliens4friends.commons.archive import Archive, ArchiveError
from aliens4friends.commons.utils import sha1sum
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.package import AlienPackage, Package, PackageError, DebianPackage
from aliens4friends.commons.version import Version
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.models.alienmatcher import (
	AlienMatcherModel,
	Tool,
	AlienSrc,
	DebianMatch,
	VersionCandidate
)

logger = logging.getLogger(__name__)

class AlienMatcherError(Exception):
	pass

class AlienMatcher:

	# Type hints for attributes not declared in __init__
	curpkg: str

	"""
	Class to match an entry inside a yocto manifest file with debian packages
	libraries through an API, exactly or if not possible find the closest
	version.

	Information taken from:
	- Semantic versioning: https://semver.org/
	- Debian versioning: https://readme.phys.ethz.ch/documentation/debian_version_numbers/
	"""

	DEBIAN_BASEURL = [
		"http://deb.debian.org/debian/pool/main",
		"http://security.debian.org/debian-security/pool/updates/main",
		"http://deb.debian.org/debian/pool/non-free",
	]
	API_URL_ALLSRC = "https://api.ftp-master.debian.org/all_sources"

	def __init__(self) -> None:
		super().__init__()
		self.pool = Pool(Settings.POOLPATH)
		if 'DEB_ALL_SOURCES' not in globals():
			global DEB_ALL_SOURCES
			DEB_ALL_SOURCES = AlienMatcher.get_deb_all_sources()

		logging.getLogger("urllib3").setLevel(logging.WARNING)

	@staticmethod
	def get_deb_all_sources() -> Any:
		# we need a static method that can be invoked before using
		# multiprocessing in execute()
		pool = Pool(Settings.POOLPATH)
		api_response_cached = pool.relpath(
			Settings.PATH_TMP,
			f"deb_all_sources.json"
		)
		# FIXME add control if cached copy is outdated
		logger.debug(f"Search cache pool for existing API response.")
		try:
			response = pool.get_json(api_response_cached)
			logger.debug(f"API call result found in cache at {api_response_cached}.")
		except FileNotFoundError:
			logger.debug(f"API call result not found in cache. Making an API call...")
			response = requests.get(AlienMatcher.API_URL_ALLSRC)
			if response.status_code != 200:
				raise AlienMatcherError(
					f"Cannot get API response, got error {response.status_code}"
					f" from {AlienMatcher.API_URL_ALLSRC}")
			pool.write_json(response.text, api_response_cached)
			response = response.text
		return json.loads(response)

	def search(self, package: Package) -> Tuple[Package, int, int]:
		logger.debug(f"[{self.curpkg}] Search for similar packages with {self.API_URL_ALLSRC}.")
		if not isinstance(package, Package):
			raise TypeError("Parameter must be a Package.")

		if package.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			raise AlienMatcherError(
				f"No parseable debian version: {package.version.str}."
			)
		logger.debug(f"[{self.curpkg}] Package version {package.version.str} has a valid Debian versioning format.")

		candidates = []
		multi_names = False
		for pkg in DEB_ALL_SOURCES:

			similarity = Calc.fuzzy_package_score(package.name, pkg["source"])

			if similarity > 0:
				candidates.append([similarity, pkg["source"], pkg["version"]])
				if pkg["source"] != package.name:
					multi_names = True

		if len(candidates) == 0:
			raise AlienMatcherError(
				f"Can't find a similar package on Debian repos"
			)

		candidates = sorted(candidates, reverse=True)

		cur_package_name = candidates[0][1]
		cur_package_score = candidates[0][0]
		if package.name != cur_package_name:
			logger.debug(f"[{self.curpkg}] Package with name {package.name} not found. Trying with {cur_package_name}.")
		if multi_names:
			cand_set = set(c[1] for c in candidates)
			logger.debug(f"[{self.curpkg}] We have multiple similar packages for '{package.name}': {cand_set}.")

		logger.debug(f"[{self.curpkg}] API call result OK. Find nearest neighbor of {cur_package_name}/{package.version.str}.")

		self.candidate_list = [
			[package.version, 0, True]
		]
		seen = set()
		for c in candidates:
			if c[1] == cur_package_name:
				if c[2] in seen:
					continue
				version = Version(c[2])
				ver_distance = version.distance(package.version)
				self.candidate_list.append([version, ver_distance, False])
				seen.add(c[2])

		self.candidate_list = sorted(self.candidate_list, reverse=True)

		i = 0
		for v in self.candidate_list:
			if v[2] == True:
				break
			i += 1

		# find 2-nearest neighbors and take the one with the smallest distance
		try:
			nn1 = self.candidate_list[i-1]
		except IndexError:
			nn1 = [None, Version.MAX_DISTANCE]
		try:
			nn2 = self.candidate_list[i+1]
		except IndexError:
			nn2 = [None, Version.MAX_DISTANCE]

		best_candidate = nn1 if nn1[1] < nn2[1] else nn2

		if best_candidate:
			#pytype: disable=attribute-error
			logger.debug(
				f"[{self.curpkg}] Nearest neighbor on Debian is"
				f" {cur_package_name}/{best_candidate[0].str}."
			)
		else:
			logger.debug(f"[{self.curpkg}] Found no neighbor on Debian.")

		# FIXME This code has been partly extracted from snap_match.py, we should
		# create a method to solve scoring for all occasions.
		cur_version_score = -100
		if best_candidate[1] == 0:
			cur_version_score = 100
		elif best_candidate[1] <= 10:
			cur_version_score = 99
		elif best_candidate[1] < Version.KO_DISTANCE:
			cur_version_score = 50
		else:
			cur_version_score = 10

		return (
			Package(name = cur_package_name, version = best_candidate[0]),
			cur_package_score,
			cur_version_score
		)

	def download_to_debian(self, package_name: str, package_version: str, filename: str) -> bytes:
		logger.debug(
			f"[{self.curpkg}] Retrieving file from Debian:"
			f" '{package_name}/{package_version}/{filename}'."
		)
		try:
			response = self.pool.get_binary(
				Settings.PATH_DEB,
				package_name,
				package_version,
				filename
			)
			logger.debug(f"[{self.curpkg}] Found in Debian cache pool.")
		except FileNotFoundError:
			logger.debug(f"[{self.curpkg}] Not found in Debian cache pool.")
			pooldir = (
				package_name[0:4]
				if package_name.startswith('lib')
				else package_name[0]
			)
			for baseurl in self.DEBIAN_BASEURL:
				#FIXME find a better way (use Debian web API to find baseurl?)
				full_url = "/".join([
					baseurl,
					pooldir,
					package_name,
					filename
				])
				logger.debug(
					f"[{self.curpkg}] Trying to download deb sources from"
					f" {full_url}."
				)
				r = requests.get(full_url)
				if r.status_code == 200:
					break
			if r.status_code != 200:
				raise AlienMatcherError(
					f"Error {r.status_code} in downloading {filename}"
				)
			local_path = self.pool.write(
				r.content,
				Settings.PATH_DEB,
				package_name,
				package_version,
				filename
			)
			logger.debug(f"[{self.curpkg}] Result cached in {local_path}.")
			response = r.content
		return response

	def fetch_debian_sources(self, package: Package) -> DebianPackage:
		dsc_filename = f'{package.name}_{package.version.str}.dsc'
		dsc_file_content = self.download_to_debian(
			package.name,
			package.version.str,
			dsc_filename
		)
		debsrc_orig = None
		debsrc_debian = None
		debian_control = Deb822(dsc_file_content)

		debian_control_files = []
		for line in debian_control['Checksums-Sha1'].split('\n'):
			elem = line.strip().split()
			# Format is triple: "sha1 size filename"
			if len(elem) != 3:
				continue
			debian_control_files.append(elem)
			self.download_to_debian(package.name, package.version.str, elem[2])

			debian_relpath = self.pool.relpath(
				Settings.PATH_DEB,
				package.name,
				package.version.str,
				elem[2]
			)

			if sha1sum(self.pool.abspath(debian_relpath)) != elem[0]:
				raise AlienMatcherError(f"Checksum mismatch for {debian_relpath}.")

			try:
				archive = Archive(elem[2])
				if debian_control['Format'] == "1.0":
					if 'orig' in archive.path:
						debsrc_orig = debian_relpath
					else: # XXX Assume archives without patterns in name are from Debian
						debsrc_debian = debian_relpath
				elif debian_control['Format'] == "3.0 (quilt)":
					if 'debian' in archive.path:
						debsrc_debian = debian_relpath
					elif 'orig' in archive.path:
						debsrc_orig = debian_relpath
				elif debian_control['Format'] == "3.0 (native)":
					debsrc_orig = debian_relpath
			except ArchiveError:
				# Ignore if not supported, it is another file and will be handled later
				pass

		return DebianPackage(
			package.name,
			package.version,
			debsrc_orig,
			debsrc_debian,
			debian_control['Format']
		)

	def match(self, apkg: AlienPackage) -> AlienMatcherModel:
		errors = []
		logger.debug(f"[{self.curpkg}] Find a matching package on Debian repositories.")
		int_arch_count = apkg.internal_archive_count()
		if int_arch_count > 1:
			if apkg.internal_archive_name:
				logger.warning(
					f"[{self.curpkg}] Alien Package has more than one"
					 " internal archive, using just primary archive"
					f" '{apkg.internal_archive_name}' for comparison"
				)
			else:
				logger.warning(
					f"[{apkg.name}-{apkg.version.str}] IGNORED: Alien Package has"
					f" {int_arch_count} internal archives and no primary archive."
					 " We support comparison of one archive only at the moment!"
				)
				errors.append(f"{int_arch_count} internal archives and no primary archive")
		elif int_arch_count == 0:
			logger.warning(
				f"[{apkg.name}-{apkg.version.str}] IGNORED: Alien Package has"
				 " no internal archive, nothing to compare!"
			)
			errors.append("no internal archive")
		resultpath = self.pool.relpath(
			Settings.PATH_USR,
			apkg.name,
			apkg.version.str,
			f"{apkg.name}-{apkg.version.str}.alienmatcher.json"
		)
		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError()
			json_data = self.pool.get_json(resultpath)
			amm = AlienMatcherModel(**json_data)
			debpkg = DebianPackage(
				amm.debian.match.name,
				amm.debian.match.version,
				amm.debian.match.debsrc_orig,
				amm.debian.match.debsrc_debian,
				amm.debian.match.dsc_format
			)
			logger.debug(f"[{self.curpkg}] Result already exists (MATCH), skipping.")

		except (PackageError):
			logger.debug(f"[{self.curpkg}] Result already exists (NO MATCH), skipping.")

		except (FileNotFoundError):

			amm = AlienMatcherModel(
				tool=Tool(__name__, Settings.VERSION),
				aliensrc=AlienSrc(
					apkg.name,
					apkg.version.str,
					apkg.alternative_names,
					apkg.internal_archive_name,
					apkg.archive_name,
					apkg.package_files
				)
			)

			try:
				if apkg.has_internal_primary_archive():

					match, package_score, version_score = self.search(apkg)

					# It will use the cache, but we need the package also if the
					# SPDX was already generated from the Debian sources.
					debpkg = self.fetch_debian_sources(match)

					amm.debian.match = DebianMatch(
						debpkg.name,
						debpkg.version.str,
						Calc.overallScore(package_score, version_score),
						package_score,
						version_score,
						debpkg.debsrc_debian,
						debpkg.debsrc_orig,
						debpkg.format,
						[
							VersionCandidate(c[0].str, c[1], c[2])
							for c in self.candidate_list
						]
					)

			except AlienMatcherError as ex:
				errors.append(str(ex))

			amm.errors = errors
			self.pool.write_json(amm, resultpath)
			logger.debug(f"[{self.curpkg}] Result written to {resultpath}.")
		return amm

	def run(self, package_path: str) -> Optional[AlienMatcherModel]:
		try:
			filename = os.path.basename(package_path)
			package = AlienPackage(package_path)
			self.curpkg = f"{package.name}-{package.version.str}"
			logger.info(f"[{self.curpkg}] Processing {filename}...")
			package.expand()
			amm = self.match(package)

			debsrc_debian = amm.debian.match.debsrc_debian
			debsrc_debian = os.path.basename(debsrc_debian) if debsrc_debian else ''

			debsrc_orig = amm.debian.match.debsrc_orig
			debsrc_orig = os.path.basename(debsrc_orig) if debsrc_orig else ''

			outcome = 'MATCH' if debsrc_debian or debsrc_orig else 'NO MATCH'
			if not debsrc_debian and not debsrc_orig and not amm.errors:
				amm.errors = 'NO MATCH without errors'
			logger.info(
				f"[{self.curpkg}] {outcome}:"
				f" {debsrc_debian} {debsrc_orig} {'; '.join(amm.errors)}"
			)
			return amm
		except PackageError as ex:
			logger.error(f"[{self.curpkg}] ERROR: {ex}")
			return None

	@staticmethod
	def execute(glob_name: str = "*", glob_version: str = "*") -> None:
		global DEB_ALL_SOURCES
		DEB_ALL_SOURCES = AlienMatcher.get_deb_all_sources()
		pool = Pool(Settings.POOLPATH)
		multiprocessing_pool = MultiProcessingPool()
		results = multiprocessing_pool.map( # pytype: disable=wrong-arg-types
			AlienMatcher._execute,
			pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc")
		)
		if Settings.PRINTRESULT:
			for match in results:
				if match:
					print(match.to_json())
		if not results:
			logger.info(
				f"Nothing found for packages '{glob_name}' with versions '{glob_version}'. "
				f"Have you executed 'add' for these packages?"
			)

	@staticmethod
	def _execute(path: str) -> Optional[AlienMatcherModel]:
		return AlienMatcher().run(path)
