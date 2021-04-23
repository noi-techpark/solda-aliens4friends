from .base import BaseModel, DictModel

class Tags(BaseModel):
	def __init__(
		self,
		distro: list = None,
		machine: list = None,
		image: list = None,
		release: list = None
	):
		self.distro = distro
		self.machine = machine
		self.image = image
		self.release = release

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
		self.files = FileWithSize.drilldown(files)

class PackageMetaData(BaseModel):
	def __init__(
		self,
		name: str = None,
		base_name: str = None,
		version: str = None,
		revision: str = None,
		recipe_name: str = None,
		recipe_version: str = None,
		recipe_revision: str = None,
		license: str = None,
		description: str = None,
		depends: str = None,
		provides: str = None
	):
		self.name = name
		self.base_name = base_name
		self.version = version
		self.revision = revision
		self.recipe_name = recipe_name
		self.recipe_version = recipe_version
		self.recipe_revision = recipe_revision
		self.license = license
		self.description = description
		self.depends = depends
		self.provides = provides

class Package(BaseModel):
	def __init__(
		self,
		metadata: PackageMetaData = None,
		files: FileContainer = None
	):
		self.metadata = PackageMetaData.decode(metadata)
		self.files = FileContainer.decode(files)

class PackageWithTags(BaseModel):
	def __init__(
		self,
		package: Package = None,
		tags: Tags = None
	):
		self.package = Package.decode(package)
		self.tags = Tags.decode(tags)

class PackageContainer(DictModel):
	subclass = PackageWithTags

class RecipeMetaData(BaseModel):
	def __init__(
		self,
		name: str = None,
		base_name: str = None,
		version: str = None,
		revision: str = None,
		package_arch: str = None,
		author: str = None,
		homepage: str = None,
		summary: str = None,
		description: str = None,
		license: str = None,
		build_workdir: str = None,
		compiled_source_dir: str = None,
		depends: str = None,
		provides: str = None,
		cve_product: str = None
	):
		self.name = name
		self.base_name = base_name
		self.version = version
		self.revision = revision
		self.package_arch = package_arch
		self.author = author
		self.homepage = homepage
		self.summary = summary
		self.description = description
		self.license = license
		self.build_workdir = build_workdir
		self.compiled_source_dir = compiled_source_dir
		self.depends = depends
		self.provides = provides
		self.cve_product = cve_product

class Recipe(BaseModel):
	def __init__(
		self,
		metadata: RecipeMetaData = None,
		source_files: list = None,
		chk_sum: str = None
	):
		self.metadata = RecipeMetaData.decode(metadata)
		self.source_files = SourceFile.drilldown(source_files)
		self.chk_sum = chk_sum

class Container(BaseModel):
	def __init__(
		self,
		recipe: Recipe = None,
		tags: Tags = None,
		packages: dict = None
	):
		self.recipe = Recipe.decode(recipe)
		self.tags = Tags.decode(tags)
		self.packages = PackageContainer.decode(packages)


class TinfoilHatModel(DictModel):
	subclass = Container
