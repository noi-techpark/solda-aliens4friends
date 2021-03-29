import json
import yaml
import logging
import os

from datetime import datetime

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class TinfoilHat2DashboardException(Exception):
	pass

class TinfoilHat2Dashboard:

	def __init__(self, tinfoilhat_yaml : str, result_file : str):
		super().__init__()
		self.inputfile = tinfoilhat_yaml
		self.result_file = result_file
		self.yaml = None
		self.result = {}


	def readfile(self):
		with open(self.inputfile) as f:
			self.yaml = yaml.safe_load(f)
		self.result = TinfoilHat2Dashboard._parse_main(self.yaml)

	def write_results(self):
		with open(self.result_file, "w") as f:
			json.dump(self.result, f, indent=2)

	@staticmethod
	def _parse_packages(cur):
		result = {}
		for name, package in cur.items():
			result[name] = TinfoilHat2Dashboard._parse_package(package)
		return result

	@staticmethod
	def _parse_metadata(cur):
		SKIP_LIST = [
			"license",
			"compiled_source_dir"
		]
		result = {}
		for k, v in cur.items():
			if k in SKIP_LIST:
				continue
			result[k] = v
		return result

	@staticmethod
	def _parse_package(cur):
		return {
			"package": {
				"metadata": TinfoilHat2Dashboard._parse_metadata(cur["package"]["metadata"]),
				# "files": cur["package"]["files"] <-- XXX Re-add it after first MVP
			},
			"tags": cur["tags"]
		}

	@staticmethod
	def _parse_recipe(cur):
		return {
			"metadata": TinfoilHat2Dashboard._parse_metadata(cur["metadata"]),
			"source_files": cur["source_files"]
		}

	@staticmethod
	def _parse_main(cur):
		result = {}
		for recipe_name, main in cur.items():
			result[recipe_name] = {
				"packages": TinfoilHat2Dashboard._parse_packages(main["packages"]),
				"recipe": TinfoilHat2Dashboard._parse_recipe(main["recipe"]),
				"tags": main["tags"]
			}
		return result

	@staticmethod
	def execute(yaml_files):

		if len(yaml_files) > 1:
			raise TinfoilHat2DashboardException(
				"We support currently only a single TinfoildHat YAML input file."
			)

		pool = Pool(Settings.POOLPATH)
		result_path = pool.abspath("stats")

		pool.mkdir(result_path)

		result_file = f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.dashboard.json'

		tfh = TinfoilHat2Dashboard(
			yaml_files[0],
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



