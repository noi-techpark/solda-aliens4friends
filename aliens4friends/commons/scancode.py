# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import os
import re
from typing import Optional

from aliens4friends.commons.archive import Archive
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import bash, bash_live

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
		result_filename = f"{package_name}-{package_version_str}.{FILETYPE.SCANCODE}"
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
		#out, _ = bash('grep "cpu cores" /proc/cpuinfo | uniq | cut -d" " -f3')
		out, _ = bash('nproc')
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
