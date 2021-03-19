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
		print(f"{filename:<0}", end="")
		package = AlienPackage(os.path.join(package_path, filename))
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
	_run(matcher, path, "alien-python3-six-1.14.0.aliensrc")

def test_search():
	matcher, path = _setup()
	package = AlienPackage(os.path.join(path, "alien-python3-six-1.14.0.aliensrc"))
	package_match = matcher.search(package)
	print(package_match)

def test_list():
	matcher, path = _setup()

	packages = [
		"alien-libmodulemd-v1-1.8.16.aliensrc",
		"alien-libx11-compose-data-1.6.8.aliensrc",
		#"alien-linux-yocto-5.4.69+gitAUTOINC+7f765dcb29_cfcdd63145.aliensrc",
		"alien-openobex-1.7.2.aliensrc",
		"alien-opkg-utils-0.4.2.aliensrc",
		"alien-psplash-0.1+gitAUTOINC+0a902f7cd8.aliensrc",
		"alien-update-rc.d-0.8.aliensrc",
		"alien-wpa-supplicant-2.9.aliensrc"
	]

	for p in packages:
		_run(matcher, path, p)
