# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0

# These mappings are match aliases. That is, if the matchers find
# something on the key-side of this map, then it gets replaced by
# the value. This is useful, not to overcomplicate matching rules.
ALIASES = {
	"gtk+3": "gtk+3.0",
	"gmmlib": "intel-gmmlib",
	"libpcre2": "pcre2",
	"libusb1": "libusb-1.0",
	"libva-intel": "libva",
	"libxfont2": "libxfont",
	"linux-firmware": "firmware-nonfree",
	"linux-intel": "linux",
	"linux-seco-fslc": "linux",
	"linux-stm32mp": "linux",
	"linux-yocto": "linux",
	"python3": "python3.9",
	"systemd-boot": "systemd",
	"tcl": "tcl8.6",
	"xz": "xz-utils",
	"wpa-supplicant": "wpa",
	"zlib-intel": "zlib"
}

# Exclude these packages from Debian package searches, since we
# are sure that we will not find anything.
EXCLUSIONS = [
	"freertos-demo",
	"zephyr-philosophers",
	"ltp",
	"libpcre",
	"xserver-xorg",
	"which"
]
