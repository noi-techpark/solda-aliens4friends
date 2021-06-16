# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

import logging

from typing import List, Dict, TypeVar
from copy import deepcopy

from deepdiff import DeepDiff

from .base import BaseModel, DictModel, ModelError
from aliens4friends.commons.utils import sha1sum_str

logger = logging.getLogger(__name__)

_TTags = TypeVar('_TTags', bound='TTags')
class Tags(BaseModel):
	def __init__(
		self,
		distro: List[str] = None,
		machine: List[str] = None,
		image: List[str] = None,
		release: List[str] = None
	) -> None:
		self.distro = distro
		self.machine = machine
		self.image = image
		self.release = release

	@staticmethod
	def merge(old_tags: _TTags, new_tags: _TTags) -> _TTags:
		res = Tags()
		for attr in old_tags.encode():
			old_list = getattr(old_tags, attr) or []
			new_list = getattr(new_tags, attr) or []
			res_list = list(set(old_list + new_list)) or None
			setattr(res, attr, res_list)
		return res

class SourceFile(BaseModel):
	def __init__(
		self,
		rootpath: str = None,
		relpath: str = None,
		src_uri: str = None,
		sha1: str = None,
		tags: List[str] = None
	) -> None:
		self.rootpath = rootpath
		self.relpath = relpath
		self.src_uri = src_uri
		self.sha1 = sha1
		self.tags = tags

class FileWithSize(BaseModel):
	def __init__(
		self,
		path: str = None,
		sha1: str = None,
		size: int = 0
	) -> None:
		self.path = path
		self.sha1 = sha1
		self.size = size

class FileContainer(BaseModel):
	def __init__(
		self,
		file_dir: str = None,
		files: List[FileWithSize] = None
	) -> None:
		self.file_dir = file_dir
		self.files = FileWithSize.drilldown(files)

class PackageMetaData(BaseModel):
	def __init__(
		self,
		name: str = None,
		base_name: str = None,
		version: str = None,
		revision: str = None,
		package_arch: str = None,
		recipe_name: str = None,
		recipe_version: str = None,
		recipe_revision: str = None,
		license: str = None,
		description: str = None,
		depends: str = None,
		provides: str = None
	) -> None:
		self.name = name
		self.base_name = base_name
		self.version = version
		self.revision = revision
		self.package_arch = package_arch
		self.recipe_name = recipe_name
		self.recipe_version = recipe_version
		self.recipe_revision = recipe_revision
		self.license = license
		self.description = description
		self.depends = depends
		self.provides = provides

_TPackage = TypeVar('_TPackage', bound='Package')
class Package(BaseModel):
	def __init__(
		self,
		metadata: PackageMetaData = None,
		files: FileContainer = None
	) -> None:
		self.metadata = PackageMetaData.decode(metadata)
		self.files = FileContainer.decode(files)


class PackageWithTags(BaseModel):
	def __init__(
		self,
		package: Package = None,
		tags: List[str] = None
	) -> None:
		self.package = Package.decode(package)
		self.tags = tags


_TPackageContainer = TypeVar('_TPackageContainer', bound='PackageContainer')
class PackageContainer(DictModel):
	subclass = PackageWithTags

	@staticmethod
	def merge(
		old: Dict[str, _TPackageContainer],
		new: Dict[str, _TPackageContainer]
	) -> Dict[str, _TPackageContainer]:
		res = {}
		ids = set(list(old) + list(new))
		for id in ids:
			if id in new and id in old:
				logger.debug(f"{id} found in new and old, merging")
				diff = DeepDiff(
					old[id],
					new[id],
					ignore_order=True,
					exclude_paths=[
						'root.tags', # here we expect differences that we want
									 # to merge
						'root.package.files.file_dir',  # specific to
									# local build, needed just for aliensrc
									# package creation in a previous stage;
									# we expect it may be different if
									# tinfoilhat files to merge have been
									# generated in different local builds, but
									# it doesn't matter here
					],
					#exclude_regex_paths=[
					#	r'root.package.files.files\[\d+\].sha1'
					#] # this should not be needed, if we have reproducible
					# builds in bitbake! Leaving it here, for future tests
				)
				if diff:
					raise ModelError(
						f"can't merge {id}, because some package fields"
						f" mismatch, diff is: {diff}"
					)
				res[id] = deepcopy(new[id])
				res[id].tags = list(set(old[id].tags + new[id].tags))
			elif id in new and id not in old:
				logger.debug(f"{id} found in new")
				res[id] = new[id]
			elif id not in new and id in old:
				logger.debug(f"{id} found in old")
				res[id] = old[id]
		return res

class DependsProvides(BaseModel):
	def __init__(self, depends: str, provides: str):
		self.depends = depends
		self.provides = provides

_TDependsProvidesContainer = TypeVar('_TDependsProvidesContainer', bound='DependsProvidesContainer')
class DependsProvidesContainer(DictModel):
	"""DictModel for 'depends' and 'provides' of bitbake recipes; the key is the
	machine name, since the same recipe, built for different machines, may have
	different build dependencies
	"""
	subclass = DependsProvides

	@staticmethod
	def merge(
		old: Dict[str, _TDependsProvidesContainer],
		new: Dict[str, _TDependsProvidesContainer]
	) -> Dict[str, _TDependsProvidesContainer]:
		res = {}
		ids = set(list(old) + list(new))
		for id in ids:
			if id in new and id in old:
				logger.debug(f"{id} found in new and old, checking sameness")
				diff = DeepDiff(old[id], new[id], ignore_order=True)
				if diff:
					raise ModelError(
						"can't merge, depends_provides mismatch for machine"
						f" '{id}', diff is: {diff}"
					)
				res[id] = new[id]
			elif id in new:
				logger.debug(f"depends_provides for machine '{id}' found in new")
				res[id] = new[id]
			elif id in old:
				logger.debug(f"depends_provides for machine '{id}' found in old")
				res[id] = old[id]
		return res

