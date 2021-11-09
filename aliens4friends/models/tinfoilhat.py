# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

import logging

from typing import List, Dict, TypeVar, Optional
from copy import deepcopy

from deepdiff import DeepDiff

from .base import BaseModel, DictModel, ModelError
from aliens4friends.commons.utils import sha1sum_str

logger = logging.getLogger(__name__)

class SourceFile(BaseModel):
	def __init__(
		self,
		rootpath: Optional[str] = None,
		relpath: Optional[str] = None,
		src_uri: Optional[str] = None,
		sha1_cksum: Optional[str] = None,
		git_sha1: Optional[str] = None,
		tags: Optional[List[str]] = None
	) -> None:
		self.rootpath = rootpath
		self.relpath = relpath
		self.src_uri = src_uri
		self.sha1_cksum = sha1_cksum
		self.git_sha1 = git_sha1
		self.tags = tags
		# TODO: a specific class for tags should be added,
		# like in tinfoilhat

class FileWithSize(BaseModel):
	def __init__(
		self,
		path: Optional[str] = None,
		sha256: Optional[str] = None,
		size: int = 0
	) -> None:
		self.path = path
		self.sha256 = sha256
		self.size = size

class FileContainer(BaseModel):
	def __init__(
		self,
		file_dir: Optional[str] = None,
		files: Optional[List[FileWithSize]] = None
	) -> None:
		self.file_dir = file_dir
		self.files = FileWithSize.drilldown(files)

class DependsProvides(BaseModel):
	def __init__(
		self,
		depends: List[str],
		provides: List[str]
	):
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
				logger.debug(f"{id} found in new and old, checking consistency")
				diff = DeepDiff(old[id].depends, new[id].depends, ignore_order=True)
				if diff:
					logger.warning(
						"depends mismatch for machine"
						f" '{id}', diff is: {diff}"
					)
				new[id].provides = list(set(old[id].provides + new[id].provides))
				res[id] = new[id]
			elif id in new:
				logger.debug(f"depends_provides for machine '{id}' found in new")
				res[id] = new[id]
			elif id in old:
				logger.debug(f"depends_provides for machine '{id}' found in old")
				res[id] = old[id]
		return res

