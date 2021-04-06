import json
import yaml
import logging
import os
import re

from datetime import datetime

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class HarvestException(Exception):
	pass

class Harvest:

	SUPPORTED_FILES = [
		".fossy.json",
		".tinfoilhat.yml",
		".alienmatcher.json",
		".deltacode.json"
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
		self.yaml = None
		self.result = {}
		self.package_id_ext = package_id_ext
		self.add_details = add_details
		self.add_missing = add_missing

	@staticmethod
	def _filename_split(path):
		path = os.path.basename(path)
		rest, mainext = os.path.splitext(path)
		if rest.endswith(".fossy"):
			ext = f".fossy{mainext}"
			package_id = rest.split(".fossy")[0]
		elif rest.endswith(".tinfoilhat"):
			ext = f".tinfoilhat{mainext}"
			package_id = rest.split(".tinfoilhat")[0]
		elif rest.endswith(".alienmatcher"):
			ext = f".alienmatcher{mainext}"
			package_id = rest.split(".alienmatcher")[0]
		elif rest.endswith(".deltacode"):
			ext = f".deltacode{mainext}"
			package_id = rest.split(".deltacode")[0]
		else:
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
		p_revision = re.compile("^.*-r[0-9]+$", flags=re.IGNORECASE)
		self.result = {
			"tool": {
				"name": __name__,
				"version": Settings.VERSION
			}
		}
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
					package_id = package_id.replace("_", "-")
					if not p_revision.match(package_id):
						package_id += "-r0"
					package_id += f"+{self.package_id_ext}"
					if not cur_package_id or package_id != cur_package_id:
						if cur_package_id:
							self._warn_missing_input(old_package, cur_package_inputs)
						cur_package_id = package_id
						source_package = {
							"id" : package_id
						}
						source_packages.append(source_package)
						old_package = source_package
						cur_package_inputs = []
					cur_package_inputs.append(ext)
					if ext == ".fossy.json":
						self._parse_fossy_main(json.load(f), source_package)
					elif ext == ".tinfoilhat.yml":
						self._parse_tinfoilhat_main(yaml.safe_load(f), source_package)
					elif ext == ".alienmatcher.json":
						self._parse_alienmatcher_main(json.load(f), source_package)
					elif ext == ".deltacode.json":
						self._parse_deltacode_main(json.load(f), source_package)
			except Exception as ex:
				logger.error(f"{self.pool.clnpath(path)} --> {ex.__class__.__name__}: {ex}")

		self._warn_missing_input(source_package, cur_package_inputs)
		self.result["source_packages"] = source_packages

	def write_results(self):
		with open(self.result_file, "w") as f:
			json.dump(self.result, f, indent=2)

	def _parse_alienmatcher_main(self, cur, out):
		try:
			name = cur["debian"]["match"]["name"]
			version = cur["debian"]["match"]["version"]
			Harvest._safe_set(
				out,
				["debian_matching", "name"],
				name
			)
			Harvest._safe_set(
				out,
				["debian_matching", "version"],
				version
			)
		except KeyError:
			pass

	def _parse_deltacode_main(self, cur, out):
		try:
			stats = cur["header"]["stats"]
			matching = (
				stats["same_files"]
				+ stats["moved_files"]
				+ stats["changed_files_with_no_license_and_copyright"]
				+ stats["changed_files_with_same_copyright_and_license"]
				+ stats["changed_files_with_updated_copyright_year_only"]
			)
		except KeyError:
			matching = 0

		Harvest._safe_set(
			out,
			["statistics", "files", "ip_matching_files"],
			matching
		)

	@staticmethod
	def _increment(dict, key, val):
		try:
			dict[key] += val
		except KeyError:
			dict[key] = val

	@staticmethod
	def _safe_set(obj, trace, value):
		pos = obj
		last = trace.pop()
		for step in trace:
			try:
				pos = pos[step]
			except KeyError:
				pos[step] = {}
				pos = pos[step]
		pos[last] = value

	@staticmethod
	def _rename(license_id):
		RENAME = {
			"GPL-1.0" : "GPL-1.0-only",
			"GPL-1.0+" : "GPL-1.0-or-later",
			"GPL-2.0" : "GPL-2.0-only",
			"GPL-2.0+" : "GPL-2.0-or-later",
			"GPL-3.0" : "GPL-3.0-only",
			"GPL-3.0+" : "GPL-3.0-or-later",
			"LGPL-2.0" : "LGPL-2.0-only",
			"LGPL-2.0+" : "LGPL-2.0-or-later",
			"LGPL-2.1" : "LGPL-2.1-only",
			"LGPL-2.1+" : "LGPL-2.1-or-later"
		}
		if isinstance(license_id, str):
			try:
				return RENAME[license_id]
			except KeyError:
				return license_id

		if isinstance(license_id, list):
			result = []
			for lic in license_id:
				result.append(Harvest._rename(lic))
			return result

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
			license_id = Harvest._rename(license_id)
			if license_id in seen:
				continue
			seen.add(license_id)
			Harvest._increment(result, license_id, 1)
		return result

	def _parse_fossy_ordered_licenses(self, list):
		result = [
			{
				"shortname": k,
				"file_count": v
			} for k, v in list.items()
		]
		return sorted(
			result,
			key = (lambda i: (i['file_count'], i['shortname'])),
			reverse = True
		)


	def _parse_fossy_main(self, cur, out):
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
		total = cur["summary"]["filesCleared"]
		not_cleared = cur["summary"]["filesToBeCleared"]
		cleared = total - not_cleared

		out["statistics"] = {
			"files": {
				"audit_total": total,
				"audit_done": cleared,
				"audit_to_do": not_cleared
			},
			"licenses": {
				"license_scanner_findings": self._parse_fossy_ordered_licenses(stat_agents),
				"license_audit_findings": {
					"main_licenses": Harvest._rename(cur["summary"]["mainLicense"].split(",")),
					"all_licenses":	self._parse_fossy_ordered_licenses(stat_conclusions)
				}
			}
		}


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
		result = {
			"name": name,
			"version": cur["package"]["metadata"]["version"],
			"revision": cur["package"]["metadata"]["revision"],
		}
		if self.add_details:
			result["metadata"] = self._parse_tinfoilhat_metadata(cur["package"]["metadata"]),
			result["tags"] = cur["tags"]
		return result

	def _parse_tinfoilhat_source_files(self, cur):
		result = []
		known_provenance = 0
		unknown_provenance = 0
		for fileobj in cur:
			result.append(
				{
					"name": fileobj["relpath"],
					"src_uri": fileobj["src_uri"],
					"sha1": fileobj["sha1"]
				}
			)
			if fileobj["src_uri"].startswith("file:"):
				unknown_provenance += 1
			elif fileobj["src_uri"].startswith("http") or fileobj["src_uri"].startswith("git"):
				known_provenance += 1
		return result, known_provenance, unknown_provenance

	def _parse_tinfoilhat_main(self, cur, out):
		for recipe_name, main in cur.items():
			out["binary_packages"] = self._parse_tinfoilhat_packages(main["packages"]),

			(
				out["source_files"],
				known_provenance,
				unknown_provenance
			) = self._parse_tinfoilhat_source_files(main["recipe"]["source_files"])

			if known_provenance == 1:
				try:
					total = out["statistics"]["files"]["audit_total"]
				except KeyError:
					total = "UNKNOWN (fossy.json missing?)"
				Harvest._safe_set(
					out,
					["statistics", "files", "known_provenance"],
					total
				)
			else:
				raise HarvestException(
					f"Error: We have more than one upstream package" \
					f'inside source_files in package {main["recipe"]["metadata"]["name"]}'
				)
			Harvest._safe_set(
				out,
				["statistics", "files", "unknown_provenance"],
				unknown_provenance
			)
			if isinstance(total, int):
				Harvest._safe_set(
					out,
					["statistics", "files", "audit_total"],
					total + unknown_provenance
				)

				try:
					not_audited = out["statistics"]["files"]["audit_to_do"]
					Harvest._safe_set(
						out,
						["statistics", "files", "audit_to_do"],
						not_audited + unknown_provenance
					)
				except KeyError:
					pass

			out["tags"] = main["tags"]
			out["name"] = main["recipe"]["metadata"]["name"]
			out["version"] = main["recipe"]["metadata"]["version"]
			out["revision"] = main["recipe"]["metadata"]["revision"]

			if self.add_details:
				out["metadata"] = self._parse_tinfoilhat_metadata(main["recipe"]["metadata"])

	@staticmethod
	def execute(pool: Pool, add_details, add_missing, glob_name: str = "*", glob_version: str = "*"):

		result_path = pool.abspath("stats")
		pool.mkdir(result_path)
		result_file = f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.harvest.json'
		output = os.path.join(result_path, result_file)

		files = []
		for supp in Harvest.SUPPORTED_FILES:
			for fn in pool.absglob(f"{glob_name}/{glob_version}/*{supp}"):
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

