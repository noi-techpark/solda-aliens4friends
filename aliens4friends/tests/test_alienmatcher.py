import os
from aliens4friends.alienmatcher import AlienMatcher, AlienMatcherError
from aliens4friends.commons.package import AlienPackage, PackageError

def _setup():
	return AlienMatcher(
		os.path.join(
			os.getcwd(),
			"tmp",
			"pool"
		)
	), os.path.join(
		os.getcwd(),
		"tmp",
		"alberto",
		"SCA"
	)

def _run(matcher, package_path, filename):
	try:
		print(f"{filename:<60}", end="")
		package = AlienPackage(package_path)
		debsrc_debian, debsrc_orig, errors = matcher.match(package)
		if debsrc_debian and debsrc_orig:
			print(f"{'MATCH':<10}{os.path.basename(debsrc_debian):<60}{os.path.basename(debsrc_orig):<60}{errors if errors else ''}")
		else:
			print(f"{'NO MATCH':<10}{'':<60}{'':<60}{errors if errors else 'FATAL: NO MATCH without errors'}")
	except (AlienMatcherError, PackageError) as ex:
		if ex == "No internal archive":
			print(f"{'IGNORED':<10}{'':<60}{'':<60}{ex}")
		else:
			print(f"{'ERROR':<10}{'':<60}{'':<60}{ex}")


def test_all():
	matcher, path = _setup()
	for filename in os.listdir(path):
		if not filename.endswith("aliensrc"):
			continue
		_run(matcher, path, filename)


def test_single():
	matcher, path = _setup()
	_run(matcher, path, "alien-gtk+3-3.24.14.aliensrc")
