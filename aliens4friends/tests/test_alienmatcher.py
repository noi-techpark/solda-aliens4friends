import os
from aliens4friends.alienmatcher import AlienMatcher, AlienMatcherError
from aliens4friends.commons.package import AlienPackage, PackageError

def test_all():
	pool_path = os.path.join(
		os.getcwd(),
		"tmp",
		"pool"
	)
	matcher = AlienMatcher(pool_path)

	path = os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA"
	)
	for filename in os.listdir(path):
		if not filename.endswith("aliensrc"):
			continue
		package_path = os.path.join(path, filename)
		try:
			print(f"{filename:<60}", end="")
			package = AlienPackage(package_path)
			debsrc_debian, debsrc_orig, errors = matcher.match(package)
			if debsrc_debian and debsrc_orig:
				print(f"{'MATCH':<10}{os.path.basename(debsrc_debian):<60}{os.path.basename(debsrc_orig):<60}{errors if errors else ''}")
			else:
				print(f"{'NO MATCH':<10}{'':<60}{'':<60}{errors if errors else 'FATAL: NO MATCH without errors'}")
		except (AlienMatcherError, PackageError) as ex:
			print(f"{'ERROR':<10}{'':<60}{'':<60}{ex}")



def test_single():
	package_path = os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA",
		"alien-file-5.38.aliensrc"
		# "alienlibusb1-1.0.22.tar.gz"
	)
	package = AlienPackage(package_path)
	pool_path = os.path.join(
		os.getcwd(),
		"tmp",
		"pool"
	)
	matcher = AlienMatcher(pool_path)
	matcher.match(package, True)
