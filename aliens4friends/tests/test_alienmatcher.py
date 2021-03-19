import os
from aliens4friends.alienmatcher import AlienMatcher, AlienMatcherError
from aliens4friends.commons.package import AlienPackage, PackageError, Package

def _setup():
	print(f"{'ALIENSRC':<80}{'OUTCOME':<10}{'DEBSRC_DEBIAN':<60}{'DEBSRC_ORIG':<60}ERRORS")
	print("-"*300)
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
		print(f"{filename:<80}", end="")
		package = AlienPackage(os.path.join(package_path, filename))
		debsrc_debian, debsrc_orig, errors = matcher.match(package)
		debsrc_debian = os.path.basename(debsrc_debian) if debsrc_debian else ''
		debsrc_orig = os.path.basename(debsrc_orig) if debsrc_orig else ''
		outcome = 'MATCH' if debsrc_debian or debsrc_orig else 'NO MATCH'
		if not debsrc_debian and not debsrc_orig and not errors:
			errors = 'FATAL: NO MATCH without errors'
		print(f"{outcome:<10}{debsrc_debian:<60}{debsrc_orig:<60}{errors if errors else ''}")
	except (AlienMatcherError, PackageError) as ex:
		if str(ex) == "No internal archive":
			print(f"{'IGNORED':<10}{'':<60}{'':<60}{ex}")
		elif str(ex) == "Can't find a similar package on Debian repos":
			print(f"{'NO MATCH':<10}{'':<60}{'':<60}{ex}")
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
	_run(matcher, path, "alien-libxkbcommon-0.10.0.aliensrc")

def test_search():
	matcher, path = _setup()
	# package = AlienPackage(os.path.join(path, "alien-libmodulemd-v1-1.8.16.aliensrc"))
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
		_run(matcher, path, p)
