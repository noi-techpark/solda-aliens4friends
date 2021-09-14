# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

from aliens4friends.commons.session import Session, SessionError
import os
import logging
from uuid import uuid4
from multiprocessing import Pool as MultiProcessingPool

from spdx.file import File as SPDXFile
from spdx.utils import NoAssert, SPDXNone
from spdx.creationinfo import Tool
from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.document import Document as SPDXDocument

from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.utils import debug_with_stacktrace, md5, log_minimal_error
from aliens4friends.commons.spdxutils import parse_spdx_tv, write_spdx_tv, fix_spdxtv, EMPTY_FILE_SHA1

from aliens4friends.commons.pool import FILETYPE, Pool
from aliens4friends.commons.settings import Settings

from aliens4friends.models.alienmatcher import AlienMatcherModel, AlienSnapMatcherModel
from aliens4friends.models.deltacode import DeltaCodeModel

logger = logging.getLogger(__name__)

# proximity2debian levels
FULL_PROXIMITY = 1
NEARLY_FULL_PROXIMITY = 0.92
MIN_ACCEPTABLE_PROXIMITY = 0.3

class MakeAlienSPDXException(Exception):
	pass

class Scancode2AlienSPDX:

	def __init__(self, scancode_spdx: SPDXDocument, alien_package: AlienPackage):
		self._scancode_spdx = scancode_spdx
		self.alien_package = alien_package

	def set_package_and_document_metadata(self):
		self.alien_spdx.package.name = self.alien_package.name
		self.alien_spdx.package.version = self.alien_package.version.str
		self.alien_spdx.package.file_name = self.alien_package.archive_name
		self.alien_spdx.package.supplier = None
		self.alien_spdx.package.comment = self.alien_package.metadata.get('comment')
		self.alien_spdx.package.download_location = self.alien_package.internal_archive_src_uri
		self.alien_spdx.package.verif_code = self.alien_spdx.package.calc_verif_code()
		self.alien_spdx.package.spdx_id = f"SPDXRef-{self.alien_package.name}-{self.alien_package.version.str}"
		self.alien_spdx.namespace = (
			f"http://spdx.org/spdxdocs/{self.alien_package.name}-{self.alien_package.version.str}-{uuid4()}"
		)
		self.alien_spdx.name = f"{self.alien_package.name}-{self.alien_package.version.str}"
		self.alien_spdx.creation_info.creators = []
		self.alien_spdx.creation_info.add_creator(Tool(__name__))
		self.alien_spdx.creation_info.set_created_now()

	def process(self):
		self.alien_spdx = self._scancode_spdx
		for f in self.alien_spdx.files:
			if not f.chk_sum:
				f.chk_sum = SPDXAlgorithm("SHA1", EMPTY_FILE_SHA1)
			elif not f.chk_sum.value:
				f.chk_sum.value = EMPTY_FILE_SHA1
		self.set_package_and_document_metadata()


