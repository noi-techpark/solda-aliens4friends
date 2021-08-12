# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import SourceFile
from typing import List, Dict, Any, Optional

class InternalArchive(BaseModel):
	"""
	This model is solely used internally when the AlienSrc package gets expanded.
	"""
	def __init__(
		self,
		name: Optional[str] = None,
		checksums: Optional[Dict[str, str]] = None,
		rootfolder: Optional[str] = None,
		src_uri: Optional[str] = None,
		paths: Optional[List[str]] = None
	):
		self.name = name
		self.checksums = checksums
		self.rootfolder = rootfolder
		self.src_uri = src_uri
		self.paths = paths

class SourcePackage(BaseModel):
	def __init__(
		self,
		name: Optional[List[str]] = None,
		version: Optional[str] = None,
		manager: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
		cve_metadata: Optional[Dict[str, Any]] = None,
		files: Optional[List[SourceFile]] = None,
		tags: Optional[List[str]] = None
	):
		self.name = name
		self.version = version
		self.manager = manager
		self.metadata = metadata
		self.files = SourceFile.drilldown(files)
		self.tags = tags

class AlienSrc(BaseModel):
	def __init__(
		self,
		version: int = 0,
		source_package: Optional[SourcePackage] = None
	):
		self.version = version
		self.source_package = SourcePackage.decode(source_package)
