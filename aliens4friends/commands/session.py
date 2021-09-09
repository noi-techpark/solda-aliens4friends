# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import logging

from aliens4friends.commons.session import Session, SessionError
from aliens4friends.commons.pool import Pool, FILETYPE
from aliens4friends.models.session import PackageListModel
from aliens4friends.models.alienmatcher import AlienMatcherModel

logger = logging.getLogger(__name__)

def match_score_gt_80(pool: Pool, package: PackageListModel) -> str:
	try:
		file_path = pool.abspath_typed(FILETYPE.ALIENMATCHER, package.name, package.version)
		amm = AlienMatcherModel.from_file(file_path)
	except FileNotFoundError:
		reason = "No alienmatcher.json file found"
		logger.warning(f"[{package.name}] {reason}")
		return reason

	if amm.debian.match.score > 80:
		return "score > 80"

	return ""

FILTERS = {
	"score-gt-80": match_score_gt_80
}

class SessionCommand:

	@staticmethod
	def execute(pool: Pool, session_id: str = "", create: bool = False, filter_name: str = "") -> None:
		session = Session(pool, session_id)

		if create:
			session.create()
			print(session.session_id)

		if filter_name:

			try:
				filter_method = FILTERS[filter_name]
			except KeyError:
				logger.error(f"Filter with name '{filter_name}' does not exist. Filters are: {', '.join(FILTERS.keys())}")
				return

			try:
				session_model = session.load()

				# We do not remove items, but just mark them as selected
				# or not selected if a filtering reason exists
				for p in session_model.package_list:
					p.reason = filter_method(pool, p)
					p.selected = not p.reason

				session.write_package_list()
			except SessionError:
				pass  # we have all error messages inside load()




