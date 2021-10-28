# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

import unittest
import shutil
import os

from aliens4friends.commons.settings import Settings
from aliens4friends.commons.pool import Pool, PoolError

TEST_PATH = "/tmp/a4f/tests"

class TestingPool(unittest.TestCase):

	def setUp(self):
		self.shared_pool = Pool(f"{TEST_PATH}/pool")
		Settings.DOTENV["A4F_CACHE"] = Settings.POOLCACHED = False
		self.shared_tmpfile = f"{TEST_PATH}/tmpfile.txt"
		with open(self.shared_tmpfile, "w") as f:
			f.write("Hello World!")

	def tearDown(self):
		shutil.rmtree(TEST_PATH)

	def _test_add_write(self, content):
		self.assertTrue(
			os.path.isfile(
				self.shared_pool.abspath(
					"test_add",
					"a_folder",
					"tmpfile.txt"
				)
			)
		)
		if isinstance(content, str):
			self.assertEqual(
				self.shared_pool.get(
					"test_add",
					"a_folder",
					"tmpfile.txt"
				),
				content
			)
		else:
			self.assertEqual(
				self.shared_pool.get_json(
					"test_add",
					"a_folder",
					"tmpfile.txt"
				),
				content
			)

	def test_add(self):
		self.shared_pool.add(
			self.shared_tmpfile,
			"test_add",
			"a_folder"
		)
		self._test_add_write("Hello World!")

	def test_write(self):
		self.shared_pool.write(
			b"TEST WRITE",
			"test_add",
			"a_folder",
			"tmpfile.txt"
		)
		self._test_add_write("TEST WRITE")

	def test_write_json(self):
		self.shared_pool.write_json(
			[1,2,3],
			"test_add",
			"a_folder",
			"tmpfile.txt"
		)
		self._test_add_write([1,2,3])


	def test_add_with_history(self):
		self.shared_pool.add_with_history(
			self.shared_tmpfile,
			"PREFIX",
			"userland",
			"pckx",
			"v1.0.2"
		)
		link = self.shared_pool.abspath("userland/pckx/v1.0.2/tmpfile.txt")
		self.assertTrue(os.path.islink(link))
		self.assertEqual(os.readlink(link), "history/PREFIXtmpfile.txt")

		self.shared_pool.add_with_history(
			self.shared_tmpfile,
			"PREFIX2",
			"userland",
			"pckx",
			"v1.0.2"
		)
		link = self.shared_pool.abspath("userland/pckx/v1.0.2/tmpfile.txt")
		self.assertTrue(os.path.islink(link))
		self.assertEqual(os.readlink(link), "history/PREFIX2tmpfile.txt")

	def test_relpath(self):
		try:
			result = self.shared_pool.relpath("/test/abc.txt")
			self.fail("Exception missing: only relative paths allowed as parameter")
		except PoolError:
			pass

		result = self.shared_pool.relpath("test/abc.txt")
		self.assertEqual(result, "test/abc.txt")

		try:
			result = self.shared_pool.clnpath(f"{TEST_PATH}/test/abc.txt")
			self.fail("Exception missing: only paths inside the pool root directory allowed as parameter")
		except PoolError:
			pass

	def test_package_info_from_path(self):
		inputs = [
			"userland/tar/1.32-r0/tar-1.32.tar.bz2-gid3.alien.spdx",
			"userland/tar/1.32-r0/tar-1.32-r0-05be69c9-gid3.fossy.json",
			"userland/tar/1.32-r0/tar-1.32-r0-05be69c9-gid123.fossy.json",
		]

		expect = [
			["tar", "1.32-r0", "", "3", "alien.spdx"],
			["tar", "1.32-r0", "05be69c9", "3", "fossy.json"],
			["tar", "1.32-r0", "05be69c9", "123", "fossy.json"],
		]

		for i, v in enumerate(inputs):
			name, version, variant, gid, ext = self.shared_pool.packageinfo_from_path(v)
			self.assertEqual(name, expect[i][0])
			self.assertEqual(version, expect[i][1])
			self.assertEqual(variant, expect[i][2])
			self.assertEqual(gid, expect[i][3])
			self.assertEqual(ext, expect[i][4])

if __name__ == '__main__':
    unittest.main()
