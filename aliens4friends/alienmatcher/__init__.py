#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Peter Moser <p.moser@noi.bz.it>
#
# Class to match an entry inside a yocto manifest file with debian packages
# libraries through an API, exactly or if not possible find the closest smaller
# version.
#
# Information gathering:
# - Semantic versioning: https://semver.org/
# - Debian versioning: https://readme.phys.ethz.ch/documentation/debian_version_numbers/
#
# APIs used (by example):
# - https://api.ftp-master.debian.org/madison?S&package=busybox
# - https://launchpad.net/debian/+source/base-passwd/3.5.29

import collections as col
import json
import os
import sys
import logging
from urllib.parse import quote as url_encode

from enum import Enum
from typing import Union

import requests
from debian.deb822 import Deb822
from spdx import utils
from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.document import License as SPDXLicense
from spdx.file import File as SPDXFile
from spdx.parsers.loggers import StandardLogger as SPDXWriterLogger
from spdx.parsers.tagvalue import Parser as SPDXTagValueParser
from spdx.parsers.tagvaluebuilders import Builder as SPDXTagValueBuilder
from spdx.writers.tagvalue import write_document

from aliens4friends.commons.archive import Archive, ArchiveError
from aliens4friends.commons.utils import sha1sum, md5, copy
from aliens4friends.commons.package import AlienPackage, Package, PackageError, DebianPackage
from aliens4friends.commons.version import Version
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class AlienMatcherError(Exception):
	pass

