# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

#!/usr/bin/python3

r"""
#----------------#
# Aliens4friends #
#----------------#

A toolset for Software Composition Analysis

This tool tries to find matching license information about an input package on
well-known source repositories, such as Debian.

Usage
-----
(automatically printed from `argparse` module)

Configuration
-------------
Use a .env file to configure this script, we will take defaults, if nothing has
been set. See "config -h" for details, or just "config" to print the current
settings.

"""

import argparse
import logging
import sys
from textwrap import dedent

from aliens4friends.commands.add import Add
from aliens4friends.commands.comparematch import CompareMatchResults
from aliens4friends.commands.delta import Delta
from aliens4friends.commands.fossy import Fossy
from aliens4friends.commands.harvest import Harvest, Harvester
from aliens4friends.commands.match import Match
from aliens4friends.commands.scan import Scan
from aliens4friends.commands.session import SessionCmd
from aliens4friends.commands.snapmatch import SnapMatch
from aliens4friends.commands.spdxalien import SpdxAlien
from aliens4friends.commands.spdxdebian import SpdxDebian
from aliens4friends.commands.upload import Upload
from aliens4friends.commands.listpool import ListPool
from aliens4friends.commands.command import Processing
from aliens4friends.commons.pool import Pool, FILETYPE
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.utils import get_attr_names

PROGNAME = "aliens4friends"

# FIXME Move this into commands/ and create a registration class
# for new commands. All cmds should inherit that, and implement that interface
SUPPORTED_COMMANDS = [
	"add",
	"match",
	"scan",
	"delta",
	"spdxdebian",
	"spdxalien",
	"upload",
	"fossy",
	"config",
	"harvest",
	"snapmatch",
	"help",
	"session",
	"comparematch",
	"listpool"
]

