# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.models.alienmatcher import AlienMatcherModel, AlienSnapMatcherModel
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


class Scan(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool):
		super().__init__(session_id, processing=Processing.LOOP)
		self.use_oldmatcher = use_oldmatcher
		self.scancode = Scancode(self.pool)

	def hint(self) -> str:
		return "match/snapmatch"

	@staticmethod
	def execute(
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> bool:
		cmd = Scan(session_id, use_oldmatcher)
		return cmd.exec_with_paths(
			FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH,
			ignore_variant=False
		)

	def run(self, args):
		path = args
		name, version, _, _ = self.pool.packageinfo_from_path(path)
		package = f"{name}-{version}"
		result = []

		try:
			if self.use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception as ex:
			raise CommandError(f"[{package}] Unable to load json from {self.pool.clnpath(path)}.")

		logger.debug(f"[{package}] Files determined through {self.pool.clnpath(path)}")

		try:
			to_scan = model.match.debsrc_orig or model.match.debsrc_debian # support for Debian Format 1.0 native
			archive = Archive(self.pool.relpath(to_scan))
			result.append(
				self.scancode.run(archive, model.match.name, model.match.version)
			)
		except KeyError:
			logger.info(f"[{package}] no debian match, no debian package to scan here")
		except TypeError as ex:
			if not to_scan:  #pytype: disable=name-error
				logger.info(f"[{package}] no debian orig archive to scan here")
			else:
				raise CommandError(f"[{package}] {ex}.")

		except Exception as ex:
			raise CommandError(logger, ex, f"[{package}] {ex}.")

		try:
			archive = Archive(
				self.pool.relpath(
					Settings.PATH_USR,
					model.aliensrc.name,
					model.aliensrc.version,
					model.aliensrc.filename
				)
			)
			result_file = self.scancode.run(
				archive,
				model.aliensrc.name,
				model.aliensrc.version,
				os.path.join("files", model.aliensrc.internal_archive_name)
			)
			if result_file and Settings.PRINTRESULT:
				with open(result_file) as r:
					result.append(json.load(r))
		except TypeError as ex:
			if not model.aliensrc.internal_archive_name:
				logger.info(f"[{package}] no internal archive to scan here")
			else:
				raise CommandError(f"[{package}] {ex}.")

		except Exception as ex:
			raise CommandError(f"[{package}] {ex}.")

		return result
