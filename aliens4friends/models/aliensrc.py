from .base import BaseModel
from .common import SourceFile

class SourcePackage(BaseModel):
	def __init__(
		self,
		name: list = None,
		version: str = None,
		manager: str = None,
		metadata: dict = None,
		files: list = None
	):
		self.name = self.drilldown(name, str)
		self.version = version
		self.manager = manager
		self.metadata = self.decode(metadata, dict)
		self.files = self.drilldown(files, SourceFile)

class AlienSrc(BaseModel):
	def __init__(
		self,
		version: int = 0,
		source_package: SourcePackage = None
	):
		self.version = version
		self.source_package = self.decode(source_package, SourcePackage)
