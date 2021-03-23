import os
from pathlib import Path
import json

from aliens4friends.scancode import run_scancode
from aliens4friends.commons.pool import Pool
from aliens4friends.commons.archive import Archive

def test_single():
	pool = Pool(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	)

	package_name = "acl"
	package_version_str = "2.2.53-2"
	debsrc_debian = "acl_2.2.53-2.debian.tar.xz"

	archive_path = pool.abspath("debian", package_name, package_version_str, debsrc_debian)

	archive = Archive(archive_path)

	res = run_scancode(pool, archive, package_name, package_version_str)

	print(res)

def test_single_from_matcheroutput():
	pool = Pool(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	)

	for path in pool.absglob("*.alienmatcher.json"):
		try:
			with open(path, "r") as jsonfile:
				j = json.load(jsonfile)
			m = j["debian"]["match"]
			a = Archive(pool.abspath(m["debsrc_orig"]))
			run_scancode(pool, a, m["name"], m["version"])
		except Exception as ex:
			print(f"######### ERROR: {path} --> {ex} ###################################################")
