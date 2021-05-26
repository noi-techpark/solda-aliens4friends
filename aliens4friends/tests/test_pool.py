import unittest
import shutil
import os

from aliens4friends.commons.settings import Settings
from aliens4friends.commons.pool import Pool

TEST_PATH = "/tmp/a4f/tests"

class TestingPool(unittest.TestCase):

	def setUp(self):
		self.shared_pool = Pool(f"{TEST_PATH}/pool")
		Settings.DOTENV["A4F_CACHE"] = Settings.POOLCACHED = False
		self.shared_tmpfile = f"{TEST_PATH}/tmpfile.txt"
		with open(self.shared_tmpfile, "w") as f:
			f.write("Hello World!")

	def tearDown(self):
		#shutil.rmtree(TEST_PATH)
		pass

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


unittest.main()