class RecipeMetaData(BaseModel):
	def __init__(
		self,
		name: str = None,
		base_name: str = None,
		version: str = None,
		revision: str = None,
		author: str = None,
		homepage: str = None,
		summary: str = None,
		description: str = None,
		license: str = None,
		build_workdir: str = None,
		compiled_source_dir: str = None,
		depends_provides: Dict[str, DependsProvides] = None,
		cve_product: str = None
	) -> None:
		self.name = name
		self.base_name = base_name
		self.version = version
		self.revision = revision
		self.author = author
		self.homepage = homepage
		self.summary = summary
		self.description = description
		self.license = license
		self.build_workdir = build_workdir
		self.compiled_source_dir = compiled_source_dir
		self.depends_provides = DependsProvidesContainer.decode(depends_provides)
		self.cve_product = cve_product


class Recipe(BaseModel):
	def __init__(
		self,
		metadata: RecipeMetaData = None,
		source_files: List[SourceFile] = None,
		chk_sum: str = None
	) -> None:
		self.metadata = RecipeMetaData.decode(metadata)
		self.source_files = SourceFile.drilldown(source_files)
		self.chk_sum = chk_sum


_TContainer = TypeVar('_TContainer', bound='Container')
class Container(BaseModel):

	def __init__(
		self,
		recipe: Recipe = None,
		tags: List[str] = None,
		packages: Dict[str, PackageWithTags] = None
	) -> None:
		self.recipe = Recipe.decode(recipe)
		self.tags = tags
		self.packages = PackageContainer.decode(packages)

	@staticmethod
	def merge(
		old: Dict[str, _TContainer],
		new: Dict[str, _TContainer],
	) -> Dict[str, _TContainer]:
		"""merge tags, packages and depends_provides of two tinfoilhat dicts in
		a new tinfoilhat dict; all other attributes of the two tinfoilhat dict -
		except for bitbake-specific paths - must be the same, otherwise a
		ModelError exception is raised
		"""
		res = {}
		ids = set(list(old) + list(new))
		for id in ids:
			if id in new and id in old:
				logger.debug(f"{id} found in new and old, merging")
				diff = DeepDiff(
					old[id],
					new[id],
					ignore_order=True,
					exclude_paths=[
						"root.tags", # here we expect differences that we want
						             # to merge
						"root.packages", # same here
						"root.recipe.chk_sum",
						"root.recipe.metadata.depends_provides", # same here
						"root.recipe.metadata.build_workdir", # specific to
									# local build, needed just for aliensrc
									# package creation in a previous stage;
									# we expect it may be different if
									# tinfoilhat files to merge have been
									# generated in different local builds, but
									# it doesn't matter here
						"root.recipe.metadata.compiled_source_dir", # same here
						"root.recipe.source_files"
					]
				)
				if diff:
					raise ModelError(
						f"can't merge tags and packages for recipe {id}, "
						f"because some fields mismatch, diff is: {diff}"
					)
				res[id] = deepcopy(new[id])
				res[id].tags = list(set(old[id].tags + new[id].tags))
				res[id].packages = PackageContainer.merge(
					old[id].packages,
					new[id].packages
				)
				res[id].recipe.metadata.depends_provides = (
					DependsProvidesContainer.merge(
						old[id].recipe.metadata.depends_provides,
						new[id].recipe.metadata.depends_provides
				))

				### FIXME This is a tinfoilhat merge hack!
				# Merging source_files
				old_files = { f'{s.src_uri}-{s.sha1}': s for s in old[id].recipe.source_files }
				new_files = { f'{s.src_uri}-{s.sha1}': s for s in new[id].recipe.source_files }
				for new_id in new_files:
					if new_id in old_files:
						for el in new_files[new_id].tags:
							old_files[new_id].tags.add(el)
					else:
						res[id].recipe.source_files.append(new_files[new_id])

				### FIXME This is a tinfoilhat merge hack!
				# Updating chk_sum
				if not res[id].recipe.source_files:
					# meta-recipe with no source files but only dependencies
					m = res[id].recipe.metadata
					res[id].recipe.chk_sum = sha1sum_str(f'{m.name}{m.version}{m.revision}')
				else:
					sha1list = [ f.sha1 for f in res[id].recipe.source_files ]
					sha1list.sort()
					res[id].recipe.chk_sum = sha1sum_str(''.join(sha1list))

			elif id in new:
				logger.debug(f"{id} found in new")
				res[id] = new[id]
			elif id in old:
				logger.debug(f"{id} found in old")
				res[id] = old[id]
		return res

_TTinfoilHatModel = TypeVar('_TTinfoilHatModel', bound='TinfoilHatModel')
class TinfoilHatModel(DictModel):
	subclass = Container

	@staticmethod
	def merge(
		old: _TTinfoilHatModel,
		new: _TTinfoilHatModel
	) -> _TTinfoilHatModel:
		"""merge tags, packages and depends_provides of two tinfoilhat objects
		in a new tinfoilhat object; all other attributes of the two tinfoilhat
		objs - except for bitbake-specific paths - must be the same, otherwise a
		ModelError exception is raised
		"""
		res = TinfoilHatModel({})
		res._container = Container.merge(old._container, new._container)
		return res
