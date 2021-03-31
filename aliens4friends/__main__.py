#!/usr/bin/python3

r"""## Aliens4friends: A toolset for Software Composition Analysis

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

import logging
import argparse
import sys
from textwrap import dedent

from aliens4friends.commons.settings import Settings
from aliens4friends.alienmatcher import AlienMatcher
from aliens4friends.scancode import Scancode
from aliens4friends.deltacodeng import DeltaCodeNG
from aliens4friends.debian2spdx import Debian2SPDX
from aliens4friends.makealienspdx import MakeAlienSPDX
from aliens4friends.harvest import Harvest
from aliens4friends.uploadaliens2fossy import UploadAliens2Fossy

from aliens4friends.tests import test_debian2spdx
from aliens4friends.tests import test_alienmatcher
from aliens4friends.tests import test_version
from aliens4friends.tests import test_alienpackage
from aliens4friends.tests import test_scancode

PROGNAME = "aliens4friends"
SUPPORTED_COMMANDS = [
	"match",
	"scan",
	"delta",
	"spdxdebian",
	"spdxalien",
	"upload",
	"config",
	"harvest",
	"help"
]
LOGGERS = {
	"match"      : 'aliens4friends.alienmatcher',
	"scan"       : 'aliens4friends.scancode',
	"delta"      : 'aliens4friends.deltacodeng',
	"spdxdebian" : 'aliens4friends.debian2spdx',
	"spdxalien"  : 'aliens4friends.makealienspdx',
	"upload"     : 'aliens4friends.uploadaliens2fossy',
	"harvest"    : 'aliens4friends.harvest'
}

class Aliens4Friends:

	def __init__(self):
		logging.basicConfig(level = logging.WARNING)
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

		getattr(self, self.args.command)()


	def _subcommand_args(self):
		if self.args.ignore_cache:
			Settings.DOTENV["A4F_CACHE"] = Settings.POOLCACHED = False

		if self.args.verbose:
			Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "DEBUG"

		if self.args.quiet:
			Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "WARNING"

		if self.args.print:
			Settings.DOTENV["A4F_PRINTRESULT"] = Settings.PRINTRESULT = True

		logger = logging.getLogger(LOGGERS[self.args.command])
		logger.setLevel(Settings.LOGLEVEL)

		return [ f.name for f in self.args.FILES ]



	def _add_default_args(self, parser, describe_files = ""):
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
			"-p",
			"--print",
			action = "store_true",
			default = False,
			help = "Print result also to stdout."
		)
		parser.add_argument(
			"FILES",
			nargs = "*",
			type = argparse.FileType('r'),
			help = describe_files
		)

	def config(self):
		for k, v in Settings.DOTENV.items():
			print(f"{k}={v}")

	def help(self):
		docparts = __doc__.split(
			"Usage\n-----\n(automatically printed from `argparse` module)\n", 1
		)
		print(docparts[0])     # Print title and section before "usage"
		print("Usage\n-----")
		self.parser.print_help()    # Print usage information
		print(docparts[1])     # Print the rest
		exit(0)

	def parser_help(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Show a help message"
		)

	def parser_config(self, cmd):
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
				  - FOSSY_USER,
				    FOSSY_PASSWORD,
				    FOSSY_GROUP_ID,
				    FOSSY_SERVER    : parameters to access fossology server
					                  (defaults: 'fossy', 'fossy', 3, 'http://localhost/repo').
				""")
		)

	def parser_match(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Find a matching source package on Debian"
		)
		self._add_default_args(
			self.parsers[cmd],
			"The Alien Packages (also wildcards allowed)"
		)

	def parser_scan(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Scan a source code folder and find license/copyright information (scancode)"
		)
		self._add_default_args(
			self.parsers[cmd],
			"The paths to source code folders"
		)

	def parser_delta(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Understand differences between two scancode results"
		)
		self._add_default_args(self.parsers[cmd])

	def parser_spdxdebian(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Translate Debian dep5 license information into SPDX files"
		)
		self._add_default_args(self.parsers[cmd])

	def parser_spdxalien(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Generate SPDX files out of Alien Package and Deltacode information"
		)
		self._add_default_args(
			self.parsers[cmd],
		)

	def parser_upload(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Upload Alien Packages to Fossology"
		)
		self._add_default_args(
			self.parsers[cmd],
			"Alien package files"
		)

	def parser_harvest(self, cmd):
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Harvest tinfoilhat, alienmatcher, deltacode, fossy and " \
			     "fossy-summary outputs and create a report for the dashboard"
		)
		self._add_default_args(
			self.parsers[cmd],
			f"Various files are supported: {Harvest.SUPPORTED_FILES}"
		)
		self.parsers[cmd].add_argument(
			"-f",
			"--full-report",
			action = "store_true",
			default = False,
			help = "Add more information to the report while harvesting."
		)


	def match(self):
		file_list = self._subcommand_args()
		AlienMatcher.execute(file_list)

	def scan(self):
		file_list = self._subcommand_args()
		Scancode.execute(file_list)

	def delta(self):
		file_list = self._subcommand_args()
		DeltaCodeNG.execute(file_list)

	def spdxdebian(self):
		file_list = self._subcommand_args()
		Debian2SPDX.execute(file_list)

	def spdxalien(self):
		file_list = self._subcommand_args()
		MakeAlienSPDX.execute(file_list)

	def upload(self):
		file_list = self._subcommand_args()
		UploadAliens2Fossy.execute(file_list)

	def harvest(self):
		file_list = self._subcommand_args()
		Harvest.execute(file_list)


if __name__ == "__main__":
	Aliens4Friends()
