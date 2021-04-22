from .base import BaseModel

class Tags(BaseModel):
	def __init__(
		self,
		distro: list = None,
		machine: list = None,
		image: list = None,
		release: list = None
	):
		self.distro = self.drilldown(distro, str)
		self.machine = self.drilldown(machine, str)
		self.image = self.drilldown(image, str)
		self.release = self.drilldown(release, str)

class SourceFile(BaseModel):
	def __init__(
		self,
		rootpath: str = None,
		relpath: str = None,
		src_uri: str = None,
		sha1: str = None
	):
		self.rootpath = rootpath
		self.relpath = relpath
		self.src_uri = src_uri
		self.sha1 = sha1

class FileWithSize(BaseModel):
	def __init__(
		self,
		path: str = None,
		sha1: str = None,
		size: int = 0
	):
		self.path = path
		self.sha1 = sha1
		self.size = size

class FileContainer(BaseModel):
	def __init__(
		self,
		file_dir: str = None,
		files: list = None
	):
		self.file_dir = file_dir
		self.files = self.drilldown(files, FileWithSize)

class Package(BaseModel):
	def __init__(
		self,
		metadata: dict = None,
		files: FileContainer = None
	):
		self.metadata = metadata
		self.files = self.decode(files, FileContainer)

class PackageWithTags(BaseModel):
	def __init__(
		self,
		package: Package = None,
		tags: Tags = None
	):
		self.package = self.decode(package, Package)
		self.tags = self.decode(tags, Tags)

class PackageContainer(BaseModel):
	def __init__(
		self,
		container: dict = None
	):
		self._container = self.decode(container, PackageWithTags, True)

class Recipe(BaseModel):
	def __init__(
		self,
		metadata: dict = None,
		source_files: list = None,
		chk_sum: str = None
	):
		self.metadata = metadata
		self.source_files = self.drilldown(source_files, SourceFile)
		self.chk_sum = chk_sum

class Container(BaseModel):
	def __init__(
		self,
		recipe: Recipe = None,
		tags: Tags = None,
		packages: dict = None
	):
		self.recipe = self.decode(recipe, Recipe)
		self.tags = self.decode(tags, Tags)
		self.packages = packages


class TinfoilHatModel(BaseModel):
	def __init__(
		self,
		container: dict = None
	):
		self._container = self.decode(container, Container, True)
