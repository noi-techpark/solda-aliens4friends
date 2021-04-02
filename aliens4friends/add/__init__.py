import logging

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class AddError(Exception):
	pass

class Add:

	def __init__(self, pool: Pool):
		super().__init__()
		self.pool = pool

	def alienpackage(self, alienpackage: AlienPackage):
		if not isinstance(alienpackage, AlienPackage):
			raise TypeError("Parameter must be a AlienPackage.")
		self.pool.add(
			alienpackage.archive_fullpath,
			Settings.PATH_USR,
			alienpackage.name,
			alienpackage.version.str
		)

	@staticmethod
	def execute(alienpackage_list, pool: Pool):
		adder = Add(pool)
		for path in alienpackage_list:
			try:
				logger.info(f"Adding {path}...")
				pkg = AlienPackage(path)
				adder.alienpackage(pkg)
			except Exception as ex:
				logger.error(f"{path} --> {ex.__class__.__name__}: {ex}")
