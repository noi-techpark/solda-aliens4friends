# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging
import os
import tempfile
from typing import Union, List

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.debian2spdx import (Debian2SPDX,
                                                Debian2SPDXException)
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import bash
from aliens4friends.models.alienmatcher import (AlienMatcherModel,
                                                AlienSnapMatcherModel)

logger = logging.getLogger(__name__)

class SpdxDebian(Command):

	def __init__(self, session_id: str, use_oldmatcher: bool):
		super().__init__(session_id, processing=Processing.MULTI)
		self.use_oldmatcher = use_oldmatcher

	def hint(self) -> str:
		return "match/snapmatch"

	@staticmethod
	def execute(
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> bool:
		cmd = SpdxDebian(session_id, use_oldmatcher)
		return cmd.exec_with_paths(
			FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH,
			ignore_variant=True
		)

	def run(self, path: str) -> Union[List[str], bool]:

		name, version, _, _ = self.pool.packageinfo_from_path(path)
		package = f"{name}-{version}"

		try:
			if self.use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception:
			raise CommandError(f"[{package}] Unable to load json from {self.pool.clnpath(path)}.")

		logger.debug(f"[{package}] Files determined through {self.pool.clnpath(path)}")

		match = model.match
		if not match.name:
			logger.info(f"[{package}] no debian match to compare here")
			return True
		if not match.debsrc_orig:
			logger.info(f"[{package}] no debian orig archive to scan here")
			return True

		debian_spdx_filename = self.pool.abspath_typed(FILETYPE.DEBIAN_SPDX, match.name, match.version)

		if self.pool.cached(debian_spdx_filename, debug_prefix=f"[{package}] "):
			return True

		# FIXME Move this logic in the Debian2SPDX class
		if not match.debsrc_orig and match.debsrc_debian:
			# support for debian format 1.0 native
			match.debsrc_orig = match.debsrc_debian
			match.debsrc_debian = None

		debsrc_orig = self.pool.abspath(match.debsrc_orig)
		debsrc_debian = (
			self.pool.abspath(match.debsrc_debian)
			if match.debsrc_debian
			else None # native format, only 1 archive
		)
		if debsrc_debian and '.diff.' in debsrc_debian:
			logger.debug(
				f"[{package}] Debian source format 1.0 (non-native) processing patch"
			)
			tmpdir_obj = tempfile.TemporaryDirectory()
			tmpdir = tmpdir_obj.name
			bash(f"cp {debsrc_debian} {tmpdir}/")
			bash(f"cp {debsrc_orig} {tmpdir}/")
			tmp_debsrc_debian = os.path.join(
				tmpdir,
				os.path.basename(debsrc_debian)
			)
			tmp_debsrc_orig = os.path.join(
				tmpdir,
				os.path.basename(debsrc_orig)
			)
			bash(f"gunzip {tmp_debsrc_debian}")
			tmp_debsrc_patch, _ = os.path.splitext(tmp_debsrc_debian)
			tmp_debsrc_orig_arch = Archive(tmp_debsrc_orig)
			tmp_debsrc_orig_arch.extract_raw(tmpdir)
			rootfolder = os.path.join(tmpdir, tmp_debsrc_orig_arch.rootfolder())
			bash(f"patch -p1 < {tmp_debsrc_patch}", cwd=rootfolder)
			tmp_debsrc_patch_name, _ = os.path.splitext(tmp_debsrc_patch)
			debsrc_debian = os.path.join(
				tmpdir,
				f"{tmp_debsrc_patch_name}.debian.tar.gz"
			)
			bash(f"tar czf {debsrc_debian} debian/", cwd=rootfolder)

		dorig = debsrc_orig or ""
		ddeb = debsrc_debian or ""
		logger.info(f"[{package}] generating spdx from {self.pool.clnpath(dorig)} and {ddeb}")

		try:
			d2s = Debian2SPDX(debsrc_orig, debsrc_debian)
			d2s.generate_SPDX()
			logger.info(f"[{package}] writing spdx to {self.pool.clnpath(debian_spdx_filename)}")
			d2s.write_SPDX(debian_spdx_filename)
			debian_copyright_filename = self.pool.abspath(
				Settings.PATH_DEB,
				match.name,
				match.version,
				f'{match.name}-{match.version}_debian_copyright'
			)
			if os.path.isfile(debian_copyright_filename) and Settings.POOLCACHED:
				logger.debug(f"[{package}] debian/copyright already extracted, skipping")
			else:
				logger.info(f"[{package}] extracting debian/copyright")
				d2s.write_debian_copyright(debian_copyright_filename)
			return([debian_copyright_filename, debian_spdx_filename])
		except Debian2SPDXException as ex:
			logger.warning(f"[{package}] {ex}")
			return True
