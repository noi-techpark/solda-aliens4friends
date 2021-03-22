import os

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
