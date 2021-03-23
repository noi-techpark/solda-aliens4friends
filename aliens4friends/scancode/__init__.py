import os
import logging
import json

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import bash_live
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class ScancodeError(Exception):
	pass

class Scancode:

	def __init__(self, path_to_pool = None, ignore_cache = None):
		super().__init__()
		self.ignore_cache = ignore_cache if isinstance(ignore_cache, bool) else Settings.POOLCACHED
		self.pool = Pool(path_to_pool) if path_to_pool else Pool(Settings.POOLPATH)

	def run(self, archive : Archive, package_name, package_version_str):

		result_path = os.path.dirname(archive.path)
		result_filename = f"{package_name}_{package_version_str}.scancode.json"
		scancode_result = os.path.join(result_path, result_filename)

		if self.ignore_cache:
			self.pool.rm(result_path, "__unpacked")
			self.pool.rm(scancode_result)

		archive_unpacked = self.pool.mkdir(result_path, "__unpacked")
		logger.info(f"# Extract archive and run SCANCODE on {archive_unpacked}... This may take a while!")
		if not os.listdir(archive_unpacked):
			archive.extract(archive_unpacked)
		if os.path.exists(scancode_result):
			logger.info(f"| Skipping because result already exists: {scancode_result}")
		else:
			bash_live(
				f"cd {archive_unpacked} && scancode -n8 -cli --strip-root --json /userland/scanresult.json /userland",
				prefix = "SCANCODE"
			)
			# Move scanresults into parent directory
			os.rename(os.path.join(archive_unpacked, "scanresult.json"), scancode_result)
		return scancode_result

	@staticmethod
	def execute(alienmatcher_json_list):
		scancode = Scancode()

		for path in alienmatcher_json_list:
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
				m = j["debian"]["match"]
				a = Archive(scancode.pool.abspath(m["debsrc_orig"]))
				scancode.run(a, m["name"], m["version"])
			except Exception as ex:
				logger.error(f"{path} --> {ex}")
