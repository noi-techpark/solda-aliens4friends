# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import os
import re
from uuid import uuid4
from typing import Tuple

from spdx.parsers.tagvalue import Parser as SPDXTagValueParser
from spdx.parsers.tagvaluebuilders import Builder as SPDXTagValueBuilder
from spdx.writers.tagvalue import write_document as tv_write_document
from spdx.document import Document as SPDXDocument

from aliens4friends.commons.utils import bash
from aliens4friends.commons.settings import Settings

EMPTY_FILE_SHA1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

class SPDXWriterLogger:
	def log(self, _):
		pass # do not log errors, they are returned by parse method

class SPDXUtilsException(Exception):
	pass

def parse_spdx_tv_str(spdx_tv: str) -> Tuple[SPDXDocument, bool]:
	p = SPDXTagValueParser(SPDXTagValueBuilder(), SPDXWriterLogger())
	p.build()
	doc, error = p.parse(spdx_tv)
	return doc, error

def parse_spdx_tv(filename: str) -> Tuple[SPDXDocument, bool]:
	with open(filename, 'r') as f:
		spdx_tv = f.read()
		return parse_spdx_tv_str(spdx_tv)

def write_spdx_tv(spdx_doc_obj: SPDXDocument, filename: str) -> None:
	"""write SPDX Document object to file (in tagvalue format)"""
	with open(filename, "w") as f:
		tv_write_document(spdx_doc_obj, f, validate=False)

def fix_spdxtv(spdxtv_path: str) -> None:
	"""fix SPDX TagValue file generated by ScanCode"""
	# TODO: check when these bugs are fixed upstream in ScanCode
	with open(spdxtv_path) as f:
		spdxtv = f.read()

	spdxtv_basename = os.path.basename(spdxtv_path)
	if "DocumentNamespace:" not in spdxtv:
		spdxtv = spdxtv.replace(
			"# Document Information",
			(
				"# Document Information\nDocumentNamespace: "
				f"http://spdx.org/spdxdocs/{spdxtv_basename}-{uuid4()}"
			),
		)
	if "DocumentName:" not in spdxtv:
		spdxtv = spdxtv.replace(
			"# Document Information",
			"# Document Information\nDocumentName: {spdxtv_basename}"
		)
	# replace empty SHA1 checksums with SHA1 checksum of an empty file
	spdxtv = spdxtv.replace(
		"FileChecksum: SHA1: \n",
		"FileChecksum: SHA1: da39a3ee5e6b4b0d3255bfef95601890afd80709\n",
	)
	spdxtv = re.sub(
		r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]",
		"",
		spdxtv
	) # remove characters that are invalid in XML (ready for RDF conversion)
	with open(spdxtv_path, 'w') as f:
		f.write(spdxtv)

def spdxtv2rdf(spdxtv_path: str, spdxrdf_path: str) -> None:
	"""Wrapper for java spdx tools TagToRDF converter"""
	out, err = bash(f'{Settings.SPDX_TOOLS_CMD} TagToRDF {spdxtv_path} {spdxrdf_path}')
	# java spdx-tools do not return error exit code: handling errors by
	# parsing command output
	if "Usage: " in out:
		raise SPDXUtilsException(
			"Error in converting spdxtv file into RDF with"
			f" java spdx-tools. Command output is: {out}"
		)
