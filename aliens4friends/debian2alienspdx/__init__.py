# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import json
from uuid import uuid4

from spdx.file import File as SPDXFile
from spdx.utils import NoAssert
from spdx.creationinfo import Tool
from spdx.checksum import Algorithm as SPDXAlgorithm
from spdx.document import Document as SPDXDocument

from aliens4friends.commons.archive import Archive
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.utils import md5
from aliens4friends.commons.spdxutils import parse_spdx_tv, write_spdx_tv

def debian2alienspdx(
		debian_spdx: SPDXDocument,
		deltacodeng_results: dict,
		alien_package: AlienPackage
):
	"""Function to filter an SPDX Document object according to deltacodeng
	results and produce a new SPDX Document object that applies SPDX Document
	license and copyright metadata only to files with unchanged copyright and
	license statements, and puts NOASSERTION on the oter files
	"""
	results = deltacodeng_results["body"]
	deb_files2copy = (
		results['same_files']
		+ results['changed_files_with_no_license_and_copyright']
		+ results['changed_files_with_same_copyright_and_license']
	)
	# TODO handle also moved_files and changed_files_with_updated_copyright_year_only
	deb_spdx_files = { f.name[2:]: f for f in debian_spdx.package.files }
		# f.name[2:] strips initial './'
	alien_spdx_files = []
	alien_files_sha1s = alien_package.internal_archive_checksums
	for alien_spdx_file, alien_file_sha1 in alien_files_sha1s.items():
		if alien_spdx_file in deb_files2copy:
			if alien_spdx_file in deb_spdx_files:
				deb2alien_file = deb_spdx_files[alien_spdx_file]
				deb2alien_file.chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1)
				alien_spdx_files.append(deb2alien_file)
			else:
				raise Exception(
					f"Something's wrong, can't find {alien_spdx_file} in SPDX doc"
				)
		else:
			name = f'./{alien_spdx_file}'
			alien_file = SPDXFile(
				name = name,
				chk_sum = SPDXAlgorithm("SHA1", alien_file_sha1),
				spdx_id=f'SPDXRef-file-{md5(name)}',
			)
			alien_file.conc_lics=NoAssert()
			alien_file.licenses_in_file=[NoAssert(),]
			alien_file.copyright=NoAssert()
			alien_spdx_files.append(alien_file)
	alien_spdx = debian_spdx
	alien_spdx.package.files = alien_spdx_files
	alien_spdx.package.name = alien_package.name
	alien_spdx.package.version = alien_package.version.str
	alien_spdx.package.file_name = alien_package.archive_name
	alien_spdx.package.supplier = None
	alien_spdx.package.comment = alien_package.metadata.get('comment')
	alien_spdx.package.download_location = alien_package.internal_archive_src_uri
	alien_spdx.package.verif_code = alien_spdx.package.calc_verif_code()
	alien_spdx.package.spdx_id = f"SPDXRef-{alien_package.name}-{alien_package.version.str}"
	alien_spdx.namespace = (
		f"http://spdx.org/spdxdocs/{alien_package.name}-{alien_package.version.str}-{uuid4()}"
	)
	alien_spdx.name = f"{alien_package.name}-{alien_package.version.str}"
	alien_spdx.creation_info.creators = []
	alien_spdx.creation_info.add_creator(Tool(__name__))
	alien_spdx.creation_info.set_created_now()
	return alien_spdx

def debian2alienspdx_files(
		debian_spdx_filename: str,
		deltacodeng_results_filename: str,
		alien_package_filename: str,
		alien_spdx_filename: str
):
	debian_spdx, err = parse_spdx_tv(debian_spdx_filename)
	with open(deltacodeng_results_filename, 'r') as f:
		deltacodeng_results = json.load(f)
	alien_package = AlienPackage(alien_package_filename)
	alien_debian_spdx = debian2alienspdx(
		debian_spdx,
		deltacodeng_results,
		alien_package
	)
	write_spdx_tv(alien_debian_spdx, alien_spdx_filename)
