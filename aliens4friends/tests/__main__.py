# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

#!/usr/bin/python3
import unittest

if __name__ == '__main__':
    # testsuite = unittest.TestLoader().discover('.')
	testsuite = unittest.TestLoader().discover('.')
	unittest.TextTestRunner(verbosity=1).run(testsuite)


