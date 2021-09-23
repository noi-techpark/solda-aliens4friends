from abc import abstractclassmethod
import logging
from aliens4friends.commons.settings import Settings
from typing import Any, List
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.session import Session
from multiprocessing import Pool as MultiProcessingPool

logger = logging.getLogger(__name__)

class Command:

	def __init__(
		self,
		session_id: str,
		multiprocessing: bool = False
	) -> None:
		super().__init__()
		self.pool = Pool(Settings.POOLPATH)
		self.session = None
		self.multiprocessing = multiprocessing

		# Load a session if possible, or terminate otherwise
		# Error messages are already inside load(), let the
		# caller handle SessionError exceptions
		if session_id:
			self.session = Session(self.pool, session_id)
			self.session.load(create=True)

	def get_paths(
		self,
		filetype: FILETYPE,
		glob_name: str = "*",
		glob_version: str = "*",
		only_selected: bool = False,
		ignore_variant: bool = False
	) -> List[str]:
		"""
		Return paths from packages of the current session or, without a
		session, take information directly from the pool
		"""

		if self.session:
			return self.session.package_list_paths(filetype, only_selected, ignore_variant)

		paths = self.pool.absglob(f"{glob_name}/{glob_version}/*.{filetype}")
		candidates = []
		filtered_paths = []
		for path in paths:
			name, version, _, _ = self.pool.packageinfo_from_path(path)
			if ignore_variant:
				package_id = f"{name}:::{version}"
				if package_id in candidates:
					continue
				candidates.append(package_id)
			filtered_paths.append(path)

		return filtered_paths

	@abstractclassmethod
	def run(self, item: Any) -> Any:
		raise NotImplementedError(
			"Implement a run method, that handles each path"
		)

	def exec(
		self,
		input: List[Any]
	) -> bool:

		results = []
		if self.multiprocessing:
			mpool = MultiProcessingPool()
			results = mpool.map(
				self.run,
				input
			)
		else:
			for item in input:
				results.append(self.run(item))

		if results:
			self._print_results(results)
			for r in results:
				if not r:
					return False
		else:
			logger.info(
				f"Nothing found for packages in session '{self.session_id}'. {self._hint()}"
			)

		return True

	def exec_with_paths(
		self,
		filetype: FILETYPE,
		ignore_variant: bool = False
	) -> bool:

		paths = self.get_paths(
			filetype,
			only_selected=True,
			ignore_variant=ignore_variant
		)

		return self.exec(paths)

	def _hint(self) -> str:
		if self.hint():
			return f"Have you executed '{self.hint()}' for these packages?"
		return ""

	def hint(self) -> str:
		return ""

	def _print_results(self, results: Any) -> None:
		if Settings.PRINTRESULT:
			self.print_results(results)

	def print_results(self, results: Any) -> None:
		print(str(results))
