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