class AlienMatcher:

	DEBIAN_BASEURL = "http://deb.debian.org/debian/pool/main"
	API_URL_SRCPKG = "https://api.ftp-master.debian.org/madison?f&a=source&package="
	API_URL_ALLSRC = "https://api.ftp-master.debian.org/all_sources"

	KNOWN_PACKAGE_ALIASES = {
		"wpa-supplicant" : "wpa",
		"linux-yocto" : "linux"
	}

	def __init__(self, pool: Pool):
		super().__init__()
		self.errors = []
		self.pool = pool

		logging.getLogger("urllib3").setLevel(logging.WARNING)

	def _reset(self):
		self.errors = []

	def _api_call(self, url, resp_name):
		api_response_cached = self.pool.abspath(
			Settings.PATH_TMP,
			f"api-resp-{resp_name}.json"
		)
		logger.debug(f"| Search cache pool for existing API response.")
		try:
			response = self.pool.get(api_response_cached)
			logger.debug(f"| API call result found in cache at {api_response_cached}.")
		except FileNotFoundError:
			logger.debug(f"| API call result not found in cache. Making an API call...")
			response = requests.get(url)
			with open(api_response_cached, "w") as f:
				f.write(response.text)
			response = response.text

		return json.loads(response)

	@staticmethod
	def _clean_name(name):
		return name.rstrip("0123456789.~+").replace("-v", "").replace("-", "")

	# XXX Add an edit-distance, since not all similar matches are equally good (Levensthein)
	def _similar_package_name(self, given, new):

		if given == new:
			return 100

		# Rename known packages to their Debian counterpart
		if given in self.KNOWN_PACKAGE_ALIASES:
			given = self.KNOWN_PACKAGE_ALIASES[given]

		if given == new:
			return 95

		g = AlienMatcher._clean_name(given)
		n = AlienMatcher._clean_name(new)

		if n == g:
			return 90

		# Prefixed with the abbreviation isc- (Internet Software Consortium)
		# Possibly postfixed with -client or -server
		if n.startswith(f"isc{g}"):
			return 80

		# Some libraries may lack a lib prefix
		if (
			(g.startswith("lib") or n.startswith("lib"))
			and g.replace("lib", "") == n.replace("lib", "")
		):
			return 70

		# Major Python version mismatch: python3-iniparse vs. python-iniparse
		# Some python packages do not have a python[23]- prefix
		if (
			n.startswith("python3")
			or g.startswith("python3")
		):
			nn = n.replace("python3", "python")
			gg = g.replace("python3", "python")
			if nn == gg:
				return 70
			if nn.replace("python", "") == gg.replace("python", ""):
				return 60

		# Fonts may start with "fonts-" in Debian
		if g.replace("fonts", "") == n.replace("fonts", ""):
			return 60

		# Library/API version at the end of the package name
		if n.startswith(g):
			return 50

		# --> Not matching at all
		return 0

	def search(self, package: Package):
		logger.debug(f"# Search for similar packages with {self.API_URL_SRCPKG}.")
		if not isinstance(package, Package):
			raise TypeError("Parameter must be a Package.")

		if package.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			raise AlienMatcherError(
				f"No parseable debian version: {package.version.str}."
			)
		logger.debug(f"| Package version {package.version.str} has a valid Debian versioning format.")

		candidates = []
		json_response = self._api_call(self.API_URL_ALLSRC, "--ALL-SOURCES--")
		if not json_response:
			raise AlienMatcherError(
				f"No API response for package '{package.name}'."
			)
		for pkg in json_response:
			similarity = self._similar_package_name(package.name, pkg["source"])
			if similarity > 0:
				candidates.append([similarity, pkg["source"], pkg["version"]])

		if len(candidates) == 0:
			raise AlienMatcherError(
				f"Can't find a similar package on Debian repos"
			)

		candidates = sorted(candidates, reverse=True)

		cur_package_name = candidates[0][1]
		logger.debug(f"| Package with name {package.name} not found. Trying with {cur_package_name}.")
		if len(candidates) > 0:
			logger.debug(f"| Warning: We have more than one similarily named package for {package.name}: {candidates}.")

		logger.debug(f"| API call result OK. Find nearest neighbor of {cur_package_name}/{package.version.str}.")

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

		best_version = nn1[0] if nn1[1] < nn2[1] else nn2[0]

		if best_version:
			logger.debug(f"| Nearest neighbor on Debian is {cur_package_name}/{best_version.str}.")
		else:
			logger.debug(f"| Found no neighbor on Debian.")

		return Package(name = cur_package_name, version = best_version)

	def download_to_debian(self, package_name, package_version, filename):
		logger.debug(f"# Retrieving file from Debian: '{package_name}/{package_version}/{filename}'.")
		try:
			response = self.pool.get_binary(Settings.PATH_DEB, package_name, package_version, filename)
			logger.debug(f"| Found in Debian cache pool.")
		except FileNotFoundError:
			pooldir = package_name[0:4] if package_name.startswith('lib') else package_name[0]
			full_url = "/".join([
				self.DEBIAN_BASEURL,
				pooldir,
				package_name,
				filename
			])
			logger.debug(f"| Not found in Debian cache pool. Downloading from {full_url}.")
			r = requests.get(full_url)
			if r.status_code != 200:
				raise AlienMatcherError(f"Error {r.status_code} in downloading {full_url}")
			local_path = self.pool.write(r.content, Settings.PATH_DEB, package_name, package_version, filename)
			logger.debug(f"| Result cached in {local_path}.")
			response = r.content
		return response

	def fetch_debian_sources(self, package: Package):
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

			debian_relpath = self.pool.relpath(Settings.PATH_DEB, package.name, package.version.str, elem[2])

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

	def match(self, apkg: AlienPackage):
		logger.debug("# Find a matching package on Debian repositories.")
		int_arch_count = apkg.internal_archive_count()
		if int_arch_count != 1:
			raise AlienMatcherError(
				f"The Alien Package {apkg.name}/{apkg.version.str} has {int_arch_count} internal archives. " \
				f"We support only single archive packages at the moment!"
			)
		self._reset()
		resultpath = self.pool.abspath(
			Settings.PATH_USR,
			apkg.name,
			apkg.version.str,
			f"{apkg.name}-{apkg.version.str}.alienmatcher.json"
		)
		try:
			if not Settings.POOLCACHED:
				raise FileNotFoundError()
			json_data = self.pool.get_json(resultpath)
			debpkg = DebianPackage(
				json_data["debian"]["match"]["name"],
				json_data["debian"]["match"]["version"],
				json_data["debian"]["match"]["debsrc_orig"],
				json_data["debian"]["match"]["debsrc_debian"],
				json_data["debian"]["match"]["dsc_format"]
			)
			logger.debug("| Result already exists, skipping.")
		except (FileNotFoundError, KeyError):

			json_data = {
				"tool": {
					"name": __name__,
					"version": Settings.VERSION
				},
				"aliensrc": {
					"name": apkg.name,
					"version": apkg.version.str,
					"alternative_names": apkg.alternative_names,
					"internal_archive_name": apkg.internal_archive_name,
					"filename": apkg.archive_name,
					"files": apkg.package_files
				},
				"debian": {
				}
			}

			try:
				if apkg.has_internal_primary_archive():

					match = self.search(apkg)

					# It will use the cache, but we need the package also if the
					# SPDX was already generated from the Debian sources.
					debpkg = self.fetch_debian_sources(match)

					json_data["debian"]["match"] = {
						"name": debpkg.name,
						"version": debpkg.version.str,
						"debsrc_debian": debpkg.debsrc_debian,
						"debsrc_orig": debpkg.debsrc_orig,
						"dsc_format": debpkg.format,
						"version_candidates": [
							{
								"version" : c[0].str,
								"distance": c[1],
								"is_aliensrc": c[2]
							} for c in self.candidate_list
						],
					}
				else:
					self.errors.append("No internal archive")

			except AlienMatcherError as ex:
				self.errors.append(str(ex))

			json_data["errors"] = self.errors
			self.pool.write_json(json_data, resultpath)
			logger.debug(f"| Result written to {resultpath}.")
		return json_data

	def run(self, package_path):
		try:
			filename = os.path.basename(package_path)
			logging.info(f"## Processing {filename}...")
			package = AlienPackage(package_path)
			package.expand()
			match = self.match(package)
			errors = match["errors"]

			try:
				debsrc_debian = match["debian"]["match"]["debsrc_debian"]
				debsrc_debian = os.path.basename(debsrc_debian) if debsrc_debian else ''
			except KeyError:
				debsrc_debian = ""

			try:
				debsrc_orig = match["debian"]["match"]["debsrc_orig"]
				debsrc_orig = os.path.basename(debsrc_orig) if debsrc_orig else ''
			except KeyError:
				debsrc_orig = ""

			outcome = 'MATCH' if debsrc_debian or debsrc_orig else 'NO MATCH'
			if not debsrc_debian and not debsrc_orig and not errors:
				errors = 'FATAL: NO MATCH without errors'
			logging.info(f"{outcome:<10}{debsrc_debian:<60}{debsrc_orig:<60}{errors if errors else ''}")
			return match
		except (AlienMatcherError, PackageError) as ex:
			if str(ex) == "No internal archive":
				logging.warning(f"{'IGNORED':<10}{'':<60}{'':<60}{ex}")
			elif str(ex) == "Can't find a similar package on Debian repos":
				logging.warning(f"{'NO MATCH':<10}{'':<60}{'':<60}{ex}")
			else:
				logging.error(f"{'ERROR':<10}{'':<60}{'':<60}{ex}")
			return None

	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*"):
		matcher = AlienMatcher(pool)
		for p in pool.absglob(f"{glob_name}/{glob_version}/*.aliensrc"):
			result = matcher.run(p)
			if Settings.PRINTRESULT:
				print(json.dumps(result, indent=2))
