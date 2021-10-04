# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import random
from typing import Any, Dict, List, Optional

from aliens4friends.commons.pool import FILETYPE, OVERWRITE, SRCTYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.models.session import SessionModel, SessionPackageModel
from aliens4friends.models.common import Tool

logger = logging.getLogger(__name__)

class SessionError(Exception):
	pass

class Session:

	def __init__(self, pool: Pool, session_id: str = ""):

		self.pool = pool
		self.session_model = None

		# Use an existing session ID, or use a predefined one and create relevant
		# files and folders from it. This overwrites existing files...
		if session_id:
			self.session_id = session_id
			self.file_path = pool.relpath_typed(FILETYPE.SESSION, session_id)
		else:
			# Create a new session with random ID. Repeat this until we find a
			# session.json that has not already been taken by a former run.
			while True:
				session_id = Session._random_string()
				file_path = pool.relpath_typed(FILETYPE.SESSION, session_id)
				if not pool.exists(file_path):
					break

			self.file_path = file_path
			self.session_id = session_id

	def write_session(self) -> None:
		self.pool._add(
			self.session_model,
			Settings.PATH_SES,
			self.pool.filename(FILETYPE.SESSION, self.session_id),
			SRCTYPE.JSON,
			OVERWRITE.ALWAYS
		)
		logger.debug(f"Session data written to '{self.file_path}'.")

	def create(self) -> SessionModel:
		self.session_model = SessionModel(
			Tool(__name__, Settings.VERSION),
			self.session_id
		)
		self.write_session()
		return self.session_model

	def load(self, create: bool = False) -> SessionModel:
		# Test immediately if the session exist, to avoid misleading error messages
		try:
			self.session_model = SessionModel.from_file(
				self.pool.abspath_typed(FILETYPE.SESSION, self.session_id)
			)
			return self.session_model
		except FileNotFoundError:
			if create:
				return self.create()

			error = (
				f"Session with ID '{self.session_id}' not found."
				f" Use 'session' to create one..."
			)
			logger.error(error)
			raise SessionError(error)

	def package_list_paths(
		self,
		type: FILETYPE,
		only_selected: bool = True,
		ignore_variant: bool = False
	) -> List[str]:

		return [
			self.pool.abspath_typed(
				type,
				pckg.name,
				pckg.version,
				pckg.variant
			) for pckg in self.session_model.get_package_list(
				only_selected,
				ignore_variant
			)
		]

	def package_list_set(
		self,
		values: Dict[str, Any],
		name: str,
		version: str,
		variant: str
	) -> bool:
		"""
		Update the package list and set all values in a specific package
		identified by name, version, and variant.

		Args:
			values (Dict[str, Any]):
				A mapping defined in <models.session.SessionPackageModel>
			name (str):
				Name of the package
		    version (str):
				Version of the package variant (str): Variant of the package

		Returns:
			bool: True, if a package could be found and updated
		"""
		for pckg in self.session_model.package_list:
			if (
				pckg.name == name
				and pckg.version == version
				and pckg.variant == variant
			):
				pckg.__dict__.update(values)
				return True
		return False

	def write_package_list(
		self,
		package_list: Optional[List[SessionPackageModel]] = None
	) -> bool:
		if not self.session_model:
			return False

		# We have a new package_list, otherwise we had probably some in-place modifications
		# therefore we should write it down onto disk
		if package_list:
			self.session_model.package_list = package_list

		self.write_session()

	@staticmethod
	def _random_string(length: int = 16):
		ranstr = ''
		for _ in range(length):
			ranstr += chr(random.randint(ord('a'), ord('z')))
		return ranstr





