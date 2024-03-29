# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

# Class to process a debian source package and generate an SPDX file out of its
# debian/control file
#
# It is based on DEP5 specs and SPDX specs:
# https://www.debian.org/doc/debian-policy/ch-controlfields.html
# https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
# https://spdx.github.io/spdx-spec/

import logging
from typing import Dict, List, Optional, Tuple, Type, Union
from uuid import uuid4

from debian.changelog import Changelog as DebChangelog
from debian.copyright import Copyright as DebCopyright
from debian.copyright import License as DebLicense
from debian.copyright import (MachineReadableFormatError,
                              NotMachineReadableError)
from debian.deb822 import Deb822
from flanker.addresslib import address as email_address
from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.config import LICENSE_MAP as SPDX_LICENSE_MAP
from spdx.creationinfo import CreationInfo as SPDXCreationInfo
from spdx.creationinfo import Organization, Tool
from spdx.document import Document as SPDXDocument
from spdx.document import ExtractedLicense as SPDXExtractedLicense
from spdx.document import License as SPDXLicense
from spdx.file import File as SPDXFile
from spdx.package import Package as SPDXPackage
from spdx.utils import NoAssert, SPDXNone
from spdx.version import Version as SPDXVersion
from spdx.writers.tagvalue import write_document

from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import md5

logger = logging.getLogger(__name__)

# Conversion table from DEP5 to SPDX license identifiers
# https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/#license-specification
# https://spdx.org/licenses/
# Note 1: In DEP5 specs, license identifiers are case insensitive (see sec.7.2).
# Note 2: Already matching identifiers between DEP5 and SPDX are not included

DEB2SPDX_IDENTIFIERS = {
	# deb_shortname_lowercase: corresponding_spdx_license_identifier
	"apache": "Apache-1.0",
	"artistic": "Artistic-1.0",
	"cc-by": "CC-BY-1.0",
	"cc-by-sa": "CC-BY-SA-1.0",
	"cc-by-nd": "CC-BY-ND-1.0",
	"cc-by-nc": "CC-BY-NC-1.0",
	"cc-by-nc-sa": "CC-BY-NC-SA-1.0",
	"cc-by-nc-nd": "CC-BY-NC-ND-1.0",
	"cc0": "CC0-1.0",
	"cddl": "CDDL-1.0",
	"cpl": "CPL-1.0",
	"efl": "EFL-1.0",
	"expat": "MIT",
	"gpl": "GPL-1.0-only",
	"gpl-1.0": "GPL-1.0-only",
	"gpl-1": "GPL-1.0-only",
	"gpl-1.0+": "GPL-1.0-or-later",
	"gpl-1+": "GPL-1.0-or-later",
	"gpl-2.0": "GPL-2.0-only",
	"gpl-2": "GPL-2.0-only",
	"gpl-2.0+": "GPL-2.0-or-later",
	"gpl-2+": "GPL-2.0-or-later",
	"gpl-3.0": "GPL-3.0-only",
	"gpl-3": "GPL-3.0-only",
	"gpl-3.0+": "GPL-3.0-or-later",
	"gpl-3+": "GPL-3.0-or-later",
	"lgpl": "LGPL-2.0-only",
	"lgpl-2.0": "LGPL-2.0-only",
	"lgpl-2": "LGPL-2.0-only",
	"lgpl-2.0+": "LGPL-2.0-or-later",
	"lgpl-2+": "LGPL-2.0-or-later",
	"lgpl-2.1": "LGPL-2.1-only",
	"lgpl-2.1+": "LGPL-2.1-or-later",
	"lgpl-3.0": "LGPL-3.0-only",
	"lgpl-3": "LGPL-3.0-only",
	"lgpl-3.0+": "LGPL-3.0-or-later",
	"lgpl-3+": "LGPL-3.0-or-later",
	"gfdl": "GFDL-1.1-only",
	"gfdl-1.1": "GFDL-1.1-only",
	"gfdl-1.1+": "GFDL-1.1-or-later",
	"gfdl-1.2": "GFDL-1.2-only",
	"gfdl-1.2+": "GFDL-1.2-or-later",
	"gfdl-1.3": "GFDL-1.3-only",
	"gfdl-1.3+": "GFDL-1.3-or-later",
	# FIXME upstream:
	# the following SPDX license identifiers are missing in the
	# LICENSE_MAP imported from spdx.config as SPDX_LICENSE_MAP
	# 'gfdl-niv': 'GFDL-1.1-no-invariants-only',
	# 'gfdl-niv-1.1': 'GFDL-1.1-no-invariants-only',
	# 'gfdl-niv-1.1+': 'GFDL-1.1-no-invariants-or-later',
	# 'gfdl-niv-1.2': 'GFDL-1.2-no-invariants-only',
	# 'gfdl-niv-1.2+': 'GFDL-1.2-no-invariants-or-later',
	# 'gfdl-niv-1.3': 'GFDL-1.3-no-invariants-only',
	# 'gfdl-niv-1.3+': 'GFDL-1.3-no-invariants-or-later',
	"lppl": "LPPL-1.0",
	"mpl": "MPL-1.1",
	"perl": "Artistic-1.0-Perl",
	"python": "Python-2.0",
	"qpl": "QPL-1.0",
	"zope-1.1": "ZPL-1.1",
	"zope-2.0": "ZPL-2.0",
	"zope-2.1": "ZPL-2.1",
}

