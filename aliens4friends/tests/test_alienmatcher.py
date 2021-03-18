import os
from aliens4friends.alienmatcher import AlienMatcher, AlienMatcherError, VERSION
from aliens4friends.commons.package import AlienPackage, PackageError

def test_all():
	print("#" * 100)
	print(f"### ALIENMATCHER v{VERSION}")
	print("#" * 100)

	path = os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA2"
	)
	for filename in os.listdir(path):
		if not filename.endswith("aliensrc"):
			continue
		package_path = os.path.join(path, filename)
		try:
			package = AlienPackage(package_path)
			pool_path = os.path.join(
				os.getcwd(),
				"tmp",
				"pool"
			)
			matcher = AlienMatcher(pool_path)
			matcher.match(package)
		except (AlienMatcherError, PackageError) as ex:
			print("#" * 100)
			print(f"ERROR: {filename} not matchable! --> {ex}")
			print("#" * 100)

def test_single():
	print("#" * 100)
	print(f"### ALIENMATCHER v{VERSION}")
	print("#" * 100)

	package_path = os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA2",
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
