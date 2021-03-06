# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import Tool, SourceFile
from typing import List, Optional

class VersionCandidate(BaseModel):
	def __init__(
		self,
		version: Optional[str] = None,
		distance: int = -1,
		is_aliensrc: bool = False
	):
		self.version = version
		self.distance = distance
		self.is_aliensrc = is_aliensrc


class DebianMatch(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
		score: Optional[float] = 0,
		package_score: Optional[float] = 0,
		version_score: Optional[float] = 0,
		debsrc_debian: Optional[str] = None,
		debsrc_orig: Optional[str] = None,
		dsc_format: Optional[str] = None,
		version_candidates: Optional[List[VersionCandidate]] = None
	):
		self.name = name
		self.version = version
		self.score = score
		self.package_score = package_score
		self.version_score = version_score
		self.debsrc_debian = debsrc_debian
		self.debsrc_orig = debsrc_orig
		self.dsc_format = dsc_format
		self.version_candidates = VersionCandidate.drilldown(version_candidates)

class AlienSrc(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
		alternative_names: Optional[List[str]] = None,
		internal_archive_name: Optional[str] = None,
		filename: Optional[str] = None,
		files: Optional[List[SourceFile]] = None
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
		tool: Optional[Tool] = None,
		aliensrc: Optional[AlienSrc] = None,
		match: Optional[DebianMatch] = None,
		errors: Optional[List[str]] = None
	):
		self.tool = Tool.decode(tool)
		self.aliensrc = AlienSrc.decode(aliensrc)
		self.match = DebianMatch.decode(match)
		self.errors = errors if errors else []

class DebianSnapMatch(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
		score: int = 0,
		distance: int = 0,
		package_score: int = 0,
		version_score: int = 0,
		package_score_ident: Optional[str] = None,
		version_score_ident: Optional[str] = None,
		srcfiles: Optional[List[SourceFile]] = None,
		debsrc_debian: Optional[str] = None,
		debsrc_orig: Optional[str] = None,
		dsc_format: Optional[str] = None,
	):
		self.name = name
		self.version = version
		self.score = score
		self.distance = distance
		self.package_score = package_score
		self.version_score = version_score
		self.package_score_ident = package_score_ident
		self.version_score_ident = version_score_ident
		self.srcfiles = SourceFile.drilldown(srcfiles)
		self.debsrc_debian = debsrc_debian
		self.debsrc_orig = debsrc_orig
		self.dsc_format = dsc_format

class AlienSnapMatcherModel(BaseModel):
	def __init__(
		self,
		tool: Optional[Tool] = None,
		aliensrc: Optional[AlienSrc] = None,
		match: Optional[DebianSnapMatch] = None,
		errors: Optional[List[str]] = None
	):
		self.tool = Tool.decode(tool)
		self.aliensrc = AlienSrc.decode(aliensrc)
		self.match = DebianSnapMatch.decode(match)
		self.errors = errors if errors else []

class MatchResults(BaseModel):
	def __init__(
		self,
		alien_name: str = "",
		match_name: str = "",
		snapmatch_name: str = "",
		match_package_score: int = 0,
		snapmatch_package_score: int = 0,
		alien_version: str = "",
		match_version: str = "",
		snapmatch_version: str = "",
		match_version_score: int = 0,
		snapmatch_version_score: int = 0,
		match_score: float = 0.0,
		snapmatch_score: float = 0.0,
		deltacode_proximity: float = 0.0
	):
		self.alien_name = alien_name
		self.match_name = match_name
		self.snapmatch_name = snapmatch_name
		self.match_package_score = match_package_score
		self.snapmatch_package_score = snapmatch_package_score
		self.alien_version = alien_version
		self.match_version = match_version
		self.snapmatch_version = snapmatch_version
		self.match_version_score = match_version_score
		self.snapmatch_version_score = snapmatch_version_score
		self.match_score = match_score
		self.snapmatch_score = snapmatch_score
		self.deltacode_proximity = deltacode_proximity
