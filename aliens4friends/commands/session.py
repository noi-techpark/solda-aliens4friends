# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging
import json
import re
from typing import Tuple

from aliens4friends.commons.session import Session, SessionError
from aliens4friends.commons.pool import Pool, FILETYPE
from aliens4friends.models.session import SessionPackageModel
from aliens4friends.models.alienmatcher import AlienMatcherModel

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
		raise FilterError(f"Parameter must be a integer, '{param}' given.")

	try:
		file_path = pool.abspath_typed(FILETYPE.ALIENMATCHER, package.name, package.version)
		amm = AlienMatcherModel.from_file(file_path)
	except FileNotFoundError:
		reason = f"No {FILETYPE.ALIENMATCHER.value} file found"
		logger.warning(f"[{package.name}] {reason}")
		return False, reason

	if amm.match.score > param:
		return False, f"score > {param}"

	return True, f"score <= {param}"

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
				return True, f"Included manually with pattern '{pattern}'"

	if 'exclude' in j:
		for pattern in j['exclude']:
			if re.match(pattern, package.name):
				return False, f"Excluded manually with pattern '{pattern}'"

	# Keep all packages as-is, if they are not inside the include/exclude lists
	return package.selected, package.selected_reason

FILTERS = {
	"score-gt": filter_score_gt,
	"include-exclude": filter_include_exclude
}

class SessionCommand:

	@staticmethod
	def execute(pool: Pool, session_id: str = "", create: bool = False, filter_str: str = "") -> None:
		session = Session(pool, session_id)

		if create:
			session.create()
			print(session.session_id)
			return

		if filter_str:
			filters = []
			for filter in filter_str.split(","):
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
					return

			try:
				session_model = session.load()

				# We do not remove items, but just mark them as selected
				# or not selected if a filtering reason exists
				for p in session_model.package_list:
					for filter in filters:
						p.selected, p.selected_reason = filter["method"](session, pool, p, filter["param"])

				session.write_package_list()
			except SessionError:
				return  # we have all error messages inside load(), nothing to do...
			except FilterError as e:
				logger.error(f"Filter '{filter['name']}' failed with message: {e}") #pytype: disable=unsupported-operands
