# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import logging

from spdx.parsers.tagvalue import Parser as SPDXTagValueParser
from spdx.parsers.tagvaluebuilders import Builder as SPDXTagValueBuilder
from spdx.writers.tagvalue import write_document as tv_write_document

class SPDXWriterLogger:
	def log(self, msg):
		logging.debug(msg)

def parse_spdx_tv(filename):
	with open(filename, 'r') as f:
		spdx_tv = f.read()
	p = SPDXTagValueParser(SPDXTagValueBuilder(), SPDXWriterLogger())
	p.build()
	doc, error = p.parse(spdx_tv)
	return doc, error

def write_spdx_tv(spdx_doc_obj, filename):
	"""write SPDX Document object to file (in tagvalue format)"""
	with open(filename, "w") as f:
		tv_write_document(spdx_doc_obj, f, validate=False)
