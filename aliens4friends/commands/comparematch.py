# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import logging
import csv
import os

from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commands.command import Command, Processing
from aliens4friends.models.alienmatcher import (
    MatchResults, AlienMatcherModel, AlienSnapMatcherModel
)
from aliens4friends.models.deltacode import DeltaCodeModel

logger = logging.getLogger(__name__)

class CompareMatchResults(Command):

    def __init__(self, session_id: str, dryrun: bool):
        super().__init__(session_id, Processing.LOOP, dryrun)
        self.pkgs = {}

    def run(self, path: str):
        if not os.path.isfile(path):
            logger.debug(f"{path} does not exist, skipping")
            return True
        name, version, _, ext = self.pool.packageinfo_from_path(path)
        pkg_id = f"{name}@{version}"
        if not self.pkgs.get(pkg_id):
            self.pkgs[pkg_id] = MatchResults(
                alien_name=name,
                alien_version=version
            )
        pkg = self.pkgs[pkg_id]
        command = ""
        try:
            if ext == FILETYPE.ALIENMATCHER:
                command = "match"
                amm = AlienMatcherModel.from_file(path)
                match = amm.match
                pkg.match_name = match.name
                pkg.match_version = match.version
                pkg.match_score = match.score
                pkg.match_package_score = match.package_score
                pkg.match_version_score = match.version_score
            elif ext == FILETYPE.SNAPMATCH:
                command = "snapmatch"
                smm = AlienSnapMatcherModel.from_file(path)
                match = smm.match
                pkg.snapmatch_name = match.name
                pkg.snapmatch_version = match.version
                pkg.snapmatch_score = match.score
                pkg.snapmatch_package_score = match.package_score
                pkg.snapmatch_version_score = match.version_score
            elif ext == FILETYPE.DELTACODE:
                command = "delta"
                dcm = DeltaCodeModel.from_file(path)
                proximity = dcm.header.stats.calc_proximity()
                pkg.deltacode_proximity = round(proximity, 3) * 100
        except FileNotFoundError:
            logger.error(f"{path} not found: have you run '{command}'?")
            return False
        logger.debug(f"processed {path}")
        return pkg.to_json()

    def write_csv(self):
        out = self.pool.abspath("stats/comparematch.csv")
        logger.info(f"writing csv data to {out}")
        rows = [ r.__dict__ for _, r in self.pkgs.items() ]
        with open(out, 'w') as f:
            w = csv.DictWriter(f, rows[0].keys())	#pytype: disable=wrong-arg-types
            w.writeheader()
            for row in rows:
                w.writerow(row)

    @staticmethod
    def execute(
        session_id: str = "",
        dryrun: bool = False
    ) -> bool:

        cmd = CompareMatchResults(session_id, dryrun)
        paths = cmd.get_paths(FILETYPE.ALIENMATCHER)
        paths += cmd.get_paths(FILETYPE.SNAPMATCH)
        paths += cmd.get_paths(FILETYPE.DELTACODE)
        cmd.exec(paths)
        if not dryrun:
            cmd.write_csv()
