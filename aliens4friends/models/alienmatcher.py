from .base import BaseModel
from .common import Tool, SourceFile

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
		version_candidates: list = None
	):
		self.name = name
		self.version = version
		self.debsrc_debian = debsrc_debian
		self.debsrc_orig = debsrc_orig
		self.dsc_format = dsc_format
		self.version_candidates = self.drilldown(version_candidates, VersionCandidate)

# FIXME Needed? It contains only the match itself, what else is on that json level?
class DebianMatchContainer(BaseModel):
	def __init__(
		self,
		match: DebianMatch = None
	):
		self.match = self.decode(match, DebianMatch)

class AlienSrc(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		alternative_names: list = None,
		internal_archive_name: str = None,
		filename: str = None,
		files: list = None
	):
		self.name = name
		self.version = version
		self.filename = filename
		self.internal_archive_name = internal_archive_name
		self.alternative_names = alternative_names if alternative_names else []
		self.files = self.drilldown(files, SourceFile)


class AlienMatcherModel(BaseModel):

	def __init__(
		self,
		tool: Tool = None,
		aliensrc: AlienSrc = None,
		debian: DebianMatchContainer = None,
		errors: list = None
	):
		self.tool = self.decode(tool, Tool)
		self.aliensrc = self.decode(aliensrc, AlienSrc)
		self.debian = self.decode(debian, DebianMatchContainer)
		self.errors = errors if errors else []

