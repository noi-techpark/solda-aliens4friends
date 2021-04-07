import os
import logging
import json

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import bash, bash_live
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class ScancodeError(Exception):
	pass

class Scancode:

	def __init__(self, pool: Pool):
		super().__init__()
		self.pool = pool

	def _unpack(self, archive : Archive, archive_in_archive : str = None):
		dest = os.path.join(os.path.dirname(archive.path), "__unpacked")
		if not Settings.POOLCACHED:
			self.pool.rm(dest)
		self.pool.mkdir(dest)
		if not os.listdir(dest):
			if archive_in_archive:
				logger.debug(
					f"[{self.curpkg}] Extracting archive {archive_in_archive} inside {archive.path} to {dest}"
				)
				archive.in_archive_extract(archive_in_archive, dest)
			else:
				logger.debug(f"[{self.curpkg}] Extracting archive {archive.path} to {dest}")
				archive.extract(dest)
		return dest


	def run(self, archive : Archive, package_name, package_version_str, archive_in_archive = None):
		self.curpkg = f"{package_name}-{package_version_str}"
		result_filename = f"{package_name}-{package_version_str}.scancode.json"
		spdx_filename = f"{package_name}-{package_version_str}.scancode.spdx"
		scancode_result = os.path.join(
			os.path.dirname(archive.path),
			result_filename
		)
		scancode_spdx = os.path.join(
			os.path.dirname(archive.path),
			spdx_filename
		)
		if not Settings.POOLCACHED:
			self.pool.rm(scancode_result)


		if os.path.exists(scancode_result): # FIXME cache controls should be moved to Pool
			logger.debug(f"[{self.curpkg}] Skip {self.pool.clnpath(scancode_result)}. Result exists and cache is enabled.")
			return None
		archive_unpacked = self._unpack(archive, archive_in_archive)

		logger.info(f"[{self.curpkg}] Run SCANCODE on {self.pool.clnpath(archive_unpacked)}... This may take a while!")
		out, err = bash('grep "cpu cores" /proc/cpuinfo | uniq | cut -d" " -f3')
		cores = int(out)
		out, err = bash("cat /proc/meminfo | grep MemTotal | grep -oP '\d+'")
		memory = int(out)
		max_in_mem = int(memory/810) # rule of the thumb to optimize this setting
		try:
			if Settings.SCANCODE_WRAPPER:
				bash_live(
					f"cd {archive_unpacked}" +
					f"&& scancode-wrapper -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json /userland/scanresult.json --spdx-tv /userland/scancode.spdx /userland",
					prefix = "SCANCODE (wrapper)",
					exception = ScancodeError
				)
				# Move scanresults into parent directory
				os.rename(os.path.join(archive_unpacked, "scanresult.json"), scancode_result)
				os.rename(os.path.join(archive_unpacked, "scancode.spdx"), scancode_spdx)
			else:
				bash_live(
					f"scancode -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json {scancode_result} --spdx-tv {scancode_spdx} {archive_unpacked} 2>&1",
					prefix = "SCANCODE (native)",
					exception = ScancodeError
				)
		except ScancodeError as ex:
			# ignore scancode scan errors on single files, FIXME upstream?
			if "Some files failed to scan properly" not in str(ex):
				raise ex

		return scancode_result

	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*"):
		scancode = Scancode(pool)

		for path in pool.absglob(f"{glob_name}/{glob_version}/*.alienmatcher.json"):
			package = f"{path.parts[-3]}-{path.parts[-2]}"

			try:
				with open(path, "r") as jsonfile:
					j = json.load(jsonfile)
			except Exception as ex:
				logger.error(f"[{package}] Unable to load json from {path}.")
				continue

			try:
				m = j["debian"]["match"]
				to_scan = m["debsrc_orig"] or m["debsrc_debian"] # support for Debian Format 1.0 native
				a = Archive(pool.abspath(to_scan))
				result = scancode.run(a, m["name"], m["version"])
				if result and Settings.PRINTRESULT:
					print(result)
			except KeyError:
				logger.warning(f"[{package}] no debian match, no debian package to scan here")
			except TypeError as ex:
				if not to_scan:
					logger.warning(f"[{package}] no debian orig archive to scan here")
				else:
					logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
			except Exception as ex:
				logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")

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
				if result and Settings.PRINTRESULT:
					with open(result) as r:
						print(json.dumps(json.load(r), indent=2))
			except TypeError as ex:
				if not m.get("internal_archive_name"):
					logger.warning(f"[{package}] no internal archive to scan here")
				else:
					logger.error(f"[{package}]  {ex.__class__.__name__}: {ex}")
			except Exception as ex:
				logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
