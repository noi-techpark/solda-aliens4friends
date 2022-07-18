# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import csv
import logging
import os
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

		session_id = Session._clean_identifier(session_id, "session_id")

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
		if not self.is_accessible():
			error = f"Session '{self.session_id}' is not accessible. Locked by another pipeline."
			logger.error(error)
			raise SessionError(error)

		self.pool._add(
			self.session_model,
			Settings.PATH_SES,
			self.pool.filename(FILETYPE.SESSION, self.session_id),
			SRCTYPE.JSON,
			OVERWRITE.ALWAYS
		)
		logger.debug(f"Session data written to '{self.file_path}'.")


	def lock(self, force: Optional[bool] = False):

		lock_key = self.get_lock_key()

		if not lock_key:
			raise SessionError(
				f"Session '{self.session_id}' cannot be locked without a lock key. Set the env-var A4F_LOCK_KEY."
			)

		lock = self.get_lock()

		if lock == lock_key:
			logger.info(f"Session '{self.session_id}' already locked with this lock key '{lock}'. Skipping.")
			return

		if lock and not force:
			raise SessionError(
				f"Session '{self.session_id}' already locked with lock key '{lock}', unlock it first or force-lock it."
			)

		self.pool._add(
			bytes(lock_key, 'utf-8'),
			Settings.PATH_SES,
			self.pool.filename(FILETYPE.SESSION_LOCK, self.session_id),
			SRCTYPE.TEXT,
			OVERWRITE.ALWAYS if force else OVERWRITE.RAISE
		)
		forcetxt = f" Forced!" if force else ""
		logger.info(f"Locking session '{self.session_id}' with lock key '{lock_key}'.{forcetxt}")

	def unlock(self, force: Optional[bool] = False):
		cur_lock = self.get_lock()
		if not cur_lock:
			logger.info(f"Session '{self.session_id}' not locked. Unlocking not necessary.")
			return

		if cur_lock == self.get_lock_key() or force:
			self.pool.rm(
				self.pool.relpath_typed(
					FILETYPE.SESSION_LOCK, self.session_id
				)
			)
			forcetxt = f" Forced!" if force else ""
			logger.info(f"Session '{self.session_id}' unlocked.{forcetxt}")
			return

		error = f"Unable to unlock session '{self.session_id}'. Lock keys do not match."
		logger.error(error)
		raise SessionError(error)

	def get_lock(self):
		lock_path = self.pool.relpath_typed(
			FILETYPE.SESSION_LOCK, self.session_id
		)

		try:
			return self.pool.get(lock_path).strip()
		except FileNotFoundError:
			return None

	def get_lock_key(self) -> str:
		lock_key = os.getenv("A4F_LOCK_KEY")
		return Session._clean_identifier(lock_key, "lock_key") if lock_key else ""

	def is_accessible(self):
		"""Is this session currently accessible, that is not locked or with our own lock"""
		cur_lock = self.get_lock()
		return not cur_lock or cur_lock == self.get_lock_key()

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
			w = csv.DictWriter( #pytype: disable=wrong-arg-types
				csvfile,
				fieldnames=report[0].keys(),
				delimiter=',',
				quotechar='"',
				quoting=csv.QUOTE_NONNUMERIC
			)
			w.writeheader()
			for row in report:
				w.writerow(row)

	def add_variants(self):
		self.load()
		to_add = []
		for session_pkg in self.session_model.package_list:
			candidate_group = { FILETYPE.TINFOILHAT: {}, FILETYPE.ALIENSRC: {} }
			for filetype, candidates in candidate_group.items():
				for path in self.pool.absglob(
					f"{Settings.PATH_USR}/"
					f"{session_pkg.name}/{session_pkg.version}/"
					f"*.{filetype}"
				):
					name, version, variant, _, _ = self.pool.packageinfo_from_path(path)
					candidate_id = f"{name}@{version}-{variant}"
					candidate_pkg = SessionPackageModel(
						name, version, variant,
						selected_reason = "Added variant"
					)
					candidates.update({candidate_id: candidate_pkg})
			for candidate_id, candidate_pkg in candidate_group[FILETYPE.TINFOILHAT].items():
				if candidate_id in candidate_group[FILETYPE.ALIENSRC] and candidate_pkg.variant != session_pkg.variant:
					to_add.append(candidate_pkg)
					logger.info(f"adding variant {candidate_id}")
		self.session_model.package_list += to_add
		logger.info(f"writing session")
		self.write_session()

	@staticmethod
	def _random_string(length: int = 16):
		ranstr = ''
		for _ in range(length):
			ranstr += chr(random.randint(ord('a'), ord('z')))
		return ranstr

	@staticmethod
	def _clean_identifier(identifier: str, error_hint: str = "unknown identifier") -> str:
		if not identifier:
			raise SessionError(f"No {error_hint} given!")
		identifier = identifier.strip().lower()
		pat = re.compile(r"[a-z0-9\-_\.]+")
		if re.fullmatch(pat, identifier):
			return identifier

		raise SessionError(
			f"{error_hint} '{identifier}' is invalid, only the following "
			f"characters are allowed: 'a-z', '0-9', '-', '_', and '.'"
		)
