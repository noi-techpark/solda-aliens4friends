# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import json
import logging
import os
import re

from datetime import datetime

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.settings import Settings

from aliens4friends.models.harvest import (
	Harvest as HarvestModel,
	SourcePackage,
	Statistics,
	StatisticsFiles,
	StatisticsLicenses,
	AuditFindings,
	BaseModelEncoder,
	License,
	DebianMatch,
	BinaryPackage,
	LicenseFinding
)

logger = logging.getLogger(__name__)

class HarvestException(Exception):
	pass

class Harvest:

	SUPPORTED_FILES = [
		".aliensrc",
		".scancode.json",
		".deltacode.json",
		".fossy.json",
		".tinfoilhat.json",
		".alienmatcher.json",
	]

	def __init__(
		self,
		pool: Pool,
		input_files,
		result_file : str,
		add_details : bool = False,
		add_missing : bool = False,
		package_id_ext : str = "solda21src"
	):
		super().__init__()
		self.pool = pool
		self.input_files = sorted(input_files)
		self.result_file = result_file
		self.result = {}
		self.package_id_ext = package_id_ext
		self.add_details = add_details
		self.add_missing = add_missing
		self.result2 = None

	@staticmethod
	def _filename_split(path):
		p = str(path).split("/")
		package_id = f'{p[-3]}-{p[-2]}'
		path = os.path.basename(path)
		rest, mainext = os.path.splitext(path)
		if mainext == ".aliensrc":
			fname = rest
			ext = mainext
		else:
			fname, subext = os.path.splitext(rest)
			ext = f"{subext}{mainext}"
		if ext not in Harvest.SUPPORTED_FILES:
			raise HarvestException("Unsupported file extension")
		return package_id, ext

	def _warn_missing_input(self, package, package_inputs):
		missing = []
		for input_file_type in self.SUPPORTED_FILES:
			if input_file_type not in package_inputs:
				missing.append(input_file_type)
		if missing:
			logger.warning(f'Package {package["id"]} misses the {missing} input files.')
			if self.add_missing:
				package["harvest_info"] = {
					"missing_input": missing
				}
		else:
			logger.debug(f'Package {package["id"]} does not miss any input files.')


	def readfile(self):
		self.result2 = HarvestModel(__name__, Settings.VERSION)
		source_packages = []
		cur_package_id = None
		cur_package_inputs = []
		old_package = None
		for path in self.input_files:
			try:
				with open(path) as f:
					logger.debug(f"Parsing {path}... ")
					try:
						package_id, ext = Harvest._filename_split(path)
					except HarvestException as ex:
						if str(ex) == "Unsupported file extension":
							logger.debug(f"File {path} is not supported. Skipping...")
							continue
					package_id += f"+{self.package_id_ext}"
					if not cur_package_id or package_id != cur_package_id:
						if cur_package_id:
							self._warn_missing_input(old_package, cur_package_inputs)
						cur_package_id = package_id
						source_package = {
							"id" : package_id
						}
						source_package2 = SourcePackage(package_id)
						self.result2.add_source_package(source_package2)
						source_packages.append(source_package)
						old_package = source_package
						cur_package_inputs = []
					cur_package_inputs.append(ext)
					if ext == ".fossy.json":
						self._parse_fossy_main(json.load(f), source_package, source_package2)
					elif ext == ".tinfoilhat.json":
						self._parse_tinfoilhat_main(json.load(f), source_package, source_package2)
					elif ext == ".alienmatcher.json":
						self._parse_alienmatcher_main(json.load(f), source_package, source_package2)
					elif ext == ".deltacode.json":
						self._parse_deltacode_main(json.load(f), source_package, source_package2)
					elif ext == ".scancode.json":
						self._parse_scancode_main(json.load(f), source_package, source_package2)
					elif ext == ".aliensrc":
						self._parse_aliensrc_main(path, source_package, source_package2)
			except Exception as ex:
				logger.error(f"{self.pool.clnpath(path)} --> {ex.__class__.__name__}: {ex}")
				raise ex

		self._warn_missing_input(source_package, cur_package_inputs)
		self.result["source_packages"] = source_packages

	def write_results(self):
		#FIXME Remove this line
		self.result_file = "/home/pemoser/projects/noi/solda/aliens4friends/tmp/test-harvest-out.json"
		with open(self.result_file, "w") as f:
			json.dump(self.result2, f, indent=2, cls=BaseModelEncoder)

	def _parse_aliensrc_main(self, path, out, source_package: SourcePackage):
		apkg = AlienPackage(path)
		files = []
		known_provenance = 0
		unknown_provenance = 0
		for f in apkg.package_files:
			f['src_uri'] = f['src_uri'].split(";")[0] # remove bitbake params
			files.append(f)
			if f["src_uri"].startswith("file:"):
				unknown_provenance += (f['files_in_archive'] or 1)
				# (files_in_archive == False) means that it's no archive, just a single file
			elif f["src_uri"].startswith("http") or f["src_uri"].startswith("git"):
				known_provenance += (f['files_in_archive'] or 1)

		source_package.source_files = files
		stats_files = source_package.statistics.files
		stats_files.known_provenance = known_provenance
		stats_files.unknown_provenance = unknown_provenance
		stats_files.total = known_provenance + unknown_provenance


	def _parse_alienmatcher_main(self, cur, out, source_package: SourcePackage):
		try:
			name = cur["debian"]["match"]["name"]
			version = cur["debian"]["match"]["version"]

			source_package.debian_matching = DebianMatch(name, version)

		except KeyError:
			pass

	def _parse_scancode_main(self, cur, out, source_package: SourcePackage):
		files = [f for f in cur['files'] if f['type'] == 'file']
		source_package.statistics.files.upstream_source_total = len(files)

	def _parse_deltacode_main(self, cur, out, source_package: SourcePackage):
		try:
			stats = cur["header"]["stats"]
			matching = (
				stats["same_files"]
				+ stats["changed_files_with_no_license_and_copyright"]
				+ stats["changed_files_with_same_copyright_and_license"]
				+ stats["changed_files_with_updated_copyright_year_only"]
			)
		except KeyError:
			matching = 0

		source_package.debian_matching.ip_matching_files = matching

	@staticmethod
	def _increment(dict, key, val):
		try:
			dict[key] += val
		except KeyError:
			dict[key] = val

	def _parse_fossy_licenselists(self, cur):
		result = {}
		if not cur:
			return result

		SKIP_LIST = [
			"Dual-license"
		]
		seen = set()
		for license_id in cur:
			if license_id in SKIP_LIST:
				continue
			license_id = License(license_id).encode()
			if license_id in seen:
				continue
			seen.add(license_id)
			Harvest._increment(result, license_id, 1)
		return result

	def _parse_fossy_ordered_licenses(self, list):
		result = [
			LicenseFinding(k, v) for k, v in list.items()
		]
		return sorted(result, reverse = True)


	def _parse_fossy_main(self, cur, out, source_package: SourcePackage):
		stat_agents = {}
		stat_conclusions = {}
		for fileobj in cur["licenses"]:
			# XXX I assume, that these are folder names, so they can be skipped
			if not fileobj["agentFindings"] and not fileobj["conclusions"]:
				continue
			cur_stat_agents = self._parse_fossy_licenselists(fileobj["agentFindings"])
			for k, v in cur_stat_agents.items():
				Harvest._increment(stat_agents, k, v)
			cur_stat_conclusions = self._parse_fossy_licenselists(fileobj["conclusions"])
			for k, v in cur_stat_conclusions.items():
				Harvest._increment(stat_conclusions, k, v)

		# Some response key do not do what they promise...
		# See https://git.ostc-eu.org/playground/fossology/-/blob/dev-packaging/fossywrapper/__init__.py#L565
		audit_total = cur["summary"]["filesCleared"]
		not_cleared = cur["summary"]["filesToBeCleared"]
		cleared = audit_total - not_cleared
		ml = cur["summary"]["mainLicense"]
		main_licenses = list(set(ml.split(","))) if ml else []

		stats = source_package.statistics
		stats_files = stats.files
		stats_files.audit_total = audit_total
		stats_files.audit_to_do = not_cleared
		stats_files.audit_done = cleared
		stats.licenses = StatisticsLicenses(
			self._parse_fossy_ordered_licenses(stat_agents),
			AuditFindings(
				main_licenses,
				self._parse_fossy_ordered_licenses(stat_conclusions)
			)
		)

	def _parse_tinfoilhat_packages(self, cur):
		result = []
		for name, package in cur.items():
			result.append(self._parse_tinfoilhat_package(name, package))
		return result

	def _parse_tinfoilhat_metadata(self, cur):
		SKIP_LIST = [
			"license",
			"compiled_source_dir",
			"revision",
			"version",
			"name"
		]
		result = {}
		for k, v in cur.items():
			if k in SKIP_LIST:
				continue
			result[k] = v
		return result

	def _parse_tinfoilhat_package(self, name, cur):
		result = BinaryPackage(
			name,
			cur["package"]["metadata"]["version"],
			cur["package"]["metadata"]["revision"]
		)
		if self.add_details:
			result.metadata = self._parse_tinfoilhat_metadata(cur["package"]["metadata"])
			result.tags = cur["tags"]
		return result

	def _parse_tinfoilhat_main(self, cur, out, source_package: SourcePackage):
		for recipe_name, main in cur.items():
			out["binary_packages"] = self._parse_tinfoilhat_packages(main["packages"])
			if self.add_details:
				out["metadata"] = self._parse_tinfoilhat_metadata(main["recipe"]["metadata"])
				source_package.metadata = self._parse_tinfoilhat_metadata(main["recipe"]["metadata"])

			source_package.name = main["recipe"]["metadata"]["name"]
			source_package.version = main["recipe"]["metadata"]["version"]
			source_package.revision = main["recipe"]["metadata"]["revision"]
			source_package.tags = main["tags"]

			source_package.binary_packages = self._parse_tinfoilhat_packages(main["packages"])

	@staticmethod
	def execute(pool: Pool, add_details, add_missing, glob_name: str = "*", glob_version: str = "*"):

		result_path = pool.abspath("stats")
		pool.mkdir(result_path)
		result_file = f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.harvest.json'
		output = os.path.join(result_path, result_file)

		files = []
		for supp in Harvest.SUPPORTED_FILES:
			for fn in pool.absglob(f"userland/{glob_name}/{glob_version}/*{supp}"):
				files.append(str(fn))

		tfh = Harvest(
			pool,
			files,
			output,
			add_details,
			add_missing
		)
		tfh.readfile()

		tfh.write_results()
		logger.info(f'Results written to {pool.abspath(output)}.')
		if Settings.PRINTRESULT:
			print(json.dumps(tfh.result, indent=2))
