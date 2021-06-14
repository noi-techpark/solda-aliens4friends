# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import logging
import json

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import Pool, SRCTYPE, OVERWRITE
from aliens4friends.commons.settings import Settings

from aliens4friends.models.tinfoilhat import TinfoilHatModel

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

	def __init__(self, pool: Pool) -> None:
		super().__init__()
		self.pool = pool

	def alienpackage(self, path: str, force: bool) -> None:
		alienpackage = AlienPackage(path)
		if not isinstance(alienpackage, AlienPackage):
			raise TypeError("Parameter must be an AlienPackage.")
		dir_in_pool = self.pool.relpath(
			Settings.PATH_USR,
			alienpackage.name,
			alienpackage.version.str
		)
		new_filename = f"{alienpackage.name}-{alienpackage.version.str}.aliensrc"

		logger.info(f"Position in pool will be: {dir_in_pool}/{new_filename}")

		self.pool._add(
			alienpackage.archive_fullpath,
			dir_in_pool,
			new_filename,
			SRCTYPE.PATH,
			overwrite=OVERWRITE.ALWAYS if force else OVERWRITE.RAISE
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
			filename = f'{package_name}-{package_version}.tinfoilhat.json'
			self.pool.merge_json_with_history(
				TinfoilHatModel({recipe_name: container}),
				filename,
				get_prefix_formatted(),
				Settings.PATH_USR,
				package_name,
				package_version
			)

	@staticmethod
	def execute(file_list, pool: Pool, force: bool) -> None:
		adder = Add(pool)
		for path in file_list:
			try:
				logger.info(f"Adding {path}...")
				if path.endswith(".aliensrc"):
					adder.alienpackage(path, force)
				elif path.endswith(".tinfoilhat.json"):
					adder.tinfoilhat(path)
				else:
					raise AddError(f"File {path} is not supported for manual adding!")
			except Exception as ex:
				log_minimal_error(logger, ex, f"{path} --> ")
