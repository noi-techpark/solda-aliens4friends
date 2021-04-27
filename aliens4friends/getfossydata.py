# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import os
import re
import json
import tempfile
import logging
from uuid import uuid4
from typing import Optional

from spdx.document import Document as SPDXDocument
from spdx.package import Package as SPDXPackage
from spdx.creationinfo import Tool
from spdx.document import License as SPDXLicense

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.utils import bash
from aliens4friends.commons.settings import Settings
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.fossywrapper import FossyWrapper
from aliens4friends.commons.spdxutils import parse_spdx_tv, write_spdx_tv

logger = logging.getLogger(__name__)

# FIXME do not hardcode it!
SPDX_DISCLAIMER = """
This SPDX file is provided for convenience only in connection with open source
software projects published by OpenHarmonyOS Working Group (OHOS). The
information provided herein has the sole purpose to describe the bill of
materials of a component of one or more of such projects and does not constitute
legal advice nor is it intended to be used for rendering legal advice. Reuse of
this file is permitted for any possible scope and purpose, under the condition
that the name of OHOS as maker of the document must be removed.
"""

GPL_RENAME = {
	"GPL-1.0" : "GPL-1.0-only",
	"GPL-1.0+" : "GPL-1.0-or-later",
	"GPL-2.0" : "GPL-2.0-only",
	"GPL-2.0+" : "GPL-2.0-or-later",
	"GPL-3.0" : "GPL-3.0-only",
	"GPL-3.0+" : "GPL-3.0-or-later",
	"LGPL-2.0" : "LGPL-2.0-only",
	"LGPL-2.0+" : "LGPL-2.0-or-later",
	"LGPL-2.1" : "LGPL-2.1-only",
	"LGPL-2.1+" : "LGPL-2.1-or-later",
	"LGPL-3.0" : "LGPL-3.0-only",
	"LGPL-3.0+" : "LGPL-3.0-or-later",
	"LicenseRef-LPGL-2.1-or-later": "LicenseRef-LGPL-2.1-or-later",
}

GPL_LICS = [
	"GPL-1.0-only",
	"GPL-1.0-or-later",
	"GPL-2.0-only",
	"GPL-2.0-or-later",
	"GPL-3.0-only",
	"GPL-3.0-or-later",
	"LGPL-2.0-only",
	"LGPL-2.0-or-later",
	"LGPL-2.1-only",
	"LGPL-2.1-or-later",
	"LGPL-3.0-only",
	"LGPL-3.0-or-later",
	"LPGL-2.1-or-later", # bugfix, just to remove misspelled extracted_licenses
]


class GetFossyDataException(Exception):
	pass


