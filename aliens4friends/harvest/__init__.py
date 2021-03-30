import json
import yaml
import logging
import os

from datetime import datetime

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class HarvestException(Exception):
	pass

class Harvest:

	def __init__(self, input_files, result_file : str, package_id_ext : str = "solda21src"):
		super().__init__()
		self.input_files = sorted(input_files)
		self.result_file = result_file
		self.yaml = None
		self.result = {}
		self.package_id_ext = package_id_ext

	@staticmethod
	def _filename_split(path):
		path = os.path.basename(path)
		rest, mainext = os.path.splitext(path)
		if rest.endswith(".summary.fossy"):
			ext = f".summary.fossy{mainext}"
			package_id = rest.split(".summary.fossy")[0]
		elif rest.endswith(".fossy"):
			ext = f".fossy{mainext}"
			package_id = rest.split(".fossy")[0]
		elif rest.endswith(".tinfoilhat"):
			ext = f".tinfoilhat{mainext}"
			package_id = rest.split(".tinfoilhat")[0]
		elif rest.endswith(".alienmatcher"):
			ext = f".alienmatcher{mainext}"
			package_id = rest.split(".alienmatcher")[0]
		return package_id, ext

	def readfile(self):
		self.result = {
			"tool": {
				"name": __name__,
				"version": Settings.VERSION
			}
		}
		source_packages = []
		cur_package_id = None
		for path in self.input_files:
			with open(path) as f:
				logger.debug(f"Parsing {path}... ")

				package_id, ext = Harvest._filename_split(path)
				package_id += f"+{self.package_id_ext}"

				if not cur_package_id or package_id != cur_package_id:
					cur_package_id = package_id
					source_package = {
						"id" : package_id
					}
					source_packages.append(source_package)

				if ext == ".summary.fossy.json":
					Harvest._parse_summary_fossy_main(json.load(f), source_package)
				elif ext == ".fossy.json":
					Harvest._parse_fossy_main(json.load(f), source_package)
				elif ext == ".tinfoilhat.yml":
					Harvest._parse_tinfoilhat_main(yaml.safe_load(f), source_package)
				elif ext == ".alienmatcher.json":
					source_package = Harvest._parse_alienmatcher_main()

				#source_packages.append(source_package)
				# for k,v in source_packages.items():
				# 	if k in self.result:
				# 		raise HarvestException(
				# 			f"Source package with name {k} already exists!"
				# 		)
				# 	self.result[k] = v
		self.result["source_packages"] = source_packages
		# print (json.dumps(result, indent=2))

	def write_results(self):
		with open(self.result_file, "w") as f:
			json.dump(self.result, f, indent=2)

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
	def _parse_summary_fossy_main(cur, out):
		Harvest._safe_set(
			out,
			["statistics", "licenses", "license_audit_findings", "main_licenses"],
			Harvest._rename(cur["mainLicense"].split(","))
		)
		Harvest._safe_set(
			out,
			["statistics", "files", "audited"],
			cur["filesCleared"]
		)
		Harvest._safe_set(
			out,
			["statistics", "files", "not_audited"],
			cur["filesToBeCleared"]
		)

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

	@staticmethod
	def _parse_fossy_licenselists(cur):
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

	@staticmethod
	def _parse_fossy_main(cur, out):
		stat_agents = {}
		stat_conclusions = {}
		file_count = 0
		for fileobj in cur:
			# XXX I assume, that these are folder names, so they can be skipped
			if not fileobj["agentFindings"] and not fileobj["conclusions"]:
				continue
			cur_stat_agents = Harvest._parse_fossy_licenselists(fileobj["agentFindings"])
			for k, v in cur_stat_agents.items():
				Harvest._increment(stat_agents, k, v)
			cur_stat_conclusions = Harvest._parse_fossy_licenselists(fileobj["conclusions"])
			for k, v in cur_stat_conclusions.items():
				Harvest._increment(stat_conclusions, k, v)
			file_count += 1
		out["statistics"] = {
			"files": {
				"total": file_count
			},
			"licenses": {
				"license_scanner_findings": [
					{
						"shortname": k,
						"file_count": v
					} for k, v in stat_agents.items()
				],
				"license_audit_findings": {
					"all_licenses":	[
						{
							"shortname": k,
							"file_count": v
						} for k, v in stat_conclusions.items()
					]
				}
			}
		}


	@staticmethod
	def _parse_tinfoilhat_packages(cur):
		result = []
		for name, package in cur.items():
			result.append(Harvest._parse_tinfoilhat_package(name, package))
		return result

	@staticmethod
	def _parse_tinfoilhat_metadata(cur):
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

	@staticmethod
	def _parse_tinfoilhat_package(name, cur):
		return {
			"name": name,  #FIXME is it the key inside tinfoilhat.yml packages or cur["package"]["metadata"]["name"],
			"version": cur["package"]["metadata"]["version"],
			"revision": cur["package"]["metadata"]["revision"],
			#"metadata": Harvest._parse_tinfoilhat_metadata(cur["package"]["metadata"]),
			#"tags": cur["tags"]
		}

	@staticmethod
	def _parse_tinfoilhat_source_files(cur):
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

	@staticmethod
	def _parse_tinfoilhat_main(cur, out):
		for recipe_name, main in cur.items():
			out["binary_packages"] = Harvest._parse_tinfoilhat_packages(main["packages"]),

			(
				out["source_files"],
				known_provenance,
				unknown_provenance
			) = Harvest._parse_tinfoilhat_source_files(main["recipe"]["source_files"])

			if known_provenance == 1:
				try:
					total = out["statistics"]["files"]["total"]
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
			out["tags"] = main["tags"]
			out["name"] = main["recipe"]["metadata"]["name"]
			out["version"] = main["recipe"]["metadata"]["version"]
			out["revision"] = main["recipe"]["metadata"]["revision"]
			#out["metadata"] = Harvest._parse_tinfoilhat_metadata(main["recipe"]["metadata"])

	@staticmethod
	def execute(files):

		pool = Pool(Settings.POOLPATH)
		result_path = pool.abspath("stats")

		pool.mkdir(result_path)

		result_file = f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.harvest.json'

		tfh = Harvest(
			files,
			os.path.join(
				result_path,
				result_file
			)
		)
		tfh.readfile()

		tfh.write_results()
		logger.info(f'Results written to {result_path}')
		if Settings.PRINTRESULT:
			print(json.dumps(tfh.result, indent=2))

