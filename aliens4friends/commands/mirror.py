# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

# example invocation of the mirror command (--verbose is default):
#
# % python3 -m aliens4friends mirror --mode FULL --session "initial_import"
# aliens4friends:slug=# ALIENS4FRIENDS v0.7.0 with cache pool /xxx/a4fpool
# aliens4friends.commands.command:slug=MIRROR: Start with session 'initial_import'.
# aliens4friends.commands.mirror:slug=Mirror(Command) class created
# aliens4friends.commands.mirror:slug=connected to Postgres database
# aliens4friends.commands.mirror:slug=FULL mode: delete/vacuum done in 1.951 sec
# aliens4friends.commands.mirror:slug=100 files processed
# aliens4friends.commands.mirror:slug=200 files processed
# aliens4friends.commands.mirror:slug=300 files processed
# aliens4friends.commands.mirror:slug=400 files processed
# aliens4friends.commands.mirror:slug=416 files processed in 70.524 sec
# aliens4friends.commands.mirror:slug=disconnected from Postgres database
# %

import sys
import time
from builtins import object
from typing import Union, Pattern
import logging

import psycopg2

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings


# from aliens4friends.models.tinfoilhat import TinfoilHatModel

logger = logging.getLogger(__name__)


class Mirror(Command):

	session_str: str
	cnt_processed: int
	cur: object

	dryrun: bool
	verbose: bool
	mode: str

	def __init__(self, session_id: str, dryrun: bool, quiet: bool, verbose: bool, mode: str):
		# don't allow empty sessions
		if session_id == "":
			logger.error("fatal error: session identifier is empty")
			sys.exit(1)
		self.session_str = session_id
		self.cnt_processed = 0
		self.cur = None
		# Processing mode should be LOOP (we use a single connection and bundle the transactions)
		super().__init__(session_id, Processing.LOOP, dryrun)
		# dryrun
		self.dryrun = bool(dryrun)
		# verbosity (we just have two levels)
		if quiet and not verbose:
			self.verbose = False
		elif not quiet and verbose:
			self.verbose = True
		elif not quiet and not verbose:  # we default to verbose
			self.verbose = True
		else:
			logger.error("fatal error: inconsistent quiet/verbose flags")
			sys.exit(1)
		# mode
		if mode == "FULL" or mode == "DELTA":
			self.mode = mode
		else:
			logger.error("fatal error: invalid mode '%s', FULL or DELTA expected" % mode)
			sys.exit(1)
		if self.verbose:
			logger.info("Mirror(Command) class created")

	@staticmethod
	def execute(
		session_id: str = "",
		dryrun: bool = True,
		quiet: bool = True,
		verbose: bool = False,
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

		cmd = Mirror(session_id, dryrun, quiet, verbose, mode)

		if cmd.dryrun:
			# dryrun: return right away, but first call exec_with_paths() to have the files logged
			return cmd.exec_with_paths(FILETYPE.TINFOILHAT)

		try:
			HOST=Settings.DOTENV["MIRROR_DB_HOST"]
			PORT=Settings.DOTENV["MIRROR_DB_PORT"]
			DBNAME=Settings.DOTENV["MIRROR_DB_DBNAME"]
			USER=Settings.DOTENV["MIRROR_DB_USER"]
			PASSWORD=Settings.DOTENV["MIRROR_DB_PASSWORD"]
			con = psycopg2.connect("host=%s port=%s dbname=%s user=%s password=%s" % (HOST, PORT, DBNAME, USER, PASSWORD))
		except psycopg2.OperationalError as ex:
			logger.error("fatal error: cannot connect to Postgres database\n%s" % ex)
			sys.exit(1)

		con.autocommit = False
		cmd.cur = con.cursor()
		if cmd.verbose:
			logger.info("connected to Postgres database")

		if cmd.mode == "FULL":
			# FULL mode: delete all files for the given session before
			t0 = time.time()
			try:
				cmd.cur.execute("delete from tinfoilhat where session = %s", (cmd.session_str,))
				con.commit()
				con.autocommit = True
				cmd.cur.execute("vacuum tinfoilhat")
				con.autocommit = False
			except psycopg2.DatabaseError as ex:
				logger.error("fatal error: delete/vacuum statement failed\n%s" % ex)
				sys.exit(1)
			if cmd.verbose:
				logger.info("FULL mode: delete/vacuum done in %.3f sec" % (time.time() - t0))

		t0 = time.time()

		result = cmd.exec_with_paths(FILETYPE.TINFOILHAT)

		con.commit()

		cmd.cur.close()
		con.close()

		if cmd.verbose:
			logger.info("%d files processed in %.3f sec" % (cmd.cnt_processed, time.time() - t0))
			logger.info("disconnected from Postgres database")

		return result

	def run(self, path: str) -> Union[str, bool]:
		if self.dryrun:
			# in dryrun mode this shouldn't be called by the super class, but better be safe
			return True
		self.cnt_processed += 1
		with open(path, 'r') as fp:
			data = fp.read()
		try:
			# note the on conflict clause: only files that don't violate the (session, fname) unique key are inserted
			self.cur.execute("insert into tinfoilhat (session, fname, data) values (%s, %s, %s) on conflict do nothing",
																				(self.session_str, path, data))
		except psycopg2.DatabaseError as ex:
			logger.error("fatal error: insert statement failed\n%s" % ex)
			sys.exit(1)
		if self.verbose and self.cnt_processed % 100 == 0:
			logger.info("%d files processed" % self.cnt_processed)
		return True

	def hint(self) -> str:
		# if a session is empty, a comment is printed with this hint about what commands the user should have run first
		return "session/add"
