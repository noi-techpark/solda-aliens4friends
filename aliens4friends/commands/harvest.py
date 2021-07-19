# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import json
import logging
import os
import re
import sys
from typing import List, Dict, Any

from datetime import datetime

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.settings import Settings

from aliens4friends.commons.utils import get_prefix_formatted, log_minimal_error

from aliens4friends.models.harvest import (
	HarvestModel,
	SourcePackage,
	Statistics,
	StatisticsFiles,
	StatisticsLicenses,
	AuditFindings,
	BaseModelEncoder,
	License,
	DebianMatchBasic,
	BinaryPackage,
	LicenseFinding,
	Tool,
	aggregate_tags
)
from aliens4friends.models.fossy import FossyModel
from aliens4friends.models.alienmatcher import AlienMatcherModel
from aliens4friends.models.deltacode import DeltaCodeModel
from aliens4friends.models.tinfoilhat import TinfoilHatModel, PackageWithTags, PackageMetaData

logger = logging.getLogger(__name__)

class HarvestException(Exception):
	pass

# FIXME use the new models everywhere in this class!
class Harvest:
	"""
	Go through all files inside the pool and extract useful information to be
	put inside a final report. This report can then be used for example in a
	visual dashboard application to show what has been found.
	"""

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
		package_id_ext : str = Settings.PACKAGE_ID_EXT
	):
		super().__init__()
		self.pool = pool
		self.input_files = sorted(input_files)
		self.result_file = result_file
		self.result = None
		self.package_id_ext = package_id_ext
		self.add_details = add_details
		self.add_missing = add_missing

	@staticmethod
	def _filename_split(path):
		p = str(path).split("/")
		path = os.path.basename(path)
		package_id, mainext = os.path.splitext(path)
		if mainext == ".aliensrc":
			ext = mainext
		else:
			package_id, subext = os.path.splitext(package_id)
			ext = f"{subext}{mainext}"
		if ext not in Harvest.SUPPORTED_FILES:
			raise HarvestException("Unsupported file extension")

		name = p[-3]
		version = p[-2]
		variant = package_id[len(name)+len(version)+2:]

		return name, version, variant, ext

	def _warn_missing_input(self, package: SourcePackage, package_inputs):
		missing = []
		for input_file_type in self.SUPPORTED_FILES:
			if input_file_type not in package_inputs:
				missing.append(input_file_type)
		if missing:
			logger.warning(f'[{package.id}] Package misses the {missing} input files.')
			if self.add_missing:
				package.harvest_info = {
					"missing_input": missing
				}
		else:
			logger.debug(f'[{package.id}] Package does not miss any input files.')


	def readfile(self):
		self.result = HarvestModel(Tool(__name__, Settings.VERSION))
		cur_package_id = None
		cur_package_inputs = []
		cur_package_id_group = None
		cur_package_stats = []
		old_package = None
		source_package = None
		for path in self.input_files:
			try:
				logger.debug(f"Parsing {self.pool.clnpath(path)}... ")
				try:
					name, version, variant, ext = Harvest._filename_split(path)
				except HarvestException as ex:
					if str(ex) == "Unsupported file extension":
						logger.debug(f"File {self.pool.clnpath(path)} is not supported. Skipping...")
						continue
				variant = f"-{variant}" if variant else ""
				package_id = f"{name}-{version}{variant}+{self.package_id_ext}"
				package_id_group = f"{name}-{version}"
				if not cur_package_id_group or package_id_group != cur_package_id_group:
					min_todo = sys.maxsize
					for stats in cur_package_stats:
						if stats.files.audit_to_do < min_todo:
							min_todo = stats.files.audit_to_do

					# Even if we have more than one package with equal audit_to_do counts,
					# we must consider only one.
					already_set = False
					for stats in cur_package_stats:
						if stats.files.audit_to_do == min_todo and not already_set:
							already_set = True
							stats.aggregate = True
						else:
							stats.aggregate = False
					cur_package_id_group = package_id_group
					cur_package_stats = []
				if not cur_package_id or package_id != cur_package_id:
					if cur_package_id:
						self._warn_missing_input(old_package, cur_package_inputs)
					cur_package_id = package_id
					source_package = SourcePackage(package_id)
					self.result.source_packages.append(source_package)
					old_package = source_package
					cur_package_inputs = []
					cur_package_stats.append(source_package.statistics)
				cur_package_inputs.append(ext)
				if ext == ".fossy.json":
					self._parse_fossy_main(path, source_package)
				elif ext == ".tinfoilhat.json":
					self._parse_tinfoilhat_main(path, source_package)
				elif ext == ".alienmatcher.json":
					self._parse_alienmatcher_main(path, source_package)
				elif ext == ".deltacode.json":
					self._parse_deltacode_main(path, source_package)
				elif ext == ".scancode.json":
					self._parse_scancode_main(path, source_package)
				elif ext == ".aliensrc":
					self._parse_aliensrc_main(path, source_package)
			except Exception as ex:
				log_minimal_error(logger, ex, f"{self.pool.clnpath(path)} ")

		if source_package:
			self._warn_missing_input(source_package, cur_package_inputs)

	def write_results(self):
		self.pool.write_json_with_history(
			self.result,
			get_prefix_formatted(),
			self.result_file
		)

	def _parse_aliensrc_main(self, path, source_package: SourcePackage) -> None:
		apkg = AlienPackage(path)
		apkg.calc_provenance()
		source_package.source_files = apkg.package_files
		stats_files = source_package.statistics.files
		stats_files.known_provenance = apkg.known_provenance
		stats_files.unknown_provenance = apkg.unknown_provenance
		stats_files.total = apkg.total

	def _parse_alienmatcher_main(self, path, source_package: SourcePackage) -> None:
		amm = AlienMatcherModel.from_file(path)
		source_package.debian_matching = DebianMatchBasic(
			amm.debian.match.name,
			amm.debian.match.version
		)

	def _parse_scancode_main(self, path, source_package: SourcePackage) -> None:
		with open(path) as f:
			cur = json.load(f)
		files = [f for f in cur['files'] if f['type'] == 'file']
		source_package.statistics.files.upstream_source_total = len(files)

	def _parse_deltacode_main(self, path, source_package: SourcePackage) -> None:
		cur = DeltaCodeModel.from_file(path)
		source_package.debian_matching.ip_matching_files = (
			cur.header.stats.same_files
			+ cur.header.stats.changed_files_with_no_license_and_copyright
			+ cur.header.stats.changed_files_with_same_copyright_and_license
			+ cur.header.stats.changed_files_with_updated_copyright_year_only
		)

	@staticmethod
	def _increment(dict: dict, key: str, val: Any) -> None:
		try:
			dict[key] += val
		except KeyError:
			dict[key] = val

	def _parse_fossy_licenselists(self, cur: List[str]) -> Dict[str, int]:
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

	def _parse_fossy_ordered_licenses(self, licenses: dict) -> List[LicenseFinding]:
		result = [
			LicenseFinding(k, v) for k, v in licenses.items()
		]
		return sorted(result, reverse = True)


	def _parse_fossy_main(self, path, source_package: SourcePackage) -> None:
		cur = FossyModel.from_file(path)
		stat_agents = {}
		stat_conclusions = {}
		for license_finding in cur.licenses:
			# XXX I assume, that these are folder names, so they can be skipped
			if not license_finding.agentFindings and not license_finding.conclusions:
				continue
			cur_stat_agents = self._parse_fossy_licenselists(license_finding.agentFindings)
			for k, v in cur_stat_agents.items():
				Harvest._increment(stat_agents, k, v)
			cur_stat_conclusions = self._parse_fossy_licenselists(license_finding.conclusions)
			for k, v in cur_stat_conclusions.items():
				Harvest._increment(stat_conclusions, k, v)

		# Some response key do not do what they promise...
		# See https://git.ostc-eu.org/playground/fossology/-/blob/dev-packaging/fossywrapper/__init__.py#L565
		audit_total = cur.summary.filesCleared
		not_cleared = cur.summary.filesToBeCleared
		cleared = audit_total - not_cleared
		ml = cur.summary.mainLicense
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

	def _parse_tinfoilhat_packages(self, cur: Dict[str, PackageWithTags]) -> List[BinaryPackage]:
		result = []
		for name, package in cur.items():
			result.append(self._parse_tinfoilhat_package(name, package))
		return result

	def _parse_tinfoilhat_metadata(self, package_metadata: PackageMetaData) -> PackageMetaData:
		SKIP_LIST = [
			"license",
			"compiled_source_dir",
			"revision",
			"version",
			"name"
		]
		result = PackageMetaData()
		for k, v in package_metadata.__dict__.items():
			if k in SKIP_LIST:
				continue
			setattr(result, k, v)
		return result

	def _parse_tinfoilhat_package(self, name: str, cur: PackageWithTags) -> BinaryPackage:
		result = BinaryPackage(
			name,
			cur.package.metadata.version,
			cur.package.metadata.revision,
			cur.tags
		)
		if self.add_details:
			result.metadata = self._parse_tinfoilhat_metadata(cur.package.metadata)
			result.tags = cur.tags
		return result

	def _parse_tinfoilhat_main(self, path, source_package: SourcePackage) -> None:
		cur = TinfoilHatModel.from_file(path)
		cur = cur._container

		for recipe_name, container in cur.items():
			source_package.name = container.recipe.metadata.name
			source_package.version = container.recipe.metadata.version
			source_package.revision = container.recipe.metadata.revision
			source_package.variant = container.recipe.metadata.variant
			source_package.tags = aggregate_tags(container.tags)
			source_package.binary_packages = self._parse_tinfoilhat_packages(container.packages)
			if self.add_details:
				source_package.metadata = self._parse_tinfoilhat_metadata(container.recipe.metadata)

	@staticmethod
	def execute(pool: Pool, add_details, add_missing, glob_name: str = "*", glob_version: str = "*") -> None:

		result_path = pool.relpath(Settings.PATH_STT)
		pool.mkdir(result_path)
		result_file = 'report.harvest.json'
		output = os.path.join(result_path, result_file)

		files = []
		for supp in Harvest.SUPPORTED_FILES:
			for fn in pool.absglob(f"{Settings.PATH_USR}/{glob_name}/{glob_version}/*{supp}"):
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
		logger.info(f'Results written to {pool.clnpath(output)}.')
		if Settings.PRINTRESULT:
			print(json.dumps(tfh.result, indent=2))
