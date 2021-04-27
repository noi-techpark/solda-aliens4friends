# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import logging
import json

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

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

	def alienpackage(self, path: str) -> None:
		alienpackage = AlienPackage(path)
		if not isinstance(alienpackage, AlienPackage):
			raise TypeError("Parameter must be a AlienPackage.")
		self.pool.add(
			alienpackage.archive_fullpath,
			Settings.PATH_USR,
			alienpackage.name,
			alienpackage.version.str
		)

	def tinfoilhat(self, path: str) -> None:
		with open(path, "r") as jsonfile:
			j = json.load(jsonfile)
		recipe_name = next(iter(j))
		recipe = j[recipe_name]["recipe"]
		package_name = recipe["metadata"]["base_name"]
		package_version = f'{recipe["metadata"]["version"]}-{recipe["metadata"]["revision"]}'
		self.pool.add(
			path,
			Settings.PATH_USR,
			package_name,
			package_version
		)

	@staticmethod
	def execute(file_list, pool: Pool) -> None:
		adder = Add(pool)
		for path in file_list:
			try:
				logger.info(f"Adding {path}...")
				if path.endswith(".aliensrc"):
					adder.alienpackage(path)
				elif path.endswith(".tinfoilhat.json"):
					adder.tinfoilhat(path)
				else:
					raise AddError(f"File {path} is not supported for manual adding!")
			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
