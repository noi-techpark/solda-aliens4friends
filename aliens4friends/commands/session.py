# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import json
import logging
import re
from typing import Tuple

from aliens4friends.commands.command import Command, CommandError, Processing
from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.session import Session, SessionError
from aliens4friends.models.alienmatcher import AlienMatcherModel
from aliens4friends.models.session import SessionPackageModel

logger = logging.getLogger(__name__)

class FilterError(Exception):
	pass


def filter_score_gt(
	session: Session,
	pool: Pool,
	package: SessionPackageModel,
	param: str
) -> Tuple[bool, str]:

	try:
		param = int(param)
	except ValueError:
		raise FilterError(f"Parameter must be an integer, '{param}' given.")

	try:
		file_path = pool.abspath_typed(FILETYPE.ALIENMATCHER, package.name, package.version)
		amm = AlienMatcherModel.from_file(file_path)
	except FileNotFoundError:
		reason = f"No {FILETYPE.ALIENMATCHER.value} file found"
		logger.warning(f"[{package.name}] {reason}")
		return False, reason

	if amm.match.score > param:
		return False, f"Exclude: score > {param}"

	return True, f"Include: score <= {param}"

def filter_include_exclude(
	session: Session,
	pool: Pool,
	package: SessionPackageModel,
	param: str
) -> Tuple[bool, str]:
	try:
		with open(param) as fp:
			j = json.load(fp)
	except FileNotFoundError as x:
		raise FilterError(f"File '{param}' not found.")

	if 'include' in j:
		for pattern in j['include']:
			if re.match(pattern, package.name):
				return True, f"Include: selected with pattern '{pattern}'"

	if 'exclude' in j:
		for pattern in j['exclude']:
			if re.match(pattern, package.name):
				return False, f"Exclude: selected with pattern '{pattern}'"

	# Keep all packages as-is, if they are not inside the include/exclude lists
	return package.selected, package.selected_reason

def filter_only_uploaded(
	session: Session,
	pool: Pool,
	package: SessionPackageModel,
	param: str
) -> Tuple[bool, str]:

	if package.uploaded == True:
		return True, "Include: uploaded in this run"
	return False, "Exclude: not uploaded in this run"


FILTERS = {
	"score-gt": filter_score_gt,
	"include-exclude": filter_include_exclude,
	"only-uploaded": filter_only_uploaded,
}

class SessionCmd(Command):

	def __init__(
		self,
		session_id: str,
		create: bool,
		filter_str: str,
		report: str,
		new: bool,
		lock: str,
		unlock: str,
		glob_name: str,
		glob_version: str
	):
		super().__init__(session_id, processing=Processing.SINGLE)
		self.create = create
		self.filter_str = filter_str
		self.report = report
		self.new = new
		self.lock = lock
		self.unlock = unlock
		self.glob_name = "*" if create and not glob_name else glob_name
		self.glob_version = "*" if create and not glob_version else glob_version

	@staticmethod
	def execute(
		session_id: str = "",
		create: bool = False,
		filter_str: str = "",
		report: str = "",
		new: bool = False,
		lock: str = "",
		unlock: str = "",
		glob_name: str = "",
		glob_version: str = ""
	) -> bool:
		cmd = SessionCmd(session_id, create, filter_str, report, new, lock, unlock, glob_name, glob_version)
		return cmd.exec()

	def run(self, _) -> bool:
		if self.new:
			if not self.session:
				self.session = Session(self.pool)
			self.session.create(write_to_disk=True)
			print(self.session.session_id)
			return True

		if self.create:
			if not self.session:
				self.session = Session(self.pool)

			# Do no write to disk immediately, since "add" will do that nevertheless
			self.session.create(write_to_disk=False)
			self.session.add(self.glob_name, self.glob_version)
			print(self.session.session_id)
			return True

		if self.filter_str:
			filters = []
			for filter in self.filter_str.split(","):
				f = filter.split("=", 1)
				try:
					filters.append(
						{
							"name": f[0],
							"param": f[1] if len(f) == 2 else "",
							"method": FILTERS[f[0]]
						}
					)
				except KeyError:
					logger.error(
						f"Filter with name '{f[0]}' does not exist. Filters are: {', '.join(FILTERS.keys())}"
					)
					return False

			try:
				session_model = self.session.load()

				# We do not remove items, but just mark them as selected
				# or not selected if a filtering reason exists
				for p in session_model.package_list:
					for filter in filters:
						p.selected, p.selected_reason = filter["method"](self.session, self.pool, p, filter["param"])

				self.session.write_package_list()
			except SessionError:
				return  False # we have all error messages inside load(), nothing to do...
			except FilterError as e:
				raise CommandError(f"Filter '{filter['name']}' failed with message: {e}") #pytype: disable=unsupported-operands

		if self.report:
			self.session.generate_report(self.report)

		if self.lock:
			self.session.lock(self.lock)

		if self.unlock:
			self.session.unlock(self.unlock)

		return True
