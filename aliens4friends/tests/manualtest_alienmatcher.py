# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings
import os
from aliens4friends.commands.match import AlienMatcher, AlienMatcherError
from aliens4friends.commons.package import PackageError, Package, DebianPackage

IGNORE_CACHE = True

def _setup():
	print(f"{'ALIENSRC':<80}{'OUTCOME':<10}{'DEBSRC_DEBIAN':<60}{'DEBSRC_ORIG':<60}ERRORS")
	print("-"*300)
	return AlienMatcher(), os.path.join(os.getcwd(), "tmp", "alberto", "SCA")

def test_all():
	_, path = _setup()
	AlienMatcher.execute(os.path.join(path, "*.aliensrc"))


def test_single():
	matcher, path = _setup()
	matcher.run(os.path.join(path, "alien-packagegroup-base-1.0.aliensrc"))

def test_search():
	# matcher, path = _setup()
	# package = AlienPackage(os.path.join(path, "alien-libmodulemd-v1-1.8.16.aliensrc"))
	matcher = AlienMatcher()
	package = Package("linux-yocto", "5.4.69+gitAUTOINC+7f765dcb29_cfcdd63145")
	package_match = matcher.search(package)
	print(package_match)

def test_list():
	matcher, path = _setup()

	# packages = [
	# 	"alien-libx11-compose-data-1.6.8.aliensrc",
	# 	"alien-opkg-utils-0.4.2.aliensrc",
	# 	"alien-psplash-0.1+gitAUTOINC+0a902f7cd8.aliensrc",
	# 	"alien-update-rc.d-0.8.aliensrc",
	# ]

	packages = [
		"alien-libpciaccess-0.16.aliensrc",
		"alien-libxkbcommon-0.10.0.aliensrc",
		"alien-mesa-20.0.2.aliensrc",
		"alien-pixman-0.38.4.aliensrc",
		"alien-v86d-0.1.10.aliensrc",
		"alien-wayland-1.18.0.aliensrc",
		"alien-weston-8.0.0.aliensrc",
		"alien-xkeyboard-config-2.28.aliensrc",
	]

	for p in packages:
		matcher.run(os.path.join(path, p))

from multiprocessing import Pool as MultiProcessingPool

class Cmd:

	def __init__(self, multi = False) -> None:
		self.multi = multi

	def exec(self, inputa):
		results = []
		if self.multi:
			mpool = MultiProcessingPool()
			results = mpool.map(
				self.run,
				inputa
			)
		else:
			for a in inputa:
				results.append(self.run(a))

		return results


class Cl(Cmd):

	def run(self, inp):
		print(inp)
		return inp+1

def test1():
	c = Cl(multi=True)
	r = c.exec(
		[1,2,3]
	)
	print(r)

	c = Cl(multi=False)
	r = c.exec(
		[1,2,3]
	)
	print(r)

if __name__ == "__main__":
	test1()