class GetFossyData:

	def __init__(
		self,
		fossy: FossyWrapper,
		alien_package: AlienPackage,
		alien_spdx_filename: Optional[str] = None
	):
		self.pkg = SPDXPackage()
		self.pkg.comment = ""
		self.fossy = fossy
		self.upload = self.fossy.get_upload(
			alien_package.name, alien_package.version.str
		)
		if not self.upload:
			raise GetFossyDataException(
				f"upload {alien_package.name}@{alien_package.version.str}"
				 " does not exist"
			)
		if alien_spdx_filename:
			self.alien_spdx_doc, _ = parse_spdx_tv(alien_spdx_filename)
			self.pkg.download_location = self.alien_spdx_doc.package.download_location
			if self.alien_spdx_doc.package.comment:
				self.pkg.comment = self.alien_spdx_doc.package.comment
			if (
					self.alien_spdx_doc.package.originator
					and hasattr(self.alien_spdx_doc.package.originator, "name")
					and self.alien_spdx_doc.package.originator.name
					and self.alien_spdx_doc.package.originator.name != "None"
			):
				self.pkg.originator = self.alien_spdx_doc.package.originator
			if self.alien_spdx_doc.package.homepage:
				self.pkg.homepage = self.alien_spdx_doc.package.homepage
		else:
			self.alien_spdx_doc = None
		self.pkg.name = alien_package.name
		self.pkg.version = alien_package.version.str
		# overrides
		keys = [ "homepage", "summary", "description" ]
		for key in keys:
			if alien_package.metadata.get(key):
				setattr(self.pkg, key, alien_package.metadata[key])

	def get_spdx(self):
		self.doc = self.fossy.get_spdxtv(self.upload)
		for attr, value in vars(self.pkg).items():
			if value:
				setattr(self.doc.package, attr, value)
		self.doc.namespace = (
			f"http://spdx.org/spdxdocs/" f"{self.pkg.name}-{self.pkg.version}-{uuid4()}"
		)
		self.doc.name = f"{self.pkg.name}-{self.pkg.version}"
		self.doc.creation_info.comment = (
			"\nThis doc was created using license information "
			"from Fossology and Scancode.\n"
		)
		if self.alien_spdx_doc and self.alien_spdx_doc.creation_info.comment:
			self.doc.creation_info.comment += f"\n{self.alien_spdx_doc.creation_info.comment}\n"
		self.doc.creation_info.comment += SPDX_DISCLAIMER
		stdout, stderr = bash("scancode --version")
		scancode_version = stdout.replace("ScanCode version ", "").replace("\n", "")
		self.doc.package.license_comment = re.sub(
			r"reportImport \([^\)]+\)",
			f"scancode ({scancode_version})",
			self.doc.package.license_comment,
		)
		self.doc.creation_info.creators = []
		self.doc.creation_info.add_creator(Tool("aliens4friends"))
		for i, file in enumerate(self.doc.package.files):
			self.doc.package.files[i].name = self.doc.package.files[i].name.replace(
				f"{self.upload.uploadname}/", f"./"
			)
		self.doc.package.verif_code = self.doc.package.calc_verif_code()
		logger.info(f"[{self.upload.uploadname}] saving spdx report")
		self._fix_fossy_spdx(self.doc)
		return self.doc

	@staticmethod
	def _fix_fossy_lic(license):
		if not isinstance(license, SPDXLicense):
			return license
		identifier = license.identifier
		identifier = identifier.replace("LicenseRef-LicenseRef", "LicenseRef")
		identifier = identifier.replace(" AND NOASSERTION", "")
		words = identifier.split(" ")
		for i, word in enumerate(words):
			for search, replace in GPL_RENAME.items():
				if word == search:
					words[i] = replace
					word = replace # fix LPGL->LGPL
			for gpl_lic in GPL_LICS:
				if word == f"LicenseRef-{gpl_lic}":
					words[i] = gpl_lic
		identifier = " ".join(words)
		return SPDXLicense.from_identifier(identifier)

	@staticmethod
	def _fix_fossy_spdx(doc):
		cls = GetFossyData
		pkg = doc.package
		pkg.conc_lics = cls._fix_fossy_lic(pkg.conc_lics)
		pkg.license_declared = cls._fix_fossy_lic(pkg.license_declared)
		if isinstance(pkg.licenses_from_files, list):
			for i, l in enumerate(pkg.licenses_from_files):
				pkg.licenses_from_files[i] = cls._fix_fossy_lic(l)
		if isinstance(pkg.files, list):
			for f in pkg.files:
				f.conc_lics = cls._fix_fossy_lic(f.conc_lics)
				if isinstance(f.licenses_in_file, list):
					for i, l in enumerate(f.licenses_in_file):
						f.licenses_in_file[i] = cls._fix_fossy_lic(l)
		if (
			hasattr(doc, "extracted_licenses")
			and isinstance(doc.extracted_licenses, list)
		):
			to_remove = [ f"LicenseRef-{id}" for id in GPL_LICS ]
			doc.extracted_licenses = [
				el for el in doc.extracted_licenses
				if el.identifier not in to_remove
			]

	def get_metadata_from_fossology(self):
		"""get summary and license findings and conclusions from fossology"""
		logger.info(f"[{self.upload.uploadname}] getting metadata from fossology")
		summary = self.fossy.get_summary(self.upload)
		licenses = self.fossy.get_license_findings_conclusions(self.upload)
		return {
			"origin": Settings.FOSSY_SERVER,
			"summary": summary,
			"licenses": licenses
		}

	@staticmethod
	def execute(pool: Pool, glob_name: str = "*", glob_version: str = "*"):
		fossy = FossyWrapper()
		# FIXME: add some control to log a message if no path is found
		# (pool.absglob doesn't return a list, and you can iterate it only once)
		for path in pool.absglob(f"userland/{glob_name}/{glob_version}/*.aliensrc"):
			package = f"{path.parts[-3]}-{path.parts[-2]}"
			out_spdx_filename = pool.abspath(
				"userland",
				path.parts[-3],
				path.parts[-2],
				f'{package}.final.spdx'
			)
			if os.path.isfile(out_spdx_filename) and Settings.POOLCACHED:
				logger.info(f"[{package}] fossy spdx already generated, skipping")
				continue
			try:
				apkg = AlienPackage(path)
				apkg_fullname = f'{apkg.name}-{apkg.version.str}'
			except Exception as ex:
				logger.error(f"[{package}] Unable to load aliensrc from {path},"
				f" got {ex.__class__.__name__}: {ex}")
				continue
			if not apkg.package_files:
				logger.info(f"[{package}] this is a metapackage with no files, skipping")
				continue
			try:
				alien_spdx = [
					p for p in pool.absglob(
						f"userland/{apkg.name}/{apkg.version.str}/*.alien.spdx"
					)
				]
				if len(alien_spdx) == 0:
					alien_spdx_filename = None
				elif len(alien_spdx) == 1:
					alien_spdx_filename = alien_spdx[0]
					logger.info(f"[{package}] using {alien_spdx_filename}")
				else:
					raise GetFossyDataException(
						f"[{package}] Something's wrong, more than one alien spdx"
						f" file found in pool: {alien_spdx}"
					)
				alien_fossy_json_filename = pool.abspath(
					"userland",
					apkg.name,
					apkg.version.str,
					f'{apkg_fullname}.fossy.json'
				)
				logger.info(f"[{package}] getting spdx and json data from Fossology")
				gfd = GetFossyData(fossy, apkg, alien_spdx_filename)
				doc = gfd.get_spdx()
				write_spdx_tv(doc, out_spdx_filename)
				fossy_json = gfd.get_metadata_from_fossology()
				with open(alien_fossy_json_filename, "w") as f:
					json.dump(fossy_json, f)

			except Exception as ex:
				logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
