import logging
import argparse

from aliens4friends.tests import test_debian2spdx
from aliens4friends.tests import test_alienmatcher
from aliens4friends.tests import test_version
from aliens4friends.tests import test_alienpackage
from aliens4friends.tests import test_scancode


if __name__ == "__main__":

	logging.basicConfig(level = logging.WARNING)

	# logger = logging.getLogger('aliens4friends.alienmatcher')
	# logger.setLevel(logging.DEBUG)

	# test_debian2spdx.test()
	test_alienmatcher.test_all()
	# test_alienmatcher.test_list()
	# test_alienmatcher.test_single()
	# test_alienmatcher.test_search()
	# test_alienpackage.test1()
	# test_scancode.test_single()
	# test_scancode.test_single_from_matcheroutput()

