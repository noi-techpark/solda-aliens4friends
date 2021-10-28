# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging
import os
from typing import Any, Union

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.scancode2alienspdx import (Debian2AlienSPDX,
                                                       Scancode2AlienSPDX)
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.spdxutils import (fix_spdxtv, parse_spdx_tv,
                                              write_spdx_tv)
from aliens4friends.models.alienmatcher import (AlienMatcherModel,
                                                AlienSnapMatcherModel)
from aliens4friends.models.deltacode import DeltaCodeModel

logger = logging.getLogger(__name__)

class SpdxAlien(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool, dryrun: bool):
		super().__init__(session_id, Processing.MULTI, dryrun)
		self.use_oldmatcher = use_oldmatcher

	def hint(self) -> str:
		return "match/snapmatch"

	@staticmethod
	def execute(
		use_oldmatcher: bool = False,
		session_id: str = "",
		dryrun: bool = False
	) -> bool:
		cmd = SpdxAlien(session_id, use_oldmatcher, dryrun)
		return cmd.exec_with_paths(
			FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH,
			ignore_variant=True
		)

	def run(self, path: str) -> Union[str, bool]:

		name, version, _, _, _ = self.pool.packageinfo_from_path(path)
		package = f"{name}-{version}"

		#FIXME Move this run code to Debian2AlienSPDX
		try:
			if self.use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception:
			raise CommandError(f"[{package}] Unable to load json from {self.pool.clnpath(path)}.")

		if not model.aliensrc.internal_archive_name:
			logger.info(f"[{package}] No internal archive in aliensrc package, skipping")
			return True

		alien = model.aliensrc
		alien_spdx_filename = self.pool.abspath_typed(
			FILETYPE.ALIENSPDX,
			alien.name,
			alien.version,
			filename=alien.internal_archive_name
		)

		if self.pool.cached(alien_spdx_filename, debug_prefix=f"[{package}] "):
			return True

		alien_package_filename = self.pool.abspath(
			Settings.PATH_USR,
			alien.name,
			alien.version,
			alien.filename
		)
		scancode_spdx_filename = self.pool.abspath_typed(FILETYPE.SCANCODE_SPDX, alien.name, alien.version)
		fix_spdxtv(scancode_spdx_filename)
		scancode_spdx, _ = parse_spdx_tv(scancode_spdx_filename)
		alien_package = AlienPackage(alien_package_filename)
		alien_package.expand(get_internal_archive_checksums=True)

		deltacodeng_results_filename = ""
		debian_spdx_filename = ""

		match = model.match

		if match.name:
			deltacodeng_results_filename = self.pool.abspath_typed(FILETYPE.DELTACODE, alien.name, alien.version)
			debian_spdx_filename = self.pool.abspath_typed(FILETYPE.DEBIAN_SPDX, match.name, match.version)

		if (
			os.path.isfile(deltacodeng_results_filename)
			and os.path.isfile(debian_spdx_filename)
		):
			logger.info(f"[{package}] Applying debian spdx to package {alien.name}-{alien.version}")
			fix_spdxtv(debian_spdx_filename)
			debian_spdx, _ = parse_spdx_tv(debian_spdx_filename)
			deltacodeng_results = DeltaCodeModel.from_file(deltacodeng_results_filename)
			d2as = Debian2AlienSPDX(
				scancode_spdx,
				alien_package,
				debian_spdx,
				deltacodeng_results
			)
			d2as.process()
			write_spdx_tv(d2as.alien_spdx, alien_spdx_filename)
		else:
			logger.info(f"[{package}] No debian spdx available, using scancode spdx for package {alien.name}-{alien.version}")
			s2as = Scancode2AlienSPDX(scancode_spdx, alien_package)
			s2as.process()
			write_spdx_tv(s2as.alien_spdx, alien_spdx_filename)

		return alien_spdx_filename
