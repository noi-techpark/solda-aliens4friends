# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
from posixpath import relpath

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import FILETYPE, Pool, SRCTYPE, OVERWRITE, PoolErrorFileExists
from aliens4friends.commons.settings import Settings

from aliens4friends.models.tinfoilhat import TinfoilHatModel
from aliens4friends.commons.session import Session, SessionError
from aliens4friends.models.session import SessionPackageModel

from aliens4friends.commons.utils import get_prefix_formatted, log_minimal_error

logger = logging.getLogger(__name__)

class AddError(Exception):
	pass

class Add:
	"""
    Add packages or result files from another Aliens4Friends pool to this pool
	structure. Depending of the internal data of each input artifact we
	calculate the correct position inside the pool's userland repository.
	"""

	def __init__(self, pool: Pool, session_id: str) -> None:
		super().__init__()
		self.pool = pool
		self.session_list_aliensrc = []
		self.session_list_tinfoilhat = []
		self.session = None

		# Load a session if possible, or terminate otherwise
		# Error messages are already inside load(), let the
		# caller handle SessionError exceptions
		if session_id:
			self.session = Session(pool, session_id)
			self.session.load()

	def alienpackage(self, path: str, force: bool) -> None:
		alienpackage = AlienPackage(path)
		if not isinstance(alienpackage, AlienPackage):
			raise TypeError("Parameter must be an AlienPackage.")
		alienpackage.expand(check_checksums=True)
		filepath = self.pool.relpath_typed(
			FILETYPE.ALIENSRC,
			alienpackage.name,
			alienpackage.version.str,
			alienpackage.variant,
			with_filename=False
		)
		filename = self.pool.filename(
			FILETYPE.ALIENSRC,
			alienpackage.name,
			alienpackage.version.str,
			alienpackage.variant,
		)
		logger.debug(f"[{alienpackage.name}-{alienpackage.version.str}] Position in pool will be: {filepath}/{filename}")

		try:
			self.pool._add(
				alienpackage.archive_fullpath,
				filepath,
				filename,
				SRCTYPE.PATH,
				overwrite=OVERWRITE.ALWAYS if force else OVERWRITE.RAISE
			)

		except PoolErrorFileExists as ex:
			logger.debug(f"[{alienpackage.name}-{alienpackage.version.str}] Skipping... {ex}")

		# Even if the file exists, we need to have it in the session list
		self.session_list_aliensrc.append(
			SessionPackageModel(
				alienpackage.name,
				alienpackage.version.str,
				alienpackage.variant
			)
		)

	def tinfoilhat(self, path: str) -> None:
		"""add a tinfoilhat file to the pool, splitting it (if it contains
		multiple recipes), and merging it with other possible existing
		tinfoilhat data in the pool
		"""
		tfh = TinfoilHatModel.from_file(path)
		for recipe_name, container in tfh._container.items():
			metadata = container.recipe.metadata
			package_name = metadata.base_name
			package_version = f'{metadata.version}-{metadata.revision}'
			filename = self.pool.filename(FILETYPE.TINFOILHAT, package_name, package_version, metadata.variant)
			filepath = self.pool.relpath_typed(FILETYPE.TINFOILHAT, package_name, package_version, with_filename=False)
			logger.debug(f"[{package_name}-{package_version}] Position in pool will be: {filepath}/{filename}")

			self.pool.merge_json_with_history(
				TinfoilHatModel({recipe_name: container}),
				filename,
				get_prefix_formatted(),
				filepath
			)

			self.session_list_tinfoilhat.append(
				SessionPackageModel(
					package_name,
					package_version,
					metadata.variant
				)
			)

	def write_session_list(self) -> None:

		# Nothing to do, if we do not have started a session...
		if not self.session:
			return

		# Since lists are not hashable, we need a custom duplicate removal here
		exists = set()
		candidates = []
		for c in self.session_list_aliensrc + self.session_list_tinfoilhat:
			if f"{c.name}-{c.version}-{c.variant}" not in exists:
				candidates.append(c)
				exists.add(f"{c.name}-{c.version}-{c.variant}")

		# Now got through all candidates and check each of them has a tinfilhat
		# and aliensrc file, either within the given file list of the ADD command
		# or already stored inside the pool.
		for candidate in candidates:
			if (
				candidate not in self.session_list_aliensrc
				and not self.pool.exists(
					self.pool.relpath_typed(FILETYPE.ALIENSRC,
						candidate.name,
						candidate.version,
						candidate.variant
					)
				)
			):
				candidate.selected = False
				candidate.reason = f"No {FILETYPE.ALIENSRC.value} found"
				continue

			if (
				candidate not in self.session_list_tinfoilhat
				and not self.pool.exists(
					self.pool.relpath_typed(FILETYPE.TINFOILHAT,
						candidate.name,
						candidate.version,
						candidate.variant
					)
				)
			):
				candidate.selected = False
				candidate.reason = f"No {FILETYPE.TINFOILHAT.value} found"

		self.session.write_package_list(candidates)

	@staticmethod
	def execute(file_list, pool: Pool, force: bool, session_id: str) -> None:
		adder = Add(pool, session_id)
		logger.info(f"ADD started with session '{session_id}'.")

		for path in file_list:
			try:
				logger.info(f"ADD {path}")
				if path.endswith(FILETYPE.ALIENSRC):
					adder.alienpackage(path, force)
				elif path.endswith(FILETYPE.TINFOILHAT):
					adder.tinfoilhat(path)
				else:
					raise AddError(f"File {path} is not supported for manual adding!")
			except Exception as ex:
				log_minimal_error(logger, ex, f"{path} --> ")

		adder.write_session_list()
