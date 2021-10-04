# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import itertools
from abc import abstractclassmethod
from enum import IntEnum
from aliens4friends.commons.utils import log_minimal_error
import logging
from aliens4friends.commons.settings import Settings
from typing import Any, List, Union
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.session import Session
from aliens4friends.commons.utils import get_func_arg_names
from multiprocessing import Pool as MultiProcessingPool

logger = logging.getLogger(__name__)

class CommandError(Exception):
	def __init__(self, msg: str, prefix: str = ""):
		super().__init__(msg)
		self.prefix = prefix

class Processing(IntEnum):
	MULTI = 0
	LOOP = 1
	SINGLE = 2

class Command:

	def __init__(
		self,
		session_id: str,
		processing: Processing,
		dryrun: bool = False
	) -> None:
		super().__init__()
		self.pool = Pool(Settings.POOLPATH)
		self.session = None
		self.processing = processing
		self.dryrun = dryrun

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
			filtered_paths.append(str(path))

		return filtered_paths

	def _run(self, args: List[Any]) -> Any:
		"""wrapper for the run() method, which does 2 things:
		- error logging
		- to avoid inconsistencies between LOOP and MULTI processing in argument
		  handling, it takes a single list of arguments as input (which is the
		  only input possible with MULTI processing) and then converts it into a
		  series of arguments for the run() method
		"""
		if self.dryrun:
			classname = self.__class__.__name__.upper()
			run_arg_names = ", ".join(get_func_arg_names(self.__class__.run))
			logger.info(
				f"[DRYRUN] {classname}: calling run({run_arg_names}) with arguments {args}"
			)
			return True
		try:
			return self.run(*args)
		except CommandError as ex:
			log_minimal_error(logger, ex, ex.prefix)
		except Exception as ex:
			log_minimal_error(logger, ex)
		return False

	@abstractclassmethod
	def run(self, *args: Any) -> Any:
		raise NotImplementedError(
			"Implement a run method giving any argument you need"
		)

	def exec(self, *args: Union[List[Any], Any]) -> bool:
		"""execute run() method, through _run() wrapper method, on the cartesian
		product of *args; each arg can be a list of items or a single item of
		whatever type (it will be automatically converted to a list with a
		single item in order to generate the cartesian product)"""

		args = [
			[arg] if not isinstance(arg, list) else arg
			for arg in args
		]

		run_args = list(itertools.product(*args))

		results = []
		if self.processing == Processing.MULTI:
			mpool = MultiProcessingPool()
			results = mpool.map(
				self._run,
				run_args
			)
		elif self.processing == Processing.SINGLE:
			results.append(self._run(run_args))
		elif self.processing == Processing.LOOP:
			for run_arg in run_args:
				results.append(self._run(run_arg))
		else:
			raise CommandError(f"Unknown Processing Type {self.processing}.")

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

	def exec_with_paths(
		self,
		filetype: FILETYPE,
		ignore_variant: bool = False,
		*args: Any
	) -> bool:

		paths = self.get_paths(
			filetype,
			only_selected=True,
			ignore_variant=ignore_variant
		)

		return self.exec(paths, *args)

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
