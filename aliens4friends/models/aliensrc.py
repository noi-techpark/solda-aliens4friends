# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import SourceFile

class InternalArchive(BaseModel):
	"""
	This model is solely used internally when the AlienSrc package gets expanded.
	"""
	def __init__(
		self,
		name: str = None,
		checksums: dict = None,
		rootfolder: str = None,
		src_uri: str = None,
	):
		self.name = name
		self.checksums = checksums
		self.rootfolder = rootfolder
		self.src_uri = src_uri

class SourcePackage(BaseModel):
	def __init__(
		self,
		name: list = None,
		version: str = None,
		manager: str = None,
		metadata: dict = None,
		files: list = None
	):
		self.name = name
		self.version = version
		self.manager = manager
		self.metadata = metadata
		self.files = SourceFile.drilldown(files)

class AlienSrc(BaseModel):
	def __init__(
		self,
		version: int = 0,
		source_package: SourcePackage = None
	):
		self.version = version
		self.source_package = SourcePackage.decode(source_package)
