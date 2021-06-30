# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import Tool, SourceFile
from typing import List

class VersionCandidate(BaseModel):
	def __init__(
		self,
		version: str = None,
		distance: int = -1,
		is_aliensrc: bool = False
	):
		self.version = version
		self.distance = distance
		self.is_aliensrc = is_aliensrc


class DebianMatch(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		debsrc_debian: str = None,
		debsrc_orig: str = None,
		dsc_format: str = None,
		version_candidates: List[VersionCandidate] = None
	):
		self.name = name
		self.version = version
		self.debsrc_debian = debsrc_debian
		self.debsrc_orig = debsrc_orig
		self.dsc_format = dsc_format
		self.version_candidates = VersionCandidate.drilldown(version_candidates)

# FIXME Needed? It contains only the match itself, what else is on that json level?
class DebianMatchContainer(BaseModel):
	def __init__(
		self,
		match: DebianMatch = None
	):
		self.match = DebianMatch.decode(match)

class AlienSrc(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		alternative_names: List[str] = None,
		internal_archive_name: str = None,
		filename: str = None,
		files: List[SourceFile] = None
	):
		self.name = name
		self.version = version
		self.filename = filename
		self.internal_archive_name = internal_archive_name
		self.alternative_names = alternative_names if alternative_names else []
		self.files = SourceFile.drilldown(files)


class AlienMatcherModel(BaseModel):

	def __init__(
		self,
		tool: Tool = None,
		aliensrc: AlienSrc = None,
		debian: DebianMatchContainer = None,
		errors: List[str] = None
	):
		self.tool = Tool.decode(tool)
		self.aliensrc = AlienSrc.decode(aliensrc)
		self.debian = DebianMatchContainer.decode(debian)
		self.errors = errors if errors else []

class DebianSnapMatch(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		score: int = 0,
		distance: int = 0,
		package_score: int = 0,
		version_score: int = 0,
		srcfiles: List[SourceFile] = None,
		binfiles: List[SourceFile] = None
	):
		self.name = name
		self.version = version
		self.score = score
		self.distance = distance
		self.package_score = package_score
		self.version_score = version_score
		self.srcfiles = SourceFile.drilldown(srcfiles)
		self.binfiles = SourceFile.drilldown(binfiles)

class AlienSnapMatcherModel(BaseModel):
	def __init__(
		self,
		tool: Tool = None,
		aliensrc: AlienSrc = None,
		match: DebianSnapMatch = None,
		errors: List[str] = None
	):
		self.tool = Tool.decode(tool)
		self.aliensrc = AlienSrc.decode(aliensrc)
		self.match = DebianSnapMatch.decode(match)
		self.errors = errors if errors else []
