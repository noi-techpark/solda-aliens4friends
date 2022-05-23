# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import time
from builtins import object
from typing import Union
import logging

import psycopg2

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class MirrorError(Exception):
	pass

class Mirror(Command):

	cnt_processed: int
	cur: object
	mode: str

	def __init__(self, session_id: str, dryrun: bool, mode: str):
		# Processing mode should be LOOP (we use a single connection and bundle the transactions)
		super().__init__(session_id, Processing.LOOP, dryrun)

		self.cnt_processed = 0
		self.cur = None

		# mode, no check needed, already done by argparse
		self.mode = mode

		logger.debug("Mirror(Command) class created")

	@staticmethod
	def execute(
		session_id: str = "",
		dryrun: bool = True,
		mode: str = "FULL"
	) -> bool:
		"""
		Entry point for subcommand "mirror". Unless dryrun, these steps will be performed:
			- open a connection to the database,
			- have the run() method called for each tinfoilhat JSON file from the current
			  session via exec_with_paths() - the run() method will persist the file in the DB
			- commit and close the database connection

		In FULL mode, records for the given session will be deleted first, so all files
		will be inserted. In DELTA mode, (session, filename) pairs that are already present will
		be left as they are thanks to the "on conflict do nothing" clause in the insert query.
		"""

		cmd = Mirror(session_id, dryrun, mode)

		if cmd.dryrun:
			# dryrun: return right away, but first call exec_with_paths() to have the files logged
			return cmd.exec_with_paths(FILETYPE.TINFOILHAT)

		try:
			con = psycopg2.connect(
				"host=%s port=%s dbname=%s user=%s password=%s" % (
					Settings.MIRROR_DB_HOST,
					Settings.MIRROR_DB_PORT,
					Settings.MIRROR_DB_DBNAME,
					Settings.MIRROR_DB_USER,
					Settings.MIRROR_DB_PASSWORD
				)
			)
		except psycopg2.OperationalError as ex:
			error = "fatal error: cannot connect to Postgres database\n%s" % ex
			logger.error(error)
			raise MirrorError(error)

		con.autocommit = False
		cmd.cur = con.cursor()
		logger.debug("connected to Postgres database")

		if cmd.mode == "FULL":
			# FULL mode: delete all files for the given session before
			t0 = time.time()
			try:
				cmd.cur.execute("delete from tinfoilhat where session = %s", (cmd.session.session_id,))
				con.commit()
				con.autocommit = True
				cmd.cur.execute("vacuum tinfoilhat")
				con.autocommit = False
			except psycopg2.DatabaseError as ex:
				error = "fatal error: delete/vacuum statement failed\n%s" % ex
				logger.error(error)
				raise MirrorError(error)
			logger.debug("FULL mode: delete/vacuum done in %.3f sec" % (time.time() - t0))

		t0 = time.time()

		result = cmd.exec_with_paths(FILETYPE.TINFOILHAT)

		con.commit()

		cmd.cur.close()
		con.close()

		logger.debug("%d files processed in %.3f sec" % (cmd.cnt_processed, time.time() - t0))
		logger.debug("disconnected from Postgres database")

		return result

	def run(self, path: str) -> Union[str, bool]:
		self.cnt_processed += 1
		with open(path, 'r') as fp:
			data = fp.read()
		try:
			# note the on conflict clause: only files that don't violate the (session, fname) unique key are inserted
			self.cur.execute(
				"insert into tinfoilhat (session, fname, data) values (%s, %s, %s) on conflict do nothing",
				(
					self.session.session_id,
					self.pool.clnpath(path),
					data
				)
			)
		except psycopg2.DatabaseError as ex:
			error = "fatal error: insert statement failed\n%s" % ex
			logger.error(error)
			raise MirrorError(error)

		if self.cnt_processed % 100 == 0:
			logger.debug("%d files processed" % self.cnt_processed)

		return True

	def hint(self) -> str:
		# if a session is empty, a comment is printed with this hint about what commands the user should have run first
		return "session/add"
