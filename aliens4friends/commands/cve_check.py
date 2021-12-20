# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>
# SPDX-License-Identifier: Apache-2.0

import os

from typing import Optional

from aliens4friends.commons.settings import Settings
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.cve_check import CveChecker
from aliens4friends.commons.utils import get_prefix_formatted

class CveCheckError(Exception):
	pass

class CveCheck:

	@staticmethod
	def execute(
		product: Optional[str] = None,
		vendor: Optional[str] = None,
		version: Optional[str] = None,
		startfrom: Optional[int] = None,
		harvest_fname: Optional[str] = None
	) -> bool:
		pool = Pool(Settings.POOLPATH)
		if harvest_fname:
			if not harvest_fname.endswith('.json'):
				raise CveCheckError(f"{harvest_fname} is not a json file")
			harvest_path = self.pool.abspath(
				Settings.PATH_STT,
				harvest_fname
			)
			if not os.path.isfile(harvest_path):
				raise CveCheckError("Can't find file '{harvest_path}'")
			if os.path.islink(harvest_path):
				harvest_path = os.readlink(harvest_path)
		config = {
			'product': product,
			'vendor': vendor,
			'version': version,
			'from': startfrom,
			'harvest': harvest_path
		}
		cve_checker = CveChecker(config)
		if harvest_fname:
			cve_harvest = cve_checker.patchHarvest(harvest_path)
			cve_harvest_path = harvest_path.replace('.json', '.cve.json')
			pool.write_json_with_history(
				cve_harvest,
				get_prefix_formatted(),
				cve_harvest_path
			)
			return True
		else
			return cve_checker.run()