class PackageMetaData(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		base_name: Optional[str] = None,
		version: Optional[str] = None,
		revision: Optional[str] = None,
		package_arch: Optional[str] = None,
		recipe_name: Optional[str] = None,
		recipe_version: Optional[str] = None,
		recipe_revision: Optional[str] = None,
		license: Optional[str] = None,
		summary: Optional[str] = None,
		description: Optional[str] = None,
		depends: Optional[List[str]] = None,
		provides: Optional[List[str]] = None
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
		self.summary = summary
		self.description = description
		self.depends = depends
		self.provides = provides

_TPackage = TypeVar('_TPackage', bound='Package')
class Package(BaseModel):
	def __init__(
		self,
		metadata: Optional[PackageMetaData] = None,
		files: Optional[FileContainer] = None,
		chk_sum: Optional[str] = None
	) -> None:
		self.metadata = PackageMetaData.decode(metadata)
		self.files = FileContainer.decode(files)
		self.chk_sum = chk_sum



class PackageWithTags(BaseModel):
	def __init__(
		self,
		package: Optional[Package] = None,
		tags: Optional[List[str]] = None
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
					]
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


class RecipeMetaData(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		base_name: Optional[str] = None,
		version: Optional[str] = None,
		revision: Optional[str] = None,
		variant: Optional[str] = None,
		author: Optional[str] = None,
		homepage: Optional[str] = None,
		summary: Optional[str] = None,
		description: Optional[str] = None,
		license: Optional[str] = None,
		depends_provides: Optional[Dict[str, DependsProvides]] = None
	) -> None:
		self.name = name
		self.base_name = base_name
		self.version = version
		self.revision = revision
		self.variant = variant
		self.author = author
		self.homepage = homepage
		self.summary = summary
		self.description = description
		self.license = license
		self.depends_provides = DependsProvidesContainer.decode(depends_provides)

	@staticmethod
	def merge(old: 'RecipeMetaData', new: 'RecipeMetaData') -> 'RecipeMetaData':
		updatable = [ "homepage", "summary", "description" ]
		res = RecipeMetaData()
		for attr_name in res.encode():
			if attr_name in updatable:
				setattr(res, attr_name, getattr(new, attr_name))
			else:
				setattr(res, attr_name, getattr(old, attr_name))
		res.depends_provides = DependsProvidesContainer.merge(
			old.depends_provides,
			new.depends_provides
		)
		return res

class CveProduct(BaseModel):
	def __init__(
		self,
		vendor: Optional[str] = None,
		product: Optional[str] = None
	):
		self.vendor = vendor
		self.product = product

class RecipeCveMetaData(BaseModel):
	def __init__(
		self,
		cve_version: Optional[str] = None,
		cve_version_suffix: Optional[str] = None,
		cve_check_whitelist: Optional[List[str]] = None,
		cve_product: Optional[List[CveProduct]] = None
	):
		self.cve_version = cve_version
		self.cve_version_suffix = cve_version_suffix
		self.cve_check_whitelist = cve_check_whitelist
		self.cve_product = CveProduct.drilldown(cve_product)

	@staticmethod
	def merge(old: 'RecipeCveMetaData', new: 'RecipeCveMetaData') -> 'RecipeCveMetaData':
		res = RecipeCveMetaData()
		must_be_equal = [ 'cve_version', 'cve_version_suffix' ]
		for attr_name in old.encode():
			old_attr = getattr(old, attr_name)
			new_attr = getattr(new, attr_name)
			if old_attr == new_attr:
				setattr(res, attr_name, old_attr)
			elif attr_name in must_be_equal:
				raise ModelError(
					f"can't merge cve metadata for {old.cve_product[0].product}"
					f": '{attr_name}' mismatch"
				)
			else:
				setattr(res, attr_name, new_attr)
		return res


class Recipe(BaseModel):
	def __init__(
		self,
		metadata: Optional[RecipeMetaData] = None,
		cve_metadata: Optional[RecipeCveMetaData] = None,
		source_files: Optional[List[SourceFile]] = None,
		chk_sum: Optional[str] = None
	) -> None:
		self.metadata = RecipeMetaData.decode(metadata)
		self.cve_metadata = RecipeCveMetaData.decode(cve_metadata)
		self.source_files = SourceFile.drilldown(source_files)
		self.chk_sum = chk_sum


_TContainer = TypeVar('_TContainer', bound='Container')
class Container(BaseModel):

	def __init__(
		self,
		recipe: Optional[Recipe] = None,
		tags: Optional[List[str]] = None,
		packages: Optional[Dict[str, PackageWithTags]] = None
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
					# legend for paths excluded from diff:
					# (M): expected diffs that we want to merge
					# (I): expected diffs that we can safely ignore (we keep the newer value)
					# (U): undesirable diffs that however "happen", even if the recipe version and revision stay the same;
					#      we ignore them to avoid complications (we keep the newer value)
					exclude_paths=[
						"root.tags", # (M)
						"root.packages", # (M)
						"root.recipe.metadata.description", # (U)
						"root.recipe.metadata.homepage", # (U)
						"root.recipe.metadata.summary", # (U)
						"root.recipe.metadata.depends_provides", # (I)
						"root.recipe.cve_metadata", # (M)
					],
					exclude_regex_paths=[
						r"root.recipe.source_files\[\d+\].tags", # (M)
						r"root.recipe.source_files\[\d+\].src_uri", # (U)
						r"root.recipe.source_files\[\d+\].rootpath", # (I)
						r"root.recipe.source_files\[\d+\].relpath", # (U) # FIXME workaround, handlye filename changes instead
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
				res[id].recipe.metadata = RecipeMetaData.merge(
					old[id].recipe.metadata,
					new[id].recipe.metadata
				)
				res[id].recipe.cve_metadata = RecipeCveMetaData.merge(
					old[id].recipe.cve_metadata,
					new[id].recipe.cve_metadata
				)
				old_files = { 
					f'{s.relpath}-{s.git_sha1 or s.sha1_cksum}': s 
					for s in old[id].recipe.source_files 
				}
				new_files = { 
					f'{s.relpath}-{s.git_sha1 or s.sha1_cksum}': s 
					for s in res[id].recipe.source_files 
					# res[id] here is on purpose, we need to modify
					# its contents by reference; 
					# it has been deepcopied from new[id]
				} 
				for file_id in new_files:
					if old_files.get(file_id): # FIMXE workaround (see above)
						new_files[file_id].tags = list(set(
							old_files[file_id].tags + new_files[file_id].tags
						))
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

	# FIXME: All merge methods here are based on one assumption:
    # that the "new" tinfoilhat file is really newer than the "old"
    # one, and that it containes more updated info than the "old" one.
    # We should add some field ('project manifest commit date'?)
    # tinfoilhat.json in order to check this