class Aliens4Friends:

	def __init__(self) -> None:
		logging.basicConfig(
			level=logging.WARNING,
			format="%(asctime)s %(levelname)-8s %(name)-35s | %(message)s",
			datefmt='%y-%m-%d %H:%M:%S',
		)
		self.parser = argparse.ArgumentParser(
			prog=PROGNAME,
			conflict_handler='resolve',
		)

		self.subparsers = self.parser.add_subparsers(
			dest="command",
			help = f"Subcommand to run"
		)

		self.parsers = {}
		for cmd in SUPPORTED_COMMANDS:
			# use dispatch pattern to invoke method with same name
			getattr(self, f"parser_{cmd}")(cmd)

		# We must capture this option before we parse the arguments, because the
		# last positional argument FILE is mandatory. Hence, the parser would exit
		# with an error (There is no meaningful exception to catch, except for
		# SystemExit).
		if (
			len(sys.argv) < 2
			or sys.argv[1] == '--help'
			or sys.argv[1] == '-h'
		):
			self.help()

		# parse_args defaults to [1:] for args, but you need to
		# exclude the rest of the args too, or validation will fail
		self.args = self.parser.parse_args()
		if self.args.command not in SUPPORTED_COMMANDS:
			print(f"ERROR: Unknown command --> {self.args.command}. See help with {PROGNAME} -h.")
			sys.exit(1)

		self.setup()

		success = getattr(self, self.args.command)()
		sys.exit(0 if success else 1)

	def setup(self) -> None:
		try:
			self._subcommand_args()
		except AttributeError:
			# Some commands (ex., help) have no subcommand arguments
			pass
		logger = logging.getLogger(PROGNAME)
		logger.setLevel(Settings.LOGLEVEL)
		logging.getLogger("urllib3").setLevel(logging.INFO)
		logging.getLogger("chardet").setLevel(logging.INFO)

		self.pool = Pool(Settings.POOLPATH)
		basepath_deb = self.pool.mkdir(Settings.PATH_DEB)
		basepath_usr = self.pool.mkdir(Settings.PATH_USR)
		basepath_tmp = self.pool.mkdir(Settings.PATH_TMP)
		basepath_stt = self.pool.mkdir(Settings.PATH_STT)
		basepath_ses = self.pool.mkdir(Settings.PATH_SES)

		if self.args.command != "help":
			logger.info(f"# ALIENS4FRIENDS v{Settings.VERSION} with cache pool {Settings.POOLPATH}")
			logger.debug(f"  Pool directory structure created:")
			logger.debug(f"    - Debian Path          : {basepath_deb}")
			logger.debug(f"    - Userland Path        : {basepath_usr}")
			logger.debug(f"    - Temporary Files Path : {basepath_tmp}")
			logger.debug(f"    - Statistics Path      : {basepath_stt}")
			logger.debug(f"    - Sessions Path        : {basepath_ses}")

		logger = logging.getLogger()
		logger.setLevel(Settings.LOGLEVEL)


	def _subcommand_args(self) -> None:
		if self.args.ignore_cache:
			Settings.DOTENV["A4F_CACHE"] = Settings.POOLCACHED = False

		if self.args.verbose:
			Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "DEBUG"

		if self.args.quiet:
			Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "WARNING"

		if hasattr(self.args, 'print') and self.args.print:
			Settings.DOTENV["A4F_PRINTRESULT"] = Settings.PRINTRESULT = True

	def _args_session(self, parser: argparse.ArgumentParser, required: bool = True) -> None:
		parser.add_argument(
			"-s",
			"--session",
			type = str,
			default="",
			required=required,
			help="Use a session to create a list of packages, otherwise all packages inside the pool are used"
		)


	def _args_defaults(self, parser: argparse.ArgumentParser, describe_files: str = "") -> None:
		parser.add_argument(
			"-i",
			"--ignore-cache",
			action = "store_true",
			default = False,
			help = f"Ignore the cache pool and overwrite existing results " \
				   f"and tmp files. This overrides the A4F_CACHE env var."
		)
		group = parser.add_mutually_exclusive_group()
		group.add_argument(
			"-v",
			"--verbose",
			action = "store_true",
			default = False,
			help = "Show debug output. This overrides the A4F_LOGLEVEL env var."
		)
		group.add_argument(
			"-q",
			"--quiet",
			action = "store_true",
			default = False,
			help = "Show only warnings and errors. This overrides the A4F_LOGLEVEL env var."
		)
		parser.add_argument(
			"--dryrun",
			help = "Log operations to be done without doing anything",
			action = "store_true",
			default = False
		)

	def _args_glob(self, parser: argparse.ArgumentParser):
		parser.add_argument(
			"glob_name",
			help="Wildcard pattern to filter by package names. Do not forget to quote it!",
			default="",
			nargs="?"
		)
		parser.add_argument(
			"glob_version",
			help="Wildcard pattern to filter by package versions. Do not forget to quote it!",
			default="",
			nargs="?"
		)

	def _args_files(self, parser: argparse.ArgumentParser, describe_files: str) -> None:
		parser.add_argument(
			"FILES",
			nargs = "*",
			type = argparse.FileType('r'),
			help = describe_files
		)

	def _args_print_to_stdout(self, parser: argparse.ArgumentParser) -> None:
		parser.add_argument(
			"-p",
			"--print",
			action = "store_true",
			default = False,
			help = "Print result also to stdout."
		)

	def _args_use_oldmatcher(self, parser: argparse.ArgumentParser) -> None:
		parser.add_argument(
			"--use-oldmatcher",
			action = "store_true",
			default = False,
			help = "Use the old alienmatcher.json input files, not snapmatch.json."
		)

	def _args_apply_debian_full(self, parser: argparse.ArgumentParser) -> None:
		parser.add_argument(
			"--apply-debian-full",
			action = "store_true",
			default= False,
			help= "apply all debian/copyright decisions as LicenseConcluded in full, without any filter"
		)

	def config(self) -> None:
		for k, v in Settings.DOTENV.items():
			print(f"{k}={v}")
		exit(0)

	def help(self) -> None:
		docparts = __doc__.split(
			"Usage\n-----\n(automatically printed from `argparse` module)\n", 1
		)
		print(docparts[0])     # Print title and section before "usage"
		print("Usage\n-----")
		self.parser.print_help()    # Print usage information
		print(docparts[1])     # Print the rest
		exit(0)

	def parser_help(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Show a help message"
		)

	def parser_config(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			formatter_class=argparse.RawTextHelpFormatter,
			help="Print .env configs or defaults",
			description=dedent("""\
				Create a .env file in the folder, where you execute the command.

				Environmental variables:
				  - A4F_POOL        : Path to the cache pool
				  - A4F_CACHE       : True/False, if cache should be used or overwritten (default = True)
				  - A4F_DEBUG       : Debug level as seen inside the "logging" package (default = INFO)
				  - A4F_SCANCODE    : wrapper/native, whether we use a natively installed scancode or
				                      run it from our docker wrapper (default = native)
				  - A4F_PRINTRESULT : Print results also to stdout
				  - SPDX_TOOLS_CMD  : command to invoke java spdx tools (default =
				                      'java -jar /usr/local/lib/spdx-tools-2.2.5-jar-with-dependencies.jar')
				  - SPDX_DISCLAIMER : legal disclaimer to add into generated SPDX files (optional)
				  - PACKAGE_ID_EXT  : extension to append to package IDs in harvest.json file
				  					  (optional, arbitrary)
				  - FOSSY_USER,
				    FOSSY_PASSWORD,
				    FOSSY_GROUP_ID,
				    FOSSY_SERVER    : parameters to access fossology server
					                  (defaults: 'fossy', 'fossy', 3, 'http://localhost/repo').
				""")
		)

	def parser_session(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Initialize a session"
		)
		group = self.parsers[cmd].add_mutually_exclusive_group()
		group.add_argument(
			"-f",
			"--filter",
			type = str,
			required = False,
			help = "Filter the package list inside the given session (use -s SESSION for that)"
		)
		group.add_argument(
			"-c",
			"--create",
			action = "store_true",
			default = False,
			help = "Create and fill a session from a given ID or random string (if absent)"
		)
		group.add_argument(
			"-n",
			"--new",
			action = "store_true",
			default = False,
			help = "Create a new empty session from a given ID or random string (if absent)"
		)
		self._args_session(self.parsers[cmd], required=False)
		self._args_glob(self.parsers[cmd])

	def parser_add(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Verify and add Alien Packages to the pool"
		)
		self.parsers[cmd].add_argument(
			"-f",
			"--force",
			action = "store_true",
			default = False,
			help = "Force AlienSrc package overwrite."
		)
		self._args_defaults(
			self.parsers[cmd]
		)
		self._args_files(
			self.parsers[cmd],
			"The Alien Packages (also wildcards allowed)"
		)
		self._args_session(self.parsers[cmd])

	def parser_match(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Find a matching source package on the current debian.org package repo"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_snapmatch(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Find a matching source package on snapshot.debian.org"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_scan(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Scan a source code folder and find license/copyright information (scancode)"
		)
		self._args_defaults(
			self.parsers[cmd]
		)
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_use_oldmatcher(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_delta(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Understand differences between matching packages (deltacode)"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_use_oldmatcher(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_spdxdebian(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Translate Debian dep5 license information into SPDX files"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_use_oldmatcher(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_spdxalien(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Generate SPDX files out of Alien Package and Deltacode information"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_apply_debian_full(self.parsers[cmd])
		self._args_print_to_stdout(self.parsers[cmd])
		self._args_use_oldmatcher(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_upload(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Upload Alien Packages to Fossology"
		)
		self._args_defaults(self.parsers[cmd])
		self.parsers[cmd].add_argument(
			"--description",
			type = str,
			default = "uploaded by aliens4friends",
			help = "Fossology upload description"
		)
		self.parsers[cmd].add_argument(
			"--folder",
			type = str,
			required = True,
			help = "Fossology folder where to upload Alien Packages"
		)
		self._args_session(self.parsers[cmd])

	def parser_fossy(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Get final SPDX and json data from Fossology"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_harvest(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Harvest tinfoilhat, alienmatcher, deltacode and fossy " \
			     "outputs to create a report for the dashboard"
		)
		self._args_defaults(
			self.parsers[cmd],
			f"Various files are supported: {Harvester.SUPPORTED_FILES}"
		)
		self._args_print_to_stdout(self.parsers[cmd])
		self.parsers[cmd].add_argument(
			"--add-missing",
			action = "store_true",
			default = False,
			help = "Add missing input files to the report while harvesting."
		)
		self.parsers[cmd].add_argument(
			"-b",
			"--with-binaries",
			type = str,
			required = False,
			default = [],
			nargs = "+",
			help = "Add only given binary_packages to the report while harvesting, separate multiple entries with space."
		)
		self._args_use_oldmatcher(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_comparematch(self, cmd:str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Compare match, snapmatch and deltacode results and write stats/comparematch.csv"
		)
		self._args_defaults(self.parsers[cmd])
		self._args_session(self.parsers[cmd])

	def parser_listpool(self, cmd:str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="List files in pool for debugging"
		)
		self._args_defaults(self.parsers[cmd])
		self.parsers[cmd].add_argument(
			"--processing",
			choices=get_attr_names(Processing),
			default="LOOP"
		)
		self.parsers[cmd].add_argument(
			"--filetype",
			choices=get_attr_names(FILETYPE),
			required=True
		)
		self.parsers[cmd].add_argument(
			"--testarg",
			help="test argument for debugging purposes"
		)
		self.parsers[cmd].add_argument(
			"--testarg2",
			help="2nd test argument for debugging purposes"
		)
		self._args_session(self.parsers[cmd])

	def session(self) -> bool:
		if (self.args.glob_name or self.args.glob_version) and (self.args.new or self.args.filter):
			logging.getLogger(PROGNAME).error(
				f"-n or -f with globs are not allowed: '{self.args.glob_name} {self.args.glob_version}' given!"
			)
			sys.exit(1)

		return SessionCmd.execute(
			self.args.session,
			self.args.create,
			self.args.filter,
			self.args.new,
			self.args.glob_name,
   			self.args.glob_version,
		)

	def add(self) -> bool:
		file_list = [ f.name for f in self.args.FILES ]
		return Add.execute(
			file_list,
			self.args.force,
			self.args.session,
			self.args.dryrun
		)

	def match(self) -> bool:
		return Match.execute(
			self.args.session,
			self.args.dryrun
		)

	def snapmatch(self) -> bool:
		return SnapMatch.execute(
			self.args.session,
			self.args.dryrun
		)

	def scan(self) -> bool:
		return Scan.execute(
			self.args.use_oldmatcher,
			self.args.session,
			self.args.dryrun
		)

	def delta(self) -> bool:
		return Delta.execute(
			self.args.use_oldmatcher,
			self.args.session,
			self.args.dryrun
		)

	def spdxdebian(self) -> bool:
		return SpdxDebian.execute(
			self.args.use_oldmatcher,
			self.args.session,
			self.args.dryrun
		)

	def spdxalien(self) -> bool:
		return SpdxAlien.execute(
			self.args.use_oldmatcher,
			self.args.apply_debian_full,
			self.args.session,
			self.args.dryrun
		)

	def upload(self) -> bool:
		return Upload.execute(
			self.args.folder,
			self.args.session,
			self.args.description,
			self.args.dryrun
		)

	def fossy(self) -> bool:
		return Fossy.execute(
			self.args.session,
			self.args.dryrun
	)

	def harvest(self) -> bool:
		return Harvest.execute(
			self.args.add_missing,
			self.args.with_binaries,
			self.args.use_oldmatcher,
			self.args.session,
			self.args.dryrun
		)

	def comparematch(self) -> bool:
		return CompareMatchResults.execute(
			self.args.session,
			self.args.dryrun
		)

	def listpool(self) -> bool:
		return ListPool.execute(
			self.args.session,
			self.args.filetype,
			self.args.processing,
			self.args.testarg,
			self.args.testarg2
		)


if __name__ == "__main__":
	Aliens4Friends()