# SPDX license map has both identifiers and full names as keys, we want only
# a case insensitive map of identifiers
SPDX_LICENSE_IDS = {k.lower(): k for k in SPDX_LICENSE_MAP if " " not in k}


# default text to use as ExtractedText for public domain in SPDX files
PUBLIC_DOMAIN_TEXT = """Public domain software is software that is not copyrighted. If the source code is in the public domain, that is a special case of noncopylefted free software, which means that some copies or modified versions may not be free at all.

In some cases, an executable program can be in the public domain but the source code is not available. This is not free software, because free software requires accessibility of source code. Meanwhile, most free software is not in the public domain; it is copyrighted, and the copyright holders have legally given permission for everyone to use it in freedom, using a free software license.

Sometimes people use the term “public domain” in a loose fashion to mean “free” or “available gratis.” However, “public domain” is a legal term and means, precisely, “not copyrighted”. For clarity, we recommend using “public domain” for that meaning only, and using other terms to convey the other meanings.

Under the Berne Convention, which most countries have signed, anything written down is automatically copyrighted. This includes programs. Therefore, if you want a program you have written to be in the public domain, you must take some legal steps to disclaim the copyright on it; otherwise, the program is copyrighted."""


def get_spdx_license(deb_shortname: str) -> Union[str, None]:
	"""Convert debian/copyright license shortname into SPDX license identifier
	:param deb_shortname: DEP5 license shortname
	:return: SPDX license identifier
	"""
	deb_shortname = deb_shortname.lower()
	spdx_lic_id = DEB2SPDX_IDENTIFIERS.get(deb_shortname) or deb_shortname
	return SPDX_LICENSE_IDS.get(spdx_lic_id.lower())
	# FIXME: we make an assumption here: if a custom license shortname in
	# debian copyright (not included in DEB2SPDX_IDENTIFIERS) corresponds to a
	# SPDX license identifier, it means that it refers to the same license.
	# This may not be always the case, in theory. Check in practice


def deb2spdx_lic_expr(deb_lic_expr: str) -> Tuple[str, List[str]]:
	"""Convert a debian/DEP5 license expression into an SPDX license expression
	f.e.
		GPL-2+ or Artistic-2.0, and BSD-3-clause
	is converted into:
		(GPL-2.0-or-later OR Artistic-2.0) AND BSD-3-Clause

	:param deb_lic_expr: DEP5 license expression
	:return: SPDX license expression, list of licenses included in expression
	"""
	# TODO: recognize spdx licenses also from license text provided
	# in debian/copyright (hash matching?)
	license_ids = []
	spdx_lic_expr = " ".join(deb_lic_expr.split())  # rm multiple spaces (if any)
	spdx_lic_expr = (
		spdx_lic_expr.replace(" or ", " OR ")
		.replace(" and ", " AND ")
		.replace(" with ", "-with-")
		.replace(" exception", "-exception")
		.replace(" Exception", "-exception")
	)
	if "," in spdx_lic_expr:
		spdx_lic_expr = "( " + spdx_lic_expr.replace(",", " ) ")
	elements = spdx_lic_expr.split()
	for i, v in enumerate(elements):
		if v not in ["(", ")", "OR", "AND"]:
			spdx_v = v.replace("+", "-or-later")
			elements[i] = get_spdx_license(v) or f"LicenseRef-{spdx_v}"
			license_ids.append(elements[i])
	spdx_lic_expr = " ".join(elements)
	spdx_lic_expr = spdx_lic_expr.replace("( ", "(").replace(" )", ")")
	return spdx_lic_expr, license_ids


