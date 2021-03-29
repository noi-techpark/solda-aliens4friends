#!/usr/bin/python3

r"""## Aliens4friends: A toolset for Software Composition Analysis

This tool tries to find matching license information about an input
package on well-known source repositories, such as Debian.

Usage
-----
(automatically printed from `argparse` module)

Configuration
-------------
Use a .env file to configure this script, we will take defaults, if
nothing has been set.

- A4F_POOL        : Path to the cache pool
- A4F_CACHE       : True/False, if cache should be used or overwritten (default = True)
- A4F_DEBUG       : Debug level as seen inside the "logging" package (default = INFO)
- A4F_SCANCODE    : wrapper/native, whether we use a natively installed scancode or
                    run it from our docker wrapper (default = native)
- A4F_PRINTRESULT : Print results also to stdout
- SPDX_TOOLS_CMD  : command to invoke java spdx tools (default =
                    'java -jar /usr/local/lib/spdx-tools-2.2.5-jar-with-dependencies.jar')
- FOSSY_USER, FOSSY_PASSWORD, FOSSY_GROUP_ID, FOSSY_SERVER: parameters to access fossology
                    server (defaults: 'fossy', 'fossy', 3, 'http://localhost/repo').
"""

import logging
import argparse
import sys

from aliens4friends.commons.settings import Settings
from aliens4friends.alienmatcher import AlienMatcher
from aliens4friends.scancode import Scancode
from aliens4friends.deltacodeng import DeltaCodeNG
from aliens4friends.debian2spdx import Debian2SPDX
from aliens4friends.debian2alienspdx import Debian2AlienSPDX
from aliens4friends.tinfoilhat2dashboard import TinfoilHat2Dashboard
from aliens4friends.alienspdx2fossy import AlienSPDX2Fossy

from aliens4friends.tests import test_debian2spdx
from aliens4friends.tests import test_alienmatcher
from aliens4friends.tests import test_version
from aliens4friends.tests import test_alienpackage
from aliens4friends.tests import test_scancode

PROGNAME = "aliens4friends"
SUPPORTED_COMMANDS = [
	"match",
	"scancode",
	"deltacode",
	"debian2spdx",
	"debian2alienspdx",
	"alienspdx2fossy",
	"config",
	"tinfoilhat2dashboard"
]

if __name__ == "__main__":

	logging.basicConfig(level = logging.WARNING)

	parser = argparse.ArgumentParser(conflict_handler='resolve', prog=PROGNAME)

	parser.add_argument(
		"-i",
		"--ignore-cache",
		action = "store_true",
		default = False,
		help = f"Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var."
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
		"CMD",
		help = f"The main command",
		choices = SUPPORTED_COMMANDS
	)

	parser.add_argument(
		"FILES",
		nargs = "*",
		type = argparse.FileType('r'),
		help = "The Alien Packages (also wildcards allowed)"
	)

	# We must capture this option before we parse the arguments, because the
    # last positional argument FILE is mandatory. Hence, the parser would exit
    # with an error (There is no meaningful exception to catch, except for
    # SystemExit).
	if len(sys.argv) < 2 or sys.argv[1] == '--help' or sys.argv[1] == '-h':
		docparts = __doc__.split(
			"Usage\n-----\n(automatically printed from `argparse` module)\n", 1
		)

		# Print title and section before "usage"
		print (docparts[0])

		# Print usage information
		print("Usage\n-----")
		parser.print_help()

		# Print the rest
		#print "\n".join(__doc__.split('\n', 1)[1:])
		print (docparts[1])

		sys.exit(0)

	# Now parse regular command line arguments
	args = parser.parse_args()

	if args.ignore_cache:
		Settings.DOTENV["A4F_CACHE"] = Settings.POOLCACHED = False

	if args.verbose:
		Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "DEBUG"

	if args.quiet:
		Settings.DOTENV["A4F_LOGLEVEL"] = Settings.LOGLEVEL = "WARNING"

	if args.print:
		Settings.DOTENV["A4F_PRINTRESULT"] = Settings.PRINTRESULT = True

	if args.CMD == "match":
		logger = logging.getLogger('aliens4friends.alienmatcher')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		AlienMatcher.execute(file_list)
	elif args.CMD == "scancode":
		logger = logging.getLogger('aliens4friends.scancode')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		Scancode.execute(file_list)
	elif args.CMD == "deltacode":
		logger = logging.getLogger('aliens4friends.deltacodeng')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		DeltaCodeNG.execute(file_list)
	elif args.CMD == "debian2spdx":
		logger = logging.getLogger('aliens4friends.debian2spdx')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		Debian2SPDX.execute(file_list)
	elif args.CMD == "debian2alienspdx":
		logger = logging.getLogger('aliens4friends.debian2alienspdx')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		Debian2AlienSPDX.execute(file_list)
	elif args.CMD == "alienspdx2fossy":
		logger = logging.getLogger('aliens4friends.alienspdx2fossy')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		AlienSPDX2Fossy.execute(file_list)
	elif args.CMD == "tinfoilhat2dashboard":
		logger = logging.getLogger('aliens4friends.tinfoilhat2dashboard')
		logger.setLevel(Settings.LOGLEVEL)
		file_list = [
			f.name for f in args.FILES
		]
		TinfoilHat2Dashboard.execute(file_list)
	elif args.CMD == "config":
		for k, v in Settings.DOTENV.items():
			print(f"{k}={v}")
	else:
		print(f"ERROR: Unknown command --> {args.CMD}. See help with {PROGNAME} -h.")


	# test_debian2spdx.test()
	# test_alienmatcher.test_all()
	# test_alienmatcher.test_list()
	# test_alienmatcher.test_single()
	# test_alienmatcher.test_search()
	# test_alienpackage.test1()
	# test_scancode.test_single()
	# test_scancode.test_single_from_matcheroutput()
