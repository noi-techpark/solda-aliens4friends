# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
import logging
import json
from typing import Optional

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import bash, bash_live
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import log_minimal_error

logger = logging.getLogger(__name__)

class ScancodeError(Exception):
	pass

class Scancode:

	# Type hints for attributes not declared in __init__
	curpkg: str

	def __init__(self, pool: Pool) -> None:
		super().__init__()
		self.pool = pool

	def _unpack(self, archive : Archive, archive_in_archive : str = None) -> str:
		dest = os.path.join(os.path.dirname(archive.path), "__unpacked")
		if not self.pool.cached(dest, is_dir=True):
			if archive_in_archive:
				logger.debug(
					f"[{self.curpkg}] Extracting archive {archive_in_archive} inside {archive.path} to {dest}"
				)
				archive.in_archive_extract(archive_in_archive, dest)
			else:
				logger.debug(f"[{self.curpkg}] Extracting archive {archive.path} to {dest}")
				archive.extract(dest)
		return dest

	def run(self, archive: Archive, package_name: str, package_version_str: str, archive_in_archive: str = None) -> Optional[str]:
		self.curpkg = f"{package_name}-{package_version_str}"
		result_filename = f"{package_name}-{package_version_str}.scancode.json"
		scancode_result = os.path.join(
			os.path.dirname(archive.path),
			result_filename
		)

		if self.pool.cached(scancode_result, f"[{self.curpkg}] "):
			return None

		archive_unpacked_relpath = self._unpack(archive, archive_in_archive)
		self.run_scancode(archive_unpacked_relpath, package_name, package_version_str)

		return scancode_result


	def run_scancode(self, path_in_pool: str, package_name: str, package_version: str) -> str:

		# FIXME should only run once per host machine (during config maybe)
		out, _ = bash('grep "cpu cores" /proc/cpuinfo | uniq | cut -d" " -f3')
		cores = int(out)
		out, _ = bash("cat /proc/meminfo | grep MemTotal | grep -oP '\d+'")
		memory = int(out)
		max_in_mem = int(memory/810) # rule of the thumb to optimize this setting

		scancode_result = os.path.join(
			path_in_pool,
			f"{package_name}-{package_version}.scancode.json"
		)
		scancode_spdx = os.path.join(
			path_in_pool,
			f"{package_name}-{package_version}.scancode.spdx"
		)
		archive_unpacked_abspath = self.pool.abspath(path_in_pool)

		logger.info(f"[{self.curpkg}] Run SCANCODE on {path_in_pool}... This may take a while!")
		try:
			if Settings.SCANCODE_WRAPPER:
				bash_live(
					f"cd {archive_unpacked_abspath}" +
					f"&& {Settings.SCANCODE_COMMAND} -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json /userland/scanresult.json --spdx-tv /userland/scancode.spdx /userland",
					prefix = "SCANCODE (wrapper)",
					exception = ScancodeError
				)
				# Move scanresults into parent directory
				os.rename(os.path.join(archive_unpacked_abspath, "scanresult.json"), scancode_result)
				os.rename(os.path.join(archive_unpacked_abspath, "scancode.spdx"), scancode_spdx)
			else:
				bash_live(
					f"{Settings.SCANCODE_COMMAND} -n {cores} --max-in-memory {max_in_mem} -cli --strip-root --json {scancode_result} --spdx-tv {scancode_spdx} {archive_unpacked_abspath} 2>&1",
					prefix = "SCANCODE (native)",
					exception = ScancodeError
				)
		except ScancodeError as ex:
			# ignore scancode scan errors on single files, FIXME upstream?
			if "Some files failed to scan properly" not in str(ex):
				raise ex



	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*") -> None:
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
				a = Archive(pool.relpath(to_scan))
				result = scancode.run(a, m["name"], m["version"])
				if result and Settings.PRINTRESULT:
					print(result)
			except KeyError:
				logger.warning(f"[{package}] no debian match, no debian package to scan here")
			except TypeError as ex:
				if not to_scan:  #pytype: disable=name-error
					logger.warning(f"[{package}] no debian orig archive to scan here")
				else:
					log_minimal_error(logger, ex, f"[{package}] ")
			except Exception as ex:
				log_minimal_error(logger, ex, f"[{package}] ")

			try:
				m = j["aliensrc"]
				a = Archive(
					pool.relpath(
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
					log_minimal_error(logger, ex, f"[{package}] ")
			except Exception as ex:
				log_minimal_error(logger, ex, f"[{package}] ")