class Debian2AlienSPDX(Scancode2AlienSPDX):

	proximity: int  # pytype hint to resolve attribute-errors

	def __init__(self,
			scancode_spdx: SPDXDocument,
			alien_package: AlienPackage,
			debian_spdx: SPDXDocument,
			deltacodeng_results: DeltaCodeModel,
	):
		super().__init__(scancode_spdx, alien_package)
		self._debian_spdx = debian_spdx
		self.deltacodeng_results = deltacodeng_results

	def process(self):
		curpkg = f"{self.alien_package.name}-{self.alien_package.version.str}"
		results = self.deltacodeng_results.body
		deb_files2copy = (
			results.same_files
			+ results.changed_files_with_no_license_and_copyright
			+ results.changed_files_with_same_copyright_and_license
			+ list(results.changed_files_with_updated_copyright_year_only.keys())
		)
		self.calc_proximity()
		if self.proximity < MIN_ACCEPTABLE_PROXIMITY:
			logger.warning(
				f"[{curpkg}] proximity with debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
				f" is too low ({int(self.proximity*100)}%),"
				 " using scancode spdx instead"
			)
			super().process()
			return
		# TODO handle also moved_files
		deb_spdx_files = { f.name[2:]: f for f in self._debian_spdx.package.files }
		scancode_spdx_files = { f.name[2:]: f for f in self._scancode_spdx.package.files }
		# f.name[2:] strips initial './'
		alien_spdx_files = []
		alien_files_sha1s = self.alien_package.internal_archive_checksums
		for alien_spdx_file, alien_file_sha1 in alien_files_sha1s.items():
			name = f'./{alien_spdx_file}'
			if alien_spdx_file in deb_files2copy:
				if alien_spdx_file in deb_spdx_files:
					deb2alien_file = deb_spdx_files[alien_spdx_file]
					deb2alien_file.chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1)
					scancode_spdx_file = scancode_spdx_files.get(alien_spdx_file)
					if scancode_spdx_file:
						if alien_spdx_file in results.changed_files_with_updated_copyright_year_only:
							deb2alien_file.copyright = scancode_spdx_file.copyright
						deb2alien_file.licenses_in_file = scancode_spdx_file.licenses_in_file
						if type(scancode_spdx_file.licenses_in_file[0]) in [ NoAssert, SPDXNone, type(None) ]:
							deb2alien_file.conc_lics = NoAssert()
							# if there are no copyright/license statements in
							# file, do not apply decisions from debian/copyright
							# in order to be consistent with Fossology's "style"
					else:
						raise MakeAlienSPDXException(
							 "Something's wrong, can't find"
							f" {alien_spdx_file} in scancode spdx file"
						)

					alien_spdx_files.append(deb2alien_file)
				else:
					raise MakeAlienSPDXException(
						f"Something's wrong, can't find {alien_spdx_file} in SPDX doc"
					)
			elif scancode_spdx_files.get(alien_spdx_file):
				alien_file = scancode_spdx_files[alien_spdx_file]
				alien_file.spdx_id = f'SPDXRef-file-{md5(name)}'
				alien_spdx_files.append(alien_file)
			else:
				alien_file = SPDXFile(
					name = name,
					chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1),
					spdx_id=f'SPDXRef-file-{md5(name)}',
				)
				alien_file.conc_lics=NoAssert()
				alien_file.licenses_in_file=[NoAssert(),]
				alien_file.copyright=NoAssert()
				alien_spdx_files.append(alien_file)
		self.alien_spdx = self._debian_spdx
		self.alien_spdx.package.files = alien_spdx_files
		if self.proximity < NEARLY_FULL_PROXIMITY:
			logger.info(
				f"[{curpkg}] proximity is not ~100%, do not apply main package"
				 " license(s) from debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
			)
			# do not apply debian main license and copyright
			# if proximity is not ~100%
			self.alien_spdx.package.license_declared = NoAssert()
			self.alien_spdx.package.conc_lics = NoAssert()
		if self.proximity < FULL_PROXIMITY:
			logger.info(
				f"[{curpkg}] proximity is not ==100%, do not apply global package"
				" license and copyright metadata from debian package"
				f" {self._debian_spdx.package.name}-{self._debian_spdx.package.version}"
			)
			# TODO the following metadata would need to be regenerated
			# we set them to NOASSERTION for now
			self.alien_spdx.package.licenses_from_files = [NoAssert(),]
			self.alien_spdx.package.cr_text = NoAssert()
		self.set_package_and_document_metadata()


	def calc_proximity(self) -> None:
		s = self.deltacodeng_results.header.stats
		similar = (
			s.same_files
			+ s.moved_files
			+ s.changed_files_with_no_license_and_copyright
			+ s.changed_files_with_same_copyright_and_license
			+ s.changed_files_with_updated_copyright_year_only
		)
		different = (
			s.changed_files_with_changed_copyright_or_license
			+ s.new_files_with_license_or_copyright
		)
		self.proximity = int(similar / (similar + different))
		# excluding deleted files and new files with no license/copyright from
		# the count, on purpose, because here the need is to have  a criterion
		# to decide whether to apply debian/copyright metadata to the
		# alienpackage's matching files and to the alienpackage as a whole


