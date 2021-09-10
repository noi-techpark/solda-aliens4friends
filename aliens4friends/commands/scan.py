# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

from aliens4friends.commons.session import Session, SessionError
import os
import re
import logging
import json
from typing import Optional

from aliens4friends.commons.pool import FILETYPE, Pool
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

	def run(self, archive: Archive, package_name: str, package_version_str: str, archive_in_archive: Optional[str] = None) -> Optional[str]:
		self.curpkg = f"{package_name}-{package_version_str}"
		result_filename = f"{package_name}-{package_version_str}.scancode.json"
		scancode_result = os.path.join(
			self.pool.clnpath(os.path.dirname(archive.path)),
			result_filename
		)

		if self.pool.cached(scancode_result, debug_prefix=f"[{self.curpkg}] "):
			return None

		archive_unpacked_relpath = self.pool.unpack(
			archive,
			archive_in_archive=archive_in_archive,
			debug_prefix=f"[{self.curpkg}] "
		)
		self.run_scancode(archive_unpacked_relpath, scancode_result)

		return scancode_result


	def run_scancode(self, archive_unpacked_relpath: str, scancode_result: str) -> None:

		# FIXME should only run once per host machine (during config maybe)
		out, _ = bash('grep "cpu cores" /proc/cpuinfo | uniq | cut -d" " -f3')
		cores = int(out)
		out, _ = bash("cat /proc/meminfo | grep MemTotal | grep -oP '\d+'")
		memory = int(out)
		max_in_mem = int(memory/810) # rule of the thumb to optimize this setting

		scancode_result = self.pool.abspath(scancode_result)
		scancode_spdx = re.sub(r'\.json$', '.spdx', scancode_result)
		archive_unpacked_abspath = self.pool.abspath(archive_unpacked_relpath)

		logger.info(f"[{self.curpkg}] Run SCANCODE on {archive_unpacked_relpath}... This may take a while!")
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
			if "Some files failed to scan properly" not in ex.args[1]:
				raise ex



	@staticmethod
	def execute(
		pool: Pool,
		glob_name: str = "*",
		glob_version: str = "*",
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> None:
		scancode = Scancode(pool)

		filetype = FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH

		# Just take packages from the current session list
		# On error just return, error messages are inside load()
		if session_id:
			try:
				session = Session(pool, session_id)
				session.load()
				paths = session.package_list_paths(filetype)
			except SessionError:
				return

		# ...without a session_id, take information directly from the pool
		else:
			paths = pool.absglob(f"{glob_name}/{glob_version}/*.{filetype}")

		found = False
		for path in paths:
			found = True

			name, version = pool.packageinfo_from_path(path)
			package = f"{name}-{version}"

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
						Settings.PATH_USR,
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

		if not found:
			if session_id:
				logger.info(
					f"Nothing found for packages in session '{session_id}'. "
					f"Have you executed 'snapmatch/match -s {session_id}' for these packages?"
				)
			else:
				logger.info(
					f"Nothing found for packages '{glob_name}' with versions '{glob_version}'. "
					f"Have you executed 'snapmatch/match' for these packages?"
				)
