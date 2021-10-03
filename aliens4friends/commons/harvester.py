# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import json
import logging
import sys
from typing import Any, Dict, List, Optional, Union

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import (FILETYPE, Pool,
                                         PoolErrorUnsupportedFiletype)
from aliens4friends.commons.session import Session
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import (get_prefix_formatted,
                                          log_minimal_error)
from aliens4friends.models.alienmatcher import (AlienMatcherModel,
                                                AlienSnapMatcherModel)
from aliens4friends.models.deltacode import DeltaCodeModel
from aliens4friends.models.fossy import FossyModel
from aliens4friends.models.harvest import (AuditFindings, BinaryPackage,
                                           DebianMatchBasic, HarvestModel,
                                           License, LicenseFinding,
                                           SessionState, SourcePackage,
                                           Statistics, StatisticsLicenses,
                                           Tool, aggregate_tags)
from aliens4friends.models.session import SessionPackageModel
from aliens4friends.models.tinfoilhat import PackageWithTags, TinfoilHatModel

logger = logging.getLogger(__name__)

class HarvestException(Exception):
	pass

# FIXME use the new models everywhere in this class!
class Harvester:
	"""
	Go through all files inside the pool and extract useful information to be
	put inside a final report. This report can then be used for example in a
	visual dashboard application to show what has been found.
	"""

	SUPPORTED_FILES = [
		FILETYPE.ALIENSRC,
		FILETYPE.SCANCODE,
		FILETYPE.DELTACODE,
		FILETYPE.FOSSY,
		FILETYPE.TINFOILHAT,

		# We use only one of these dipending on the given execution parameters
		FILETYPE.ALIENMATCHER,
		FILETYPE.SNAPMATCH
	]

	def __init__(
		self,
		pool: Pool,
		input_files: List[str],
		result_file : str,
		add_missing : bool = False,
		use_oldmatcher: bool = False,
		package_id_ext : str = Settings.PACKAGE_ID_EXT,
		session: Optional[Session] = None
	):
		super().__init__()
		self.pool = pool
		self.input_files = sorted(input_files)
		self.result_file = result_file
		self.result = None
		self.package_id_ext = package_id_ext
		self.add_missing = add_missing
		self.use_oldmatcher = use_oldmatcher
		self.session = session

	def _warn_missing_input(self, package: SourcePackage, package_inputs):
		missing = []
		candidates = self.SUPPORTED_FILES.copy()
		if self.use_oldmatcher:
			candidates.remove(FILETYPE.SNAPMATCH)
		else:
			candidates.remove(FILETYPE.ALIENMATCHER)

		for input_file_type in candidates:
			if input_file_type not in package_inputs:
				missing.append(input_file_type.value)
		if missing:
			logger.warning(f'[{package.id}] Package misses the {missing} input files.')
			if self.add_missing:
				package.harvest_info = {
					"missing_input": missing
				}
		else:
			logger.debug(f'[{package.id}] Package does not miss any input files.')

	@staticmethod
	def _create_variant(p: Optional[SessionPackageModel] = None) -> Dict[str, Union[None, SessionState, List]]:
		return {
			"session_state": SessionState(
				p.selected,
				p.selected_reason,
				p.uploaded,
				p.uploaded_reason
			) if p else None,
			"list": []
		}

	def _create_groups(self):
		self.package_groups = {}

		if self.session:
			for p in self.session.session_model.package_list:
				group_id = f"{p.name}-{p.version}"
				if group_id not in self.package_groups:
					self.package_groups[group_id] = {
						"variants": {},
						"scancode": None,
						"deltacode": None,
						"matcher": None
					}
				if p.variant not in self.package_groups[group_id]['variants']:
					self.package_groups[group_id]['variants'][p.variant] = Harvester._create_variant(p)

		for path in self.input_files:

			# We do not need to do much here, we get a missing file list at the end of the
			# harvesting job...
			if not self.pool.exists(path):
				continue

			try:
				logger.debug(f"Parsing {self.pool.clnpath(path)}... ")
				try:
					name, version, variant, ext = self.pool.packageinfo_from_path(path)
				except PoolErrorUnsupportedFiletype:
					logger.debug(f"File {self.pool.clnpath(path)} is not supported. Skipping...")
					continue

				group_id = f"{name}-{version}"

				if group_id not in self.package_groups:
					self.package_groups[group_id] = {
						"variants": {},
						"scancode": None,
						"deltacode": None,
						"matcher": None
					}

				# We already sort either ALIENMATCHER or SNAPMATCH files out,
				# so we do not need to distinguish it here anymore.
				if ext == FILETYPE.ALIENMATCHER or ext == FILETYPE.SNAPMATCH:
					if self.use_oldmatcher:
						model = AlienMatcherModel.from_file(path)
					else:
						model = AlienSnapMatcherModel.from_file(path)
					self.package_groups[group_id]['matcher'] = DebianMatchBasic(
						model.match.name,
						model.match.version
					)
				elif ext == FILETYPE.SCANCODE:
					with open(path) as f:
						sc = json.load(f)
					self.package_groups[group_id]['scancode'] = {
						'upstream_source_total' : sum([1 for f in sc['files'] if f['type'] == 'file'])
					}
				elif ext == FILETYPE.DELTACODE:
					dc = DeltaCodeModel.from_file(path)
					self.package_groups[group_id]['deltacode'] = dc.header.stats
				else:
					if variant not in self.package_groups[group_id]['variants']:
						self.package_groups[group_id]['variants'][variant] = Harvester._create_variant()
					self.package_groups[group_id]['variants'][variant]['list'].append( #pytype: disable=attribute-error
						{
							"ext": ext,
							"path": path
						}
					)
			except Exception as ex:
				log_minimal_error(logger, ex, f"[{self.pool.clnpath(path)}] Grouping: ")

	def _parse_groups(self):
		for group_id, group in self.package_groups.items():
			cur_package_stats = []

			logger.debug(f"[{group_id}] Group has {len(group['variants'])} variants")

			for variant_id, variant in group['variants'].items():

				logger.debug(f"[{group_id}][{variant_id}] Variant has {len(variant['list'])} file infos")

				package_id = f"{group_id}-{variant_id}+{self.package_id_ext}"
				cur_package_inputs = []

				source_package = self._create_source_package(
					package_id,
					group,
					cur_package_inputs,
					variant['session_state']
				)

				self.result.source_packages.append(source_package)
				for fileinfo in variant['list']:
					logger.debug(f"[{group_id}][{variant_id}] Processing {self.pool.clnpath(fileinfo['path'])}...")
					cur_package_inputs.append(fileinfo['ext'])
					if fileinfo['ext'] == FILETYPE.FOSSY:
						self._parse_fossy_main(fileinfo['path'], source_package)
					elif fileinfo['ext'] == FILETYPE.TINFOILHAT:
						self._parse_tinfoilhat_main(fileinfo['path'], source_package)
					elif fileinfo['ext'] == FILETYPE.ALIENSRC:
						self._parse_aliensrc_main(fileinfo['path'], source_package)

				cur_package_stats.append(source_package.statistics)
				self._warn_missing_input(source_package, cur_package_inputs)
				self._set_aggregation_flag(cur_package_stats)

	def readfile(self):
		self.result = HarvestModel(Tool(__name__, Settings.VERSION))
		self._create_groups()
		self._parse_groups()

	def _create_source_package(
		self,
		package_id: str,
		group: Dict[str, Any],
		cur_package_inputs: List[str],
		session_state: SessionState
	) -> SourcePackage:
		source_package = SourcePackage(package_id, session_state=session_state)

		try:
			upstream_source_total = group['scancode']['upstream_source_total']
			cur_package_inputs.append(FILETYPE.SCANCODE.value)
		except TypeError:
			upstream_source_total = 0
		source_package.statistics.files.upstream_source_total = upstream_source_total

		if group['matcher']:
			source_package.debian_matching = group['matcher']
			cur_package_inputs.append(FILETYPE.ALIENMATCHER.value if self.use_oldmatcher else FILETYPE.SNAPMATCH.value)
		else:
			source_package.debian_matching = None

		if group['deltacode']:
			cur_package_inputs.append(FILETYPE.DELTACODE.value)
			source_package.debian_matching.ip_matching_files = (
				group['deltacode'].same_files
				+ group['deltacode'].changed_files_with_no_license_and_copyright
				+ group['deltacode'].changed_files_with_same_copyright_and_license
				+ group['deltacode'].changed_files_with_updated_copyright_year_only
			)

		return source_package


	@staticmethod
	def _set_aggregation_flag(cur_package_stats: List[Statistics]):
		min_todo = sys.maxsize
		for stats in cur_package_stats:
			if stats.files.audit_total > 0:
				min_todo = min(min_todo, stats.files.audit_to_do)

		if min_todo == sys.maxsize:
			min_todo = 0

		# Even if we have more than one package with equal audit_to_do counts,
		# we must consider only one.
		already_set = False
		for stats in cur_package_stats:
			if (
				stats.files.audit_total > 0
				and stats.files.audit_to_do == min_todo
				and not already_set
			):
				already_set = True
				stats.aggregate = True
			else:
				stats.aggregate = False

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
			Harvester._increment(result, license_id, 1)
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
				Harvester._increment(stat_agents, k, v)
			cur_stat_conclusions = self._parse_fossy_licenselists(license_finding.conclusions)
			for k, v in cur_stat_conclusions.items():
				Harvester._increment(stat_conclusions, k, v)

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

	def _parse_tinfoilhat_package(self, name: str, cur: PackageWithTags) -> BinaryPackage:
		result = BinaryPackage(
			name,
			cur.package.metadata.version,
			cur.package.metadata.revision,
			cur.tags
		)
		result.metadata = cur.package.metadata
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
			source_package.metadata = container.recipe.metadata
