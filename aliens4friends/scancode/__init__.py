import os
import logging
import json

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import bash, bash_live
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class ScancodeError(Exception):
	pass

class Scancode:

	def __init__(self, path_to_pool = None, ignore_cache = None):
		super().__init__()
		self.ignore_cache = ignore_cache if isinstance(ignore_cache, bool) else not Settings.POOLCACHED
		self.pool = Pool(path_to_pool) if path_to_pool else Pool(Settings.POOLPATH)

	def _unpack(self, archive : Archive, archive_in_archive : str = None):
		dest = os.path.join(os.path.dirname(archive.path), "__unpacked")
		if self.ignore_cache:
			self.pool.rm(dest)
		self.pool.mkdir(dest)
		if not os.listdir(dest):
			if archive_in_archive:
				logger.debug(
					f"# Extracting archive {archive_in_archive} inside {archive.path} to {dest}"
				)
				archive.in_archive_extract(archive_in_archive, dest)
			else:
				logger.debug(f"# Extracting archive {archive.path} to {dest}")
				archive.extract(dest)
		return dest


	def run(self, archive : Archive, package_name, package_version_str, archive_in_archive = None):

		result_filename = f"{package_name}_{package_version_str}.scancode.json"
		scancode_result = os.path.join(
			os.path.dirname(archive.path),
			result_filename
		)

		if self.ignore_cache:
			self.pool.rm(scancode_result)

		archive_unpacked = self._unpack(archive, archive_in_archive)
		logger.info(f"# Run SCANCODE on {archive_unpacked}... This may take a while!")
		if os.path.exists(scancode_result):
			logger.info(f"| Skipping because result already exists (cache enabled): {scancode_result}")
		else:
			out, err = bash('grep "cpu cores" /proc/cpuinfo | uniq | cut -d" " -f3')
			cores = int(out)
			out, err = bash("cat /proc/meminfo | grep MemTotal | grep -oP '\d+'")
			memory = int(out)
			max_in_mem = int(memory/810) # rule of the thumb to optimize this setting
			try:
				if Settings.SCANCODE_WRAPPER:
					bash_live(
						f"cd {archive_unpacked}" +
						f"&& scancode-wrapper -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json /userland/scanresult.json /userland",
						prefix = "SCANCODE (wrapper)",
						exception = ScancodeError
					)
					# Move scanresults into parent directory
					os.rename(os.path.join(archive_unpacked, "scanresult.json"), scancode_result)
				else:
					bash_live(
						f"scancode -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json {scancode_result} {archive_unpacked} 2>&1",
						prefix = "SCANCODE (native)",
						exception = ScancodeError
					)
			except ScancodeError as ex:
				# ignore scancode scan errors on single files, FIXME upstream?
				if "Some files failed to scan properly" not in str(ex):
					raise ex

		return scancode_result

	@staticmethod
	def execute(alienmatcher_json_list):
		scancode = Scancode()
		pool = scancode.pool

		for path in alienmatcher_json_list:
			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"Unable to load json from {path}.")
				continue

			try:
				m = j["debian"]["match"]
				a = Archive(pool.abspath(m["debsrc_orig"]))
				result = scancode.run(a, m["name"], m["version"])
				if Settings.PRINTRESULT:
					print(result)
			except Exception as ex:
				logger.error(f"{path} --> {ex}")

			try:
				m = j["aliensrc"]
				a = Archive(
					pool.abspath(
						"userland",
						m["name"],
						m["version"],
						m["filename"]
					)
				)
				result = scancode.run(
					a,
					m["name"],
					m["version"],
					os.path.join("files", m["internal_archive_name"])
				)
				if Settings.PRINTRESULT:
					print(json.dumps(json.loads(result), indent=2))
			except Exception as ex:
				logger.error(f"{path} --> {ex}")

