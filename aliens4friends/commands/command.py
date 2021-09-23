# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

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
		multiprocessing: bool
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

		logger.info(f"{self.__class__.__name__.upper()}: Start with session '{session_id}'.")

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
	def run(self, *args: Any) -> Any:
		raise NotImplementedError(
			"Implement a run method, that handles each path"
		)

	def exec(
		self,
		*args: List[Any]
	) -> bool:

		cleaned_args = []
		for arg in args:
			if isinstance(arg, list):
				cleaned_args = Command._inputlist_add_list(cleaned_args, arg)
			else:
				cleaned_args = Command._inputlist_add_constant(cleaned_args, arg)

		results = []
		if self.multiprocessing:
			mpool = MultiProcessingPool()
			results = mpool.map(
				self.run,
				[ [i] for i in cleaned_args ]
			)
		else:
			for item in cleaned_args:
				results.append(self.run(item))

		if results:
			self._print_results(results)
			for r in results:
				if not r:
					return False
		else:
			session_info = f" in session '{self.session.session_id}'" if self.session else ""
			logger.info(
				f"{self.__class__.__name__.upper()}:"
				f" Nothing found for packages{session_info}."
				f" {self._hint()}"
			)

		return True

	@staticmethod
	def _inputlist_add_constant(inputlist: List, constant):
		if inputlist and isinstance(inputlist[0], list):
			return [
				[ *l, constant ] for l in inputlist
			]

		return [
			[
				l, constant
			] for l in inputlist
		]

	@staticmethod
	def _inputlist_add_list(inputlist, list2):
		if not inputlist:
			return list2
		return [
			[*l1, l2] for l1 in inputlist for l2 in list2
		]

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
