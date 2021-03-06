# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import json
import logging
import os
from pathlib import Path
from typing import Tuple, Union

import requests
from debian.deb822 import Deb822

from aliens4friends.commons.archive import Archive, ArchiveError
from aliens4friends.commons.calc import Calc
from aliens4friends.commons.package import (AlienPackage, DebianPackage,
                                            Package, PackageError)
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import sha1sum
from aliens4friends.commons.version import Version
from aliens4friends.models.alienmatcher import (AlienMatcherModel, AlienSrc,
                                                DebianMatch, Tool,
                                                VersionCandidate)

logger = logging.getLogger(__name__)


class AlienMatcherError(Exception):
	pass

class AlienMatcher:
	"""
	Class to match an entry inside a yocto manifest file with debian packages
	libraries through an API, exactly or if not possible find the closest
	version.

	Information taken from:
	- Semantic versioning: https://semver.org/
	- Debian versioning: https://readme.phys.ethz.ch/documentation/debian_version_numbers/
	"""

	# Type hints for attributes not declared in __init__
	curpkg: str

	DEBIAN_BASEURL = [
		"http://deb.debian.org/debian/pool/main",
		"http://security.debian.org/debian-security/pool/updates/main",
		"http://deb.debian.org/debian/pool/non-free",
	]
	API_URL_ALLSRC = "https://api.ftp-master.debian.org/all_sources"

	def __init__(self, pool: Pool) -> None:
		self.pool = pool
		self.set_deb_all_sources()
		logging.getLogger("urllib3").setLevel(logging.WARNING)

	def set_deb_all_sources(self) -> None:
		if 'DEB_ALL_SOURCES' in globals():
			return

		api_response_cached = self.pool.relpath(
			Settings.PATH_TMP,
			f"deb_all_sources.json"
		)
		# FIXME add control if cached copy is outdated
		logger.debug(f"Search cache pool for existing API response.")
		try:
			response = self.pool.get_json(api_response_cached)
			logger.debug(f"API call result found in cache at {api_response_cached}.")
		except FileNotFoundError:
			logger.debug(f"API call result not found in cache. Making an API call...")
			response = requests.get(AlienMatcher.API_URL_ALLSRC)
			if response.status_code != 200:
				raise AlienMatcherError(
					f"Cannot get API response, got error {response.status_code}"
					f" from {AlienMatcher.API_URL_ALLSRC}")
			self.pool.write_json(response.text, api_response_cached)
			response = response.text

		global DEB_ALL_SOURCES
		DEB_ALL_SOURCES = json.loads(response)

	def search(self, package: Package) -> Tuple[Package, int, float]:
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

		if best_candidate and best_candidate[0]:
			logger.debug(
				f"[{self.curpkg}] Nearest neighbor on Debian is"
				f" {cur_package_name}/{best_candidate[0].str}."
			)
		else:
			logger.debug(f"[{self.curpkg}] Found no neighbor on Debian.")

		cur_version_score = package.version.similarity(best_candidate[0])
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
					if '.orig.' in archive.path:
						debsrc_orig = debian_relpath
					else: # XXX Assume archives without patterns in name are from Debian
						debsrc_debian = debian_relpath
				elif debian_control['Format'] == "3.0 (quilt)":
					if '.debian.' in archive.path:
						debsrc_debian = debian_relpath
					elif '.orig.' in archive.path:
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

	def match(self, full_archive_path: Union[Path, str]) -> AlienMatcherModel:

		try:
			package = AlienPackage(full_archive_path)
			self.curpkg = f"{package.name}-{package.version.str}"
			logger.info(f"[{self.curpkg}] Processing {package.archive_name}...")
			package.expand()
		except PackageError as ex:
			raise AlienMatcherError(f"[{self.curpkg}] ERROR: {ex}")

		errors = []
		logger.debug(f"[{self.curpkg}] Find a matching package on Debian repositories.")
		int_arch_count = package.internal_archive_count()
		if int_arch_count > 1:
			if package.internal_archive_name:
				logger.info(
					f"[{self.curpkg}] Alien Package has more than one"
					 " internal archive, using just primary archive"
					f" '{package.internal_archive_name}' for comparison"
				)
			else:
				logger.info(
					f"[{package.name}-{package.version.str}] IGNORED: Alien Package has"
					f" {int_arch_count} internal archives and no primary archive."
					 " We support comparison of one archive only at the moment!"
				)
				errors.append(f"{int_arch_count} internal archives and no primary archive")
		elif int_arch_count == 0:
			logger.info(
				f"[{package.name}-{package.version.str}] IGNORED: Alien Package has"
				 " no internal archive, nothing to compare!"
			)
			errors.append("no internal archive")
		resultpath = self.pool.relpath_typed(FILETYPE.ALIENMATCHER, package.name, package.version.str)
		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError()
			json_data = self.pool.get_json(resultpath)
			amm = AlienMatcherModel(**json_data)
			debpkg = DebianPackage(
				amm.match.name,
				amm.match.version,
				amm.match.debsrc_orig,
				amm.match.debsrc_debian,
				amm.match.dsc_format
			)
			logger.debug(f"[{self.curpkg}] Result already exists (MATCH), skipping.")

		except (PackageError):
			logger.debug(f"[{self.curpkg}] Result already exists (NO MATCH), skipping.")

		except (FileNotFoundError):

			amm = AlienMatcherModel(
				tool=Tool(__name__, Settings.VERSION),
				aliensrc=AlienSrc(
					package.name,
					package.version.str,
					package.alternative_names,
					package.internal_archive_name,
					package.archive_name,
					package.package_files
				)
			)

			try:
				if package.has_internal_primary_archive():

					match, package_score, version_score = self.search(package)

					# It will use the cache, but we need the package also if the
					# SPDX was already generated from the Debian sources.
					debpkg = self.fetch_debian_sources(match)

					amm.match = DebianMatch(
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

		debsrc_debian = amm.match.debsrc_debian
		debsrc_debian = os.path.basename(debsrc_debian) if debsrc_debian else ''

		debsrc_orig = amm.match.debsrc_orig
		debsrc_orig = os.path.basename(debsrc_orig) if debsrc_orig else ''

		outcome = 'MATCH' if debsrc_debian or debsrc_orig else 'NO MATCH'
		if not debsrc_debian and not debsrc_orig and not amm.errors:
			amm.errors = 'NO MATCH without errors'
		logger.info(
			f"[{self.curpkg}] {outcome}:"
			f" {debsrc_debian} {debsrc_orig} {'; '.join(amm.errors)}"
		)

		return amm
