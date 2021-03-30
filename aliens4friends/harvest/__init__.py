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

	def __init__(self, tinfoilhat_yaml_files, result_file : str):
		super().__init__()
		self.inputfiles = tinfoilhat_yaml_files
		self.result_file = result_file
		self.yaml = None
		self.result = {}


	def readfile(self):
		for path in self.inputfiles:
			with open(path) as f:
				logger.debug(f"Parsing {path}...")
				recipe = Harvest._parse_main(yaml.safe_load(f))
				for k,v in recipe.items():
					if k in self.result:
						raise HarvestException(
							f"Recipe with name {k} already exists!"
						)
					self.result[k] = v

	def write_results(self):
		with open(self.result_file, "w") as f:
			json.dump(self.result, f, indent=2)

	@staticmethod
	def _parse_packages(cur):
		result = {}
		for name, package in cur.items():
			result[name] = Harvest._parse_package(package)
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
				"metadata": Harvest._parse_metadata(cur["package"]["metadata"]),
				# "files": cur["package"]["files"] <-- XXX Re-add it after first MVP
			},
			"tags": cur["tags"]
		}

	@staticmethod
	def _parse_recipe(cur):
		return {
			"metadata": Harvest._parse_metadata(cur["metadata"]),
			"source_files": cur["source_files"]
		}

	@staticmethod
	def _parse_main(cur):
		result = {}
		for recipe_name, main in cur.items():
			result[recipe_name] = {
				"packages": Harvest._parse_packages(main["packages"]),
				"recipe": Harvest._parse_recipe(main["recipe"]),
				"tags": main["tags"]
			}
		return result

	@staticmethod
	def execute(yaml_files):

		pool = Pool(Settings.POOLPATH)
		result_path = pool.abspath("stats")

		pool.mkdir(result_path)

		result_file = f'{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}.dashboard.json'

		tfh = Harvest(
			yaml_files,
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



