import numpy

class Calc:

	KNOWN_PACKAGE_ALIASES = {
		"gtk+3": "gtk+3.0",
		"gmmlib": "intel-gmmlib",
		"libpcre": "doesnotexistindebian",
		"libpcre2": "pcre2",
		"libusb1": "libusb-1.0",
		"libva-intel": "libva",
		"libxfont2": "libxfont",
		"linux-firmware": "firmware-nonfree",
		"linux-intel": "linux",
		"linux-seco-fslc": "linux",
		"linux-stm32mp": "linux",
		"linux-yocto" : "linux",
		"ltp": "doesnotexistindebian",
		"systemd-boot": "systemd",
		"tcl": "tcl8.6",
		"xserver-xorg": "doesnotexistindebian",
		"xz": "xz-utils",
		"which": "doesnotexistindebian",
		"wpa-supplicant" : "wpa",
		"zlib-intel": "zlib",
	}

	@staticmethod
	def levenshtein(first, second):
		dist = numpy.zeros((len(first) + 1, len(second) + 1))

		# start values
		for f in range(len(first) + 1):
			dist[f][0] = f

		for s in range(len(second) + 1):
			dist[0][s] = s

		insert = 0
		delete = 0
		replace = 0

		for f in range(1, len(first)+1):
			for s in range(1, len(second)+1):
				if (first[f-1] == second[s-1]):
					dist[f][s] = dist[f-1][s-1]
				else:
					insert = dist[f][s-1]
					delete = dist[f-1][s]
					replace = dist[f-1][s-1]

					if (insert <= delete and insert <= replace):
						dist[f][s] = insert+1
					elif (delete <= insert and delete <= replace):
						dist[f][s] = delete+1
					else:
						dist[f][s] = replace+1

		res = dist[len(first)][len(second)];

		return res

	@staticmethod
	def _clean_name(name: str) -> str:
		return name.rstrip("0123456789.~+").replace("-v", "").replace("-", "")

	@staticmethod
	def fuzzyScore(given: str, new: str, aliases = {}) -> int:

		if given == new:
			return 100

		# Rename known packages to their Debian counterpart
		if given in aliases:
			given = aliases[given]

		if given == new:
			return 95

		g = Calc._clean_name(given)
		n = Calc._clean_name(new)

		if n == g:
			return 90

		# Prefixed with the abbreviation isc- (Internet Software Consortium)
		# Possibly postfixed with -client or -server
		if n.startswith(f"isc{g}"):
			return 80

		# Some libraries may lack a lib prefix
		if (
			(g.startswith("lib") or n.startswith("lib"))
			and g.replace("lib", "") == n.replace("lib", "")
		):
			return 70

		# Major Python version mismatch: python3-iniparse vs. python-iniparse
		# Some python packages do not have a python[23]- prefix
		if (
			n.startswith("python3")
			or g.startswith("python3")
		):
			nn = n.replace("python3", "python")
			gg = g.replace("python3", "python")
			if nn == gg:
				return 70
			if nn.replace("python", "") == gg.replace("python", ""):
				return 60

		# Fonts may start with "fonts-" in Debian
		if g.replace("fonts", "") == n.replace("fonts", ""):
			return 60

		# Library/API version at the end of the package name
		if n.startswith(g):
			return 50

		# --> Not matching at all
		return 0
