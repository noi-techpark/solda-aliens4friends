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
from aliens4friends.commons.package import AlienPackage, Package, PackageError
from aliens4friends.commons.version import Version
from aliens4friends.commons.pool import Pool

logger = logging.getLogger(__name__)

VERSION = "0.1"

class AlienMatcherError(Exception):
	pass

class AlienMatcher:

	PATH_TMP = "apiresponse"
	PATH_DEB = "debian"
	PATH_USR = "userland"
	DEBIAN_BASEURL = "http://deb.debian.org/debian/pool/main"
	API_URL_SRCPKG = "https://api.ftp-master.debian.org/madison?f&a=source&package="
	API_URL_ALLSRC = "https://api.ftp-master.debian.org/all_sources"

	def __init__(self, path_to_pool):
		logger.debug(f"# Initializing ALIENMATCHER v{VERSION} with cache pool at {path_to_pool}.")
		super().__init__()
		self.pool = Pool(path_to_pool)
		self.debian_path = self.pool.mkdir(self.PATH_DEB)
		self.userland_path = self.pool.mkdir(self.PATH_USR)
		self.tmp_path = self.pool.mkdir(self.PATH_TMP)

		logger.debug(f"| Pool directory structure created:")
		logger.debug(f"|   - Debian Path          : {self.debian_path}")
		logger.debug(f"|   - Userland Path	       : {self.userland_path}")
		logger.debug(f"|   - Temporary Files Path : {self.tmp_path}")

	def add_to_userland(self, alienpackage: AlienPackage):
		if not isinstance(alienpackage, AlienPackage):
			raise TypeError("Parameter must be a AlienPackage.")
		self.pool.add(
			alienpackage.archive_fullpath,
			self.PATH_USR,
			alienpackage.name,
			alienpackage.version.str
		)
		logger.debug(f"| Adding package '{alienpackage.name}/{alienpackage.version.str}' to '{self.PATH_USR}'.")

	def add_to_debian(self, package: Package):
		if not isinstance(package, Package):
			raise TypeError("Parameter must be a Package.")
		self.pool.add(
			package.archive_fullpath,
			self.PATH_DEB,
			package.name,
			package.version
		)
		logger.debug(f"| Adding package '{package.name}/{package.version}' to '{self.PATH_DEB}'.")

	def _api_call(self, url, resp_name):
		api_response_cached = self.pool.subpath(
			self.PATH_TMP,
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

	def _similar_package_name(self, original, package_name):
		# 1) Library/API version at the end of the package name
		if original.startswith(package_name):
			try:
				int(original[len(package_name):])
				return True
			except ValueError:
				pass

		# 2) Prefixed with the abbreviation isc- (Internet Software Consortium)
		#	Possibly postfixed with -client or -server
		if original.startswith(f"isc-{package_name}"):
			return True

		# 3) Sometimes we just have a dash mismatch
		if original.startswith(package_name.replace("-", "")):
			return True

		# x) Not matching
		return False

	def search(self, package: Package):
		logger.debug(f"# Search for similar packages with {self.API_URL_SRCPKG}.")
		if not isinstance(package, Package):
			raise TypeError("Parameter must be a Package.")

		if package.version.has_flag(Version.FLAG_DEB_VERSION_ERROR):
			raise AlienMatcherError(
				f"'{package.name}' has no parseable debian version: {package.version.str}."
			)
		logger.debug(f"| Package version {package.version.str} has a valid Debian versioning format.")
		candidate_list = [
			[package.version, 0, True]
		]

		fallback = False
		renamings = set()
		json_response = self._api_call(self.API_URL_SRCPKG + package.name, package.name)
		if not json_response:
			logger.debug(f"| No API response for package name {package.name}.")
			logger.debug(f"# Fallback search on all source packages:")
			json_response = self._api_call(self.API_URL_ALLSRC, "--ALL-SOURCES--")
			if not json_response:
				logger.debug("| Fallback call did not produce a response.")
				logger.debug(f"+-- FAILURE.")
				return None
			fallback = True
			for key in json_response:
				if self._similar_package_name(key["source"], package.name):
					renamings.add(key["source"])

		if len(renamings) == 0:
			if fallback:
				logger.debug("| Fallback did not find a similar package.")
				logger.debug(f"+-- FAILURE.")
				return None
			else:
				cur_package_name = package.name
		else:
			cur_package_name = renamings.pop()
			logger.debug(f"| Package with name {package.name} not found. Trying with {cur_package_name}.")
			if len(renamings) > 0:
				logger.debug(f"| Warning: We have more than one similarily named package for {package.name}: {renamings}.")
			json_response = self._api_call(self.API_URL_SRCPKG + cur_package_name, cur_package_name)
			if not json_response: # Needed? Could we not simply use the all sources API call for all packages from the start?
				logger.debug(f"| No API response for package name {cur_package_name}. No fallbacks remaining...")
				logger.debug(f"+-- FAILURE.")
				return None

		logger.debug(f"| API call result OK. Find nearest neighbor of {cur_package_name}/{package.version.str}.")

		seen = set()
		j = json_response[0]
		for revision in j[cur_package_name]:
			for vers_str in j[cur_package_name][revision]:
				if vers_str in seen:
					continue
				version = Version(vers_str)
				ver_distance = version.distance(package.version)
				candidate_list.append([version, ver_distance, False])
				seen.add(vers_str)


		candidate_list = sorted(candidate_list, reverse=True)

		i = 0
		for v in candidate_list:
			if v[2] == True:
				break
			i += 1

		# find 2-nearest neighbors and take the one with the smallest distance
		try:
			nn1 = candidate_list[i-1]
		except IndexError:
			nn1 = [None, Version.MAX_DISTANCE]
		try:
			nn2 = candidate_list[i+1]
		except IndexError:
			nn2 = [None, Version.MAX_DISTANCE]

		best_version = nn1[0] if nn1[1] < nn2[1] else nn2[0]

		logger.debug(f"| Nearest neighbor on Debian is {cur_package_name}/{best_version.str}.")

		return Package(name = cur_package_name, version = best_version)

	def download_to_debian(self, package_name, package_version, filename):
		logger.debug(f"# Retrieving file from Debian: '{package_name}/{package_version}/{filename}'.")
		try:
			response = self.pool.get_binary(
				self.PATH_DEB,
				package_name,
				package_version,
				filename
			)
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
			local_path = self.pool.write(
				r.content,
				self.PATH_DEB,
				package_name,
				package_version,
				filename
			)
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

		debsrc_orig = ""
		debsrc_debian = ""
		debian_control = Deb822(dsc_file_content)

		if not debian_control['Format'].startswith('3.0'):
			raise AlienMatcherError(
				f"ERROR: We support only Debian Source Control files of format 3.0 at the moment: {debian_control['Format']} given."
			)

		debian_control_files = []
		for line in debian_control['Checksums-Sha1'].split('\n'):
			elem = line.strip().split()
			if len(elem) != 3:
				continue
			debian_control_files.append(elem)
			self.download_to_debian(package.name, package.version.str, elem[2])
			debian_path = self.pool.subpath(
				self.PATH_DEB,
				package.name,
				package.version.str,
				elem[2]
			)
			chksum = sha1sum(debian_path)
			if chksum != elem[0]:
				raise AlienMatcherError("ERROR: Checksum mismatch")
			try:
				archive = Archive(elem[2])
				if debian_control['Format'] == "3.0 (quilt)":
					if 'debian' in archive.path:
						debsrc_debian = debian_path
					elif 'orig' in archive.path:
						debsrc_orig = debian_path
				elif debian_control['Format'] == "3.0 (native)":
					debsrc_orig = debian_path
					debsrc_debian = None
			except ArchiveError:
				# Ignore if not supported, it is another file and will be handled later
				pass

		return debsrc_debian, debsrc_orig

	def match(self, apkg: AlienPackage, ignore_cache = False):
		logger.debug("# Find a matching package on Debian repositories.")

		self.add_to_userland(apkg)
		match = self.search(apkg)

		if not match:
			return None

		# It will use the cache, but we need the package also if the
		# SPDX was already generated from the Debian sources.
		debsrc_debian, debsrc_orig = self.fetch_debian_sources(match)

		logger.debug(f"| Done. Match found and stored in {debsrc_debian} and {debsrc_orig}.")
		logger.debug(f"+-- SUCCESS.")

		return debsrc_debian, debsrc_orig
