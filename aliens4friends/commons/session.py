# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import csv
import logging
import random
import re
from typing import Any, Dict, List, Optional

from aliens4friends.commons.pool import FILETYPE, OVERWRITE, SRCTYPE, Pool
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.models.session import SessionModel, SessionPackageModel
from aliens4friends.models.common import Tool

logger = logging.getLogger(__name__)

def csv_truefalse(value: bool) -> str:
	return "x" if value else ""

class SessionError(Exception):
	pass

class Session:

	def __init__(self, pool: Pool, session_id: str = ""):

		self.pool = pool
		self.session_model = None

		session_id = Session._clean_session_id(session_id)

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

	def create(self, write_to_disk: bool = True) -> SessionModel:
		self.session_model = SessionModel(
			Tool(__name__, Settings.VERSION),
			self.session_id
		)
		if write_to_disk:
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

	def get_package(
		self,
		name: str,
		version: str,
		variant: str
	) -> Optional[SessionPackageModel]:
		for pckg in self.session_model.package_list:
			if (
				pckg.name == name
				and pckg.version == version
				and pckg.variant == variant
			):
				return pckg
		return None

	def set_package(
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
		pckg = self.get_package(name, version, variant)
		if pckg:
			pckg.__dict__.update(values)
			return True
		return False

	def add(self, glob_name: str, glob_version: str) -> None:
		tinfoilhat_list = []
		for path in self.pool.absglob(f"{Settings.PATH_USR}/{glob_name}/{glob_version}/*.{FILETYPE.TINFOILHAT}"):
			name, version, variant, _, _ = self.pool.packageinfo_from_path(path)
			tinfoilhat_list.append(SessionPackageModel(name, version, variant))
		aliensrc_list = []
		for path in self.pool.absglob(f"{Settings.PATH_USR}/{glob_name}/{glob_version}/*.{FILETYPE.ALIENSRC}"):
			name, version, variant, _, _ = self.pool.packageinfo_from_path(path)
			aliensrc_list.append(SessionPackageModel(name, version, variant))
		self.write_joined_package_lists(tinfoilhat_list, aliensrc_list)

	def write_package_list(
		self,
		package_list: Optional[List[SessionPackageModel]] = None,
		overwrite: bool = False
	) -> bool:
		if not self.session_model:
			return False

		# We have a new package_list, otherwise we had probably some in-place modifications
		# therefore we should write it down onto disk
		if package_list:
			if overwrite:
				self.session_model.package_list = package_list
			else:
				self.merge_package_lists(package_list)

		self.write_session()

	def merge_package_lists(self, package_list: List[SessionPackageModel]) -> None:
		for pckg in package_list:
			pckg_existing = self.get_package(pckg.name, pckg.version, pckg.variant)
			if pckg_existing:
				pckg_existing.selected = True
				pckg_existing.selected_reason = "Added again"
			else:
				self.session_model.package_list.append(
					SessionPackageModel(pckg.name, pckg.version, pckg.variant)
				)

	def write_joined_package_lists(
		self,
		tinfoilhat_list: List[SessionPackageModel],
		aliensrc_list: List[SessionPackageModel]
	) -> None:
		"""
		Write a package list for all packages that have a tinfoilhat *and*
		aliensrc file, that is join these two lists into one without duplicates.
		If the counterpart of some entries in these two lists cannot be found in
		the other list, we search the pool.

		Args:
			tinfoilhat_list (List[SessionPackageModel]): Some tinfoilhat models
			aliensrc_list (List[SessionPackageModel]): Some aliensrc models
		"""

		# Since lists are not hashable, we need a custom duplicate removal here
		exists = set()
		candidates = []
		for c in aliensrc_list + tinfoilhat_list:
			if f"{c.name}-{c.version}-{c.variant}" not in exists:
				candidates.append(c)
				exists.add(f"{c.name}-{c.version}-{c.variant}")

		# Now got through all candidates and check each of them has a tinfilhat
		# and aliensrc file, either within the given file list of the ADD command
		# or already stored inside the pool.
		for candidate in candidates:
			if (
				candidate not in aliensrc_list
				and not self.pool.exists(
					self.pool.relpath_typed(FILETYPE.ALIENSRC,
						candidate.name,
						candidate.version,
						candidate.variant
					)
				)
			):
				candidate.selected = False
				candidate.selected_reason = f"No {FILETYPE.ALIENSRC.value} found"
				continue

			if (
				candidate not in tinfoilhat_list
				and not self.pool.exists(
					self.pool.relpath_typed(FILETYPE.TINFOILHAT,
						candidate.name,
						candidate.version,
						candidate.variant
					)
				)
			):
				candidate.selected = False
				candidate.selected_reason = f"No {FILETYPE.TINFOILHAT.value} found"

		self.write_package_list(candidates, overwrite=False)

	def generate_report(self, report_filename: str) -> None:
		report = []
		logger.debug("connecting to Fossology")
		fw = FossyWrapper()
		for p in self.session_model.package_list:
			uploadname = f"{p.name}@{p.version}-{p.variant}"
			foldername = ""
			not_scheduled_agents = "all"
			uploaded = False
			scheduled_reportImport = False
			audit = ""
			logger.debug(
				f"checking if {uploadname} has already been uploaded"
			)
			upload = fw.check_already_uploaded(uploadname)
			if upload:
				foldername = upload.foldername
				uploaded = True
				logger.debug(f"checking scheduled agents for {uploadname}")
				not_scheduled_agents = fw.get_not_scheduled_agents(upload)
				logger.debug(f"checking reportImport for {uploadname}")
				scheduled_reportImport = fw.check_already_imported_report(upload)
				logger.debug(f"getting summary for {uploadname}")
				summary = fw.get_summary(upload)
				audit_total = summary["filesCleared"]
				not_cleared = summary["filesToBeCleared"]
				cleared = audit_total - not_cleared
				audit = f"{audit_total} / {cleared} / {not_cleared}"
			report.append({
				"package": uploadname,
				"selected in this session": csv_truefalse(p.selected),
				"selected reason": p.selected_reason,
				"uploaded in this session": csv_truefalse(p.uploaded),
				"uploaded reason": p.uploaded_reason,
				"uploaded": csv_truefalse(uploaded),
				"folder": foldername,
				"not scheduled agents": " ".join(not_scheduled_agents),
				"scheduled reportImport": scheduled_reportImport,
				"audit (total / cleared / not cleared)": audit
			})
		logger.info(f"writing report to {report_filename}")
		with open(report_filename, "w") as csvfile:
			w = csv.DictWriter(
				csvfile,
				fieldnames=report[0].keys(),
				delimiter=',',
				quotechar='"',
				quoting=csv.QUOTE_NONNUMERIC
			)
			w.writeheader()
			for row in report:
				w.writerow(row)


	@staticmethod
	def _random_string(length: int = 16):
		ranstr = ''
		for _ in range(length):
			ranstr += chr(random.randint(ord('a'), ord('z')))
		return ranstr

	@staticmethod
	def _clean_session_id(session_id: str) -> str:
		if not session_id:
			raise SessionError("No session_id given!")
		session_id = session_id.strip().lower()
		pat = re.compile(r"[a-z0-9\-_\.]+")
		if re.fullmatch(pat, session_id):
			return session_id

		raise SessionError(
			f"Session ID '{session_id}' is invalid, only the following "
			f"characters are allowed: 'a-z', '0-9', '-', '_', and '.'"
		)