class MakeAlienSPDX:

	@staticmethod
	def execute(
		pool: Pool,
		glob_name: str = "*",
		glob_version: str = "*",
		use_oldmatcher: bool = False,
		session_id: str = ""
	) -> None:

		filetype = FILETYPE.ALIENMATCHER if use_oldmatcher else FILETYPE.SNAPMATCH

		# Just take packages from the current session list
		# On error just return, error messages are inside load()
		if session_id:
			try:
				session = Session(pool, session_id)
				session.load()
				paths = session.package_list_paths(filetype)
			except SessionError:
				return

		# ...without a session_id, take information directly from the pool
		else:
			paths = pool.absglob(f"{glob_name}/{glob_version}/*.{filetype}")

		multiprocessing_pool = MultiProcessingPool()
		multiprocessing_pool.map(
			MakeAlienSPDX._execute,
			[
				[path, use_oldmatcher, pool] for path in paths
			]
		)

	@staticmethod
	def _execute(args):

		path, use_oldmatcher, pool = args

		name, version = pool.packageinfo_from_path(path)
		package = f"{name}-{version}"

		try:
			if use_oldmatcher:
				model = AlienMatcherModel.from_file(path)
			else:
				model = AlienSnapMatcherModel.from_file(path)
		except Exception as ex:
			logger.error(f"[{package}] Unable to load json from {pool.clnpath(path)}.")
			debug_with_stacktrace(logger)
			return

		try:
			if model.errors and 'No internal archive' in model.errors:
				logger.warning(f"[{package}] No internal archive in aliensrc package, skipping")
				return
			alien = model.aliensrc
			alien_spdx_filename = pool.abspath(
				Settings.PATH_USR,
				alien.name,
				alien.version,
				f'{alien.internal_archive_name}.alien.spdx'
			)
			if os.path.isfile(alien_spdx_filename) and Settings.POOLCACHED:
				logger.debug(f"[{package}] {pool.clnpath(alien_spdx_filename)} already found in cache, skipping")
				return
			alien_package_filename = pool.abspath(
				Settings.PATH_USR,
				alien.name,
				alien.version,
				alien.filename
			)
			scancode_spdx_filename = pool.abspath_typed(FILETYPE.SCANCODE, alien.name, alien.version)
			fix_spdxtv(scancode_spdx_filename)
			scancode_spdx, _ = parse_spdx_tv(scancode_spdx_filename)
			alien_package = AlienPackage(alien_package_filename)
			alien_package.expand(get_internal_archive_checksums=True)

			deltacodeng_results_filename = ""
			debian_spdx_filename = ""

			match = model.match

			if match.name:
				deltacodeng_results_filename = pool.abspath_typed(FILETYPE.DELTACODE, alien.name, alien.version)
				debian_spdx_filename = pool.abspath_typed(FILETYPE.DEBIAN_SPDX, match.name, match.version)

			if (
				os.path.isfile(deltacodeng_results_filename)
				and os.path.isfile(debian_spdx_filename)
			):
				logger.info(f"[{package}] Applying debian spdx to package {alien.name}-{alien.version}")
				fix_spdxtv(debian_spdx_filename)
				debian_spdx, _ = parse_spdx_tv(debian_spdx_filename)
				deltacodeng_results = DeltaCodeModel.from_file(deltacodeng_results_filename)
				d2as = Debian2AlienSPDX(
					scancode_spdx,
					alien_package,
					debian_spdx,
					deltacodeng_results
				)
				d2as.process()
				write_spdx_tv(d2as.alien_spdx, alien_spdx_filename)
			else:
				logger.warning(f"[{package}] No debian spdx available, using scancode spdx for package {alien.name}-{alien.version}")
				s2as = Scancode2AlienSPDX(scancode_spdx, alien_package)
				s2as.process()
				write_spdx_tv(s2as.alien_spdx, alien_spdx_filename)
		except Exception as ex:
			log_minimal_error(logger, ex, f"[{package}] ")