class Debian2SPDXException(Exception):
	pass


class Debian2SPDX:

	# Type hints for attributes not declared in __init__
	deb_license_defs: dict

	"""Class to process a debian source pkg and generate an SPDX file out of it

	:Example:
		>>> from debian2spdx import Debian2SPDX
		>>> debsrc_orig = "./ffmpeg_4.1.6.orig.tar.xz"
		>>> debsrc_debian = "./ffmpeg_4.1.6-1~deb10u1.debian.tar.xz"
		>>> d2s = Debian2SPDX(debsrc_orig, debsrc_debian)
		>>> d2s.generate_SPDX()
		>>> d2s.write_SPDX("./ffmpeg_4.1.6.spdx")

	:param debsrc_orig:
		- quilt format: path of the original upstream source tarball
		- native format: path of the source tarball
	:param debsrc_debian:
		- quilt format: path of the debian folder tarball
		- native format: None
	:raises Debian2SPDXException: if any error occurs during data processing
	"""

	def __init__(self, debsrc_orig: str, debsrc_debian: Optional[str] = None) -> None:
		self.debarchive_orig = Archive(debsrc_orig)
		if debsrc_debian:
			self.native_rootdir = ''
			self.debarchive_debian = Archive(debsrc_debian)
		else: 	# native format
			self.native_rootdir = self.debarchive_orig.list()[0]
			self.debarchive_debian = self.debarchive_orig
		self.spdx_files: Dict[str, Type[SPDXFile]] = {}
		self.spdx_extracted_licenses: Dict[str, Type[SPDXExtractedLicense]] = {}
		self.deb_copyright = None
		self.deb_control = None
		self.deb_changelog = None
		self.deb_license_paragraphs = None
		self.catchall_deb_files = None
		self.spdx_pkg = None
		self.spdx_doc = None

	def get_files_sha1s(self) -> None:
		"""Use tar+sha1sum commands to generate a dict of SPDX File objects"""
		lines = self.debarchive_orig.checksums("")
		for path, sha1 in lines.items():
			spdx_file = SPDXFile(
				path,
				chk_sum=SPDXAlgorithm("SHA1", sha1),
				spdx_id=f'SPDXRef-file-{md5(path)}'
			)
			self.spdx_files.update({path: spdx_file})

	def parse_deb_copyright(self) -> bool:
		"""Extract and parse debian/copyright"""
		try:
			content = self.debarchive_debian.readfile(f"{self.native_rootdir}debian/copyright")
		except Exception as ex:
			if 'Not found in archive' in str(ex):
				raise Debian2SPDXException(
					"No Debian Copyright file found in debian source package"
				)
			else:
				raise ex
		try:
			self.deb_copyright = DebCopyright(content)
			self.deb_license_defs = {
				lp.license.synopsis: lp
				for lp in self.deb_copyright.all_license_paragraphs()
			}
			return True
		except (NotMachineReadableError, MachineReadableFormatError):
			logger.warning(
				"Debian Copyright file is not machine readable,"
				" can't convert it to SPDX"
			)
			return False

	def parse_deb_changelog(self) -> None:
		"""Extract and parse debian/changelog"""
		content = self.debarchive_debian.readfile(f"{self.native_rootdir}debian/changelog")
		self.deb_changelog = DebChangelog(content)

	def parse_deb_control(self) -> None:
		"""Extract and parse debian/control"""
		content = self.debarchive_debian.readfile(f"{self.native_rootdir}debian/control")
		self.deb_control = Deb822(content)

	def add_spdx_extracted_license(self, license_id: str, deb_license: DebLicense) -> None:
		"""Search for text of non-spdx licenses in debian/copyright (identified
		by the prefix 'LicenseRef-') and create SPDX extracted license object

		:param license_id: license id to process
		:param deb_license: debian license object where to possibly collect
			license text
		"""
		if (
			license_id.startswith("LicenseRef-")
			and license_id not in self.spdx_extracted_licenses
		):
			deb_shortname = license_id.replace("LicenseRef-", "").replace(
				"-or-later", "+"
			)
			extracted_license = SPDXExtractedLicense(license_id)
			if deb_license.text:
				extracted_license.text = deb_license.text
			elif deb_shortname in self.deb_license_defs:
				extracted_license.text = self.deb_license_defs[
					deb_shortname
				].license.text
				extracted_license.comment = self.deb_license_defs[deb_shortname].comment
			elif license_id == "LicenseRef-public-domain":
				extracted_license.text = PUBLIC_DOMAIN_TEXT
			else:
				extracted_license.text = "Dummy text (FIXME)"
				# FIXME log a warning here
			self.spdx_extracted_licenses.update({license_id: extracted_license})

	def process_deb_license_expr(self, deb_license: DebLicense) -> Tuple[SPDXLicense, List[SPDXLicense]]:
		"""convert debian license expression into SPDX license expression, and
		if there are any licenses not included in SPDX list, add them to SPDX
		document as extracted licenses
		"""
		deb_lic_expr = deb_license.synopsis
		spdx_lic_expr, license_ids = deb2spdx_lic_expr(deb_lic_expr)
		for license_id in license_ids:
			if license_id.startswith("LicenseRef-"):
				self.add_spdx_extracted_license(license_id, deb_license)
		spdx_conc_lics = SPDXLicense.from_identifier(spdx_lic_expr)
		return spdx_conc_lics

	def process_deb_files_and_license(self) -> bool:
		"""Process debian Files and License Paragraphs"""
		for deb_files in self.deb_copyright.all_files_paragraphs():
			try:
				spdx_conc_lics = self.process_deb_license_expr(
					deb_files.license
				)
			except MachineReadableFormatError as ex:
				logger.warning(
					"Debian Copyright file is not machine readable,"
					" can't convert it to SPDX"
				)
				return False
			pattern = deb_files.files_pattern()
			spdx_file_paths = list(filter(pattern.match, self.spdx_files))
			for path in spdx_file_paths:
				self.spdx_files[path].conc_lics = spdx_conc_lics
				self.spdx_files[path].licenses_in_file = [ NoAssert(), ]
				if deb_files.files != ("*",):
					self.spdx_files[path].copyright = deb_files.copyright
					# even if it is not compliant with DEP5 specs, sometimes
					# instead of putting package copyright info in
					# debian/copyright header, someone puts it into an initial
					# Files Paragraph with '*' pattern; this means that any file
					# that is not included in a Files Paragraph below the first
					# "catchall" File Paragraph ('*') gets all copyright
					# statements of the whole package, which is wrong!
				else:
					self.catchall_deb_files = deb_files
			return True

	def create_spdx_package(self) -> None:
		"""create SPDX Package object with package data taken from
		debian/copyright
		"""
		spdx_pkg = SPDXPackage()
		spdx_pkg.name = deb_pkg_name = self.deb_changelog.package
		spdx_pkg.version = upstream_ver = self.deb_changelog.upstream_version
		spdx_pkg.spdx_id = f"SPDXRef-{spdx_pkg.name}-{spdx_pkg.version}"
		spdx_pkg.file_name = f"{deb_pkg_name}_{upstream_ver}.orig.tar.xz"
		spdx_pkg.originator = Organization(
			self.deb_copyright.header.upstream_name,
			(
				self.deb_copyright.header.upstream_contact[0]
				if self.deb_copyright.header.upstream_contact
				else None
			),
		)
		a = email_address.parse(self.deb_control["Maintainer"])
		name = a.display_name if a else self.deb_control["Maintainer"]
		email = a.address if a else None
		spdx_pkg.supplier = Organization(name, email)
		pool_subdir = (
			spdx_pkg.name[:4] if spdx_pkg.name.startswith("lib") else spdx_pkg.name[:1]
		)
		url = "http://deb.debian.org/debian/pool/main"
		spdx_pkg.download_location = (
			f"{url}/{pool_subdir}/{deb_pkg_name}/{spdx_pkg.file_name}"
		)
		spdx_pkg.files_analyzed = True
		spdx_pkg.homepage = self.deb_control.get("Homepage")
		if self.deb_copyright.header.license:
			deb_license = self.deb_copyright.header.license
		elif self.catchall_deb_files:
			deb_license = self.catchall_deb_files.license
		else:
			raise Debian2SPDXException("No license declared in package")
		spdx_pkg.conc_lics = self.process_deb_license_expr(deb_license)
		if self.deb_copyright.header.copyright:
			spdx_pkg.cr_text = self.deb_copyright.header.copyright
		elif self.catchall_deb_files and self.catchall_deb_files.copyright:
			spdx_pkg.cr_text = self.catchall_deb_files.copyright
		else:
			raise Debian2SPDXException("No copyright declared in package")
		spdx_pkg.license_declared = spdx_pkg.conc_lics
		spdx_pkg.comment = self.deb_copyright.header.comment
		for path, spdx_file in self.spdx_files.items():
			spdx_file.name = f"./{spdx_file.name}"
			spdx_file.copyright = spdx_file.copyright or SPDXNone()
			spdx_pkg.add_file(spdx_file)
		spdx_pkg.verif_code = spdx_pkg.calc_verif_code()
		self.spdx_pkg = spdx_pkg

	def create_spdx_document(self) -> None:
		"""create SPDX Document object"""
		spdx_doc = SPDXDocument()
		spdx_doc.version = SPDXVersion(2, 2)
		spdx_doc.data_license = SPDXLicense.from_identifier("CC0-1.0")
		spdx_doc.name = f"{self.spdx_pkg.name}-{self.spdx_pkg.version}"
		spdx_doc.spdx_id = "SPDXRef-DOCUMENT"
		spdx_doc.namespace = (
			f"http://spdx.org/spdxdocs/"
			f"{self.spdx_pkg.name}-{self.spdx_pkg.version}-{uuid4()}"
		)
		spdx_doc.creation_info = SPDXCreationInfo()
		spdx_doc.creation_info.set_created_now()
		spdx_doc.creation_info.add_creator(Tool(__name__))
		spdx_doc.creation_info.comment = (
			"This doc was created using license information from debian source"
			f" package {self.spdx_pkg.name}-{self.deb_changelog.version}"
		)
		spdx_doc.package = self.spdx_pkg
		for id, extracted_license in self.spdx_extracted_licenses.items():
			spdx_doc.add_extr_lic(extracted_license)
		self.spdx_doc = spdx_doc

	def generate_SPDX(self) -> bool:
		"""main method: perform all processing operations to generate SPDX file
		from debian/copyright and original source tarball
		"""
		self.get_files_sha1s()
		if not self.parse_deb_copyright():
			return False
		self.parse_deb_changelog()
		self.parse_deb_control()
		if not self.process_deb_files_and_license():
			return False
		self.create_spdx_package()
		self.create_spdx_document()
		return True

	def write_SPDX(self, filename: Optional[str] = None) -> None:
		"""write SPDX Document object to file (in tagvalue format)"""
		filename = filename or f"{self.spdx_doc.name}.spdx"
		with open(filename, "w") as f:
			write_document(self.spdx_doc, f, validate=False)

	def write_debian_copyright(self, filename: str) -> None:
		"""export debian/copyright (useful if for instance it is not machine
		parseable and needs to be manually examined)"""
		try:
			content = self.debarchive_debian.readfile(f"{self.native_rootdir}debian/copyright")
		except Exception as ex:
			if 'Not found in archive' in str(ex):
				raise Debian2SPDXException(
					"No Debian Copyright file found in debian source package"
				)
			else:
				raise ex
		with open(filename, "w") as f:
			f.write("\n".join(content))
