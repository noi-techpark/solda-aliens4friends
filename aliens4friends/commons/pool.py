# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

import os
import logging
from enum import IntEnum, Enum
from json import dump as jsondump, load as jsonload
from pathlib import Path
from shutil import rmtree
from typing import Generator, Any, Set, Union, Tuple
from datetime import datetime

from spdx.document import Document as SPDXDocument

from .utils import copy, mkdir, get_prefix_formatted
from .settings import Settings
from .archive import Archive

from aliens4friends.models.base import BaseModelEncoder, BaseModel, ModelError
from aliens4friends.commons.spdxutils import write_spdx_tv
from aliens4friends.commons.utils import bash, sha1sum

logger = logging.getLogger(__name__)

class SRCTYPE(IntEnum):
	JSON = 0
	TEXT = 1
	PATH = 2
	SPDX = 3

class OVERWRITE(IntEnum):
	CACHE_SETTING = 0
	ALWAYS = 1
	RAISE = 2

class FILETYPE(str, Enum):
	ALIENMATCHER = "alienmatcher.json"
	ALIENSRC = "aliensrc"
	TINFOILHAT = "tinfoilhat.json"
	SNAPMATCH = "snapmatch.json"
	DELTACODE = "deltacode.json"
	SCANCODE = "scancode.json"
	DEBIAN_SPDX = "debian.spdx"
	SCANCODE_SPDX = "scancode.spdx"
	FOSSY = "fossy.json"
	SESSION = "session.json"
	ALIENSPDX = "alien.spdx"
	# TODO Extend when needed, use it everywhere

class PoolError(Exception):
	pass
class PoolErrorFileExists(PoolError):
	pass
class PoolErrorUnsupportedFiletype(PoolError):
	pass

class Pool:

	def __init__(self, basepath: str) -> None:
		super().__init__()
		self.basepath = os.path.abspath(basepath)
		self.mkdir()
		if not os.path.isdir(self.basepath):
			raise NotADirectoryError(
				f"Unable to create the POOL at path '{self.basepath}'."
			)

	def filename(
		self,
		type: FILETYPE,
		name: str,
		version: str = "",
		variant: str = ""
	) -> str:
		"""Get the filename with extension of a certain file type

		Args:
			`type` (FILETYPE): The file type defined in `Pool.FILETYPE`
			`name` (str): The name of a package or any other name of a file
			`version` (str, optional): The version of a package. Defaults to `""`.
			`variant` (str, optional): The variant of a package. This might be ignored, dipending of the file type. Defaults to `""`.

		Raises:
			`PoolError`: if the `FILETYPE` is unknown to this method

		Returns:
			str: filename
		"""

		# Special type SESSION, name must be the session_id
		if type == FILETYPE.SESSION:
			return f"{name}.{type}"

		# Special type ALIENSPDX, name is the internal archive name, contains also the group ID
		if type == FILETYPE.ALIENSPDX:
			return f"{name}-gid{Settings.FOSSY_GROUP_ID}.{type}"

		# Types without variants
		if type in [
			FILETYPE.ALIENMATCHER,
			FILETYPE.SNAPMATCH,
			FILETYPE.DELTACODE,
			FILETYPE.SCANCODE,
			FILETYPE.DEBIAN_SPDX,
			FILETYPE.SCANCODE_SPDX
		]:
			return f"{name}-{version}.{type}"

		# Types that have a variant in their filename
		if type in [
			FILETYPE.ALIENSRC,
			FILETYPE.TINFOILHAT
		]:
			if variant:
				variant = f"-{variant}"
			return f"{name}-{version}{variant}.{type}"

		# Types with variant and group ID in their filename
		if type in [
			FILETYPE.FOSSY
		]:
			if variant:
				variant = f"-{variant}"
			return f"{name}-{version}{variant}-gid{Settings.FOSSY_GROUP_ID}.{type}"

		raise PoolError(f"Unable to find a path for the file type '{type}'")

	def relpath_typed(
		self,
		type: FILETYPE,
		name: str,
		version: str = "",
		variant: str = "",
		filename: str = "",
		with_filename: bool = True,
		in_userland: bool = True
	) -> str:
		"""
		Get a relative path to the corresponding file of a certain type
		"""

		# File that is located inside <PATH_SES>
		if type == FILETYPE.SESSION:
			relpath = self.relpath(Settings.PATH_SES)

		# Files that are located only inside <PATH_USR>/<name>/<version>
		elif type in [
			FILETYPE.SNAPMATCH,
			FILETYPE.ALIENMATCHER,
			FILETYPE.ALIENSRC,
			FILETYPE.TINFOILHAT,
			FILETYPE.DELTACODE,
			FILETYPE.FOSSY,
			FILETYPE.ALIENSPDX
		]:
			relpath = self.relpath(Settings.PATH_USR, name, version)

		# Files that are located only in <PATH_DEB>/<name>/<version>
		elif type in [
			FILETYPE.DEBIAN_SPDX
		]:
			relpath = self.relpath(Settings.PATH_DEB, name, version)

		# Files that are located inside <PATH_USR or PATH_DEB>/<name>/<version>
		elif type in [
			FILETYPE.SCANCODE,
			FILETYPE.SCANCODE_SPDX
		]:
			basepath = Settings.PATH_USR if in_userland else Settings.PATH_DEB
			relpath = self.relpath(basepath, name, version)

		else:
			raise PoolError(f"Unable to find a path for the file type '{type}'")

		if with_filename:
			relpath = os.path.join(
				relpath,
				self.filename(type, filename if filename else name, version, variant)
			)
		return relpath

	def packageinfo_from_path(self, path: Union[str, Path]):
		p = str(path).split("/")
		path = os.path.basename(path)
		package_id, mainext = os.path.splitext(path)
		if mainext == f".{FILETYPE.ALIENSRC}":
			ext = mainext
		else:
			package_id, subext = os.path.splitext(package_id)
			ext = f"{subext}{mainext}"

		ext = ext.lstrip('.')
		if ext not in FILETYPE.__dict__.values():
			raise PoolErrorUnsupportedFiletype(f"Unsupported file extension '{ext}'")

		name = p[-3]
		version = p[-2]

		# Types that have a variant in their filename
		variant = ""
		if ext in [
			FILETYPE.ALIENSRC,
			FILETYPE.TINFOILHAT,
			FILETYPE.FOSSY
		]:
			pos = len(name)+len(version)+2
			variant = package_id[pos:pos+8]

		# Handle filenames with group IDs
		group_id = ""
		if ext in [
			FILETYPE.FOSSY,
			FILETYPE.ALIENSPDX
		]:
			pos = package_id.rindex("-gid")
			group_id = package_id[pos+4:]

		return name, version, variant, group_id, ext


	def abspath_typed(
		self,
		type: FILETYPE,
		name: str,
		version: str = "",
		variant: str = "",
		filename: str = "",
		with_filename: bool = True,
		in_userland: bool = True
	) -> str:
		return self.abspath(
			self.relpath_typed(type, name, version, variant, filename, with_filename, in_userland)
		)

	def clnpath(self, path: Union[Path, str]) -> str:
		if isinstance(path, Path):
			path = os.path.join(path)
		if path.startswith(f"{self.basepath}/"):
			return path[len(self.basepath) + 1:]

		if path.startswith(os.path.sep):
			raise PoolError(f'Path {path} is outside the pool!')

		return path

	def mkdir(self, *sub_folder: str) -> str:
		return mkdir(self.abspath(*sub_folder))

	def relpath(self, *sub_folders: str) -> str:
		result = ""
		if sub_folders:
			result = os.path.join(*sub_folders)
			if result.startswith(os.path.sep):
				raise PoolError(f'Path {result} is not a relative path: sub_folders must be relative!')
		return result

	def abspath(self, *sub_folders: str) -> str:
		if sub_folders:
			if sub_folders[0].startswith(os.path.sep):
				path = os.path.join(*sub_folders)
				if not path.startswith(f"{self.basepath}/"):
					raise PoolError(f'Path {path} is outside the pool!')
				return path
			return os.path.join(
				self.basepath,
				self.relpath(*sub_folders)
			)
		return self.basepath

	def _upsertlink(self, dest: str, link: str, target: str) -> None:
		dest = self.abspath(dest)
		link = os.path.join(dest, link)
		target = os.path.join(dest, "history", target)
		if os.path.islink(link):
			if os.readlink(link) != target:
				os.unlink(link)
				os.symlink(os.path.relpath(target, dest), link)
		else:
			if os.path.isfile(link):
				prefix = get_prefix_formatted(datetime.fromtimestamp(os.path.getmtime(link)))
				new_path = os.path.join(dest, "history", prefix + os.path.basename(link))
				os.rename(link, new_path)
				logger.warn(
					f"File {self.clnpath(link)} already exists..."
				    f"migrating to a history based structure: New file is {self.clnpath(new_path)}."
				)
			os.symlink(os.path.relpath(target, dest), link)

	def _add_with_history(
		self,
		src: Union[str, Any, bytes, SPDXDocument], # depends which src_type will be set
		dir_in_pool: str,
		link_filename: str,
		history_prefix: str,
		src_type: SRCTYPE
	) -> None:
		history_filename = history_prefix + link_filename
		history_path = os.path.join(dir_in_pool, "history")
		self._add(src, history_path, history_filename, src_type, OVERWRITE.RAISE)
		self._upsertlink(dir_in_pool, link_filename, history_filename)

	def _add(
		self,
		src: Union[str, Any, bytes, SPDXDocument], # depends which src_type will be set
		dir_in_pool: str,
		new_filename: str,
		src_type: SRCTYPE,
		overwrite: OVERWRITE = OVERWRITE.CACHE_SETTING
	) -> str:

		file_in_pool = os.path.join(dir_in_pool, new_filename)
		dest = self.abspath(dir_in_pool)
		dest_full = os.path.join(dest, new_filename)

		if os.path.isfile(dest_full):
			if overwrite == OVERWRITE.RAISE:
				raise PoolErrorFileExists(
					f"can't add {file_in_pool}: file already exists"
				)
			elif Settings.POOLCACHED and overwrite == OVERWRITE.CACHE_SETTING:
				logger.debug(
					f"Pool cache active and file {file_in_pool}"
					" exists... skipping!"
				)
				return dir_in_pool

		self.mkdir(dir_in_pool)
		if src_type == SRCTYPE.PATH:
			copy(src, dest_full)
		elif src_type == SRCTYPE.JSON:
			with open(dest_full, 'w') as f:
				jsondump(src, f, indent = 2, cls = BaseModelEncoder)
		elif src_type == SRCTYPE.TEXT:
			with open(dest_full, 'wb+') as f:
				f.write(src)
		elif src_type == SRCTYPE.SPDX:
			write_spdx_tv(src, dest_full)
		else:
			raise PoolError("Unknown source type to be written into the pool")
		return dir_in_pool

	def _merge_json_with_history(
		self,
		src: BaseModel,
		dir_in_pool,
		filename: str,
		history_prefix: str,
	) -> str:

		dest = self.abspath(dir_in_pool)
		dest_full = os.path.join(dest, filename)

		history_filename = history_prefix + filename
		history_path = os.path.join(dir_in_pool, "history")

		# add file to history and check if a file with the same content
		# has already been added before
		history_files = os.path.join(self.abspath(history_path), f"*{filename}")
		stdout, _ = bash(f"sha1sum {history_files} | cut -d' ' -f 1")
		old_checksums = stdout.split("\n")
		if '' in old_checksums:
			old_checksums.remove('')
		self._add(
			src, history_path, history_filename, SRCTYPE.JSON, OVERWRITE.RAISE
		)
		new_file = os.path.join(self.abspath(history_path), history_filename)
		new_checksum = sha1sum(new_file)
		if new_checksum in old_checksums:
			bash(f"rm {new_file}")
			logger.info(
				f"'{filename}': a file with same content has been already"
				 " added before, skipping"
			)
			return dir_in_pool

		if not os.path.isfile(dest_full):
			to_add = src
		else:
			model = type(src)
			old = model.from_file(dest_full)
			new = src
			try:
				to_add = model.merge(old, new) # type: ignore
			except ModelError as ex:
				# delete history file if merge fails
				bash(f"rm {new_file}")
				raise ex

		self._add(to_add, dir_in_pool, filename, SRCTYPE.JSON, OVERWRITE.ALWAYS)
		return dir_in_pool


	def _splitpath(self, *path_args: str) -> Tuple[str, str]:
		relpath = self.relpath(*path_args)
		return os.path.dirname(relpath), os.path.basename(relpath)


	def add(self, src: str, *path_args: str) -> str:
		filename = os.path.basename(src)
		filepath = self.relpath(*path_args)
		return self._add(src, filepath, filename, SRCTYPE.PATH)

	def add_with_history(self, src: str, history_prefix: str, *path_args: str) -> None:
		filename = os.path.basename(src)
		filepath = self.relpath(*path_args)
		self._add_with_history(src, filepath, filename, history_prefix, SRCTYPE.PATH)

	def write_with_history(self, contents: bytes, history_prefix: str, *path_args: str) -> None:
		filepath, filename = self._splitpath(*path_args)
		self._add_with_history(contents, filepath, filename, history_prefix, SRCTYPE.TEXT)

	def write(self, contents: bytes, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add(contents, filepath, filename, SRCTYPE.TEXT)

	def write_json_with_history(self, contents: Any, history_prefix: str, *path_args: str) -> None:
		filepath, filename = self._splitpath(*path_args)
		self._add_with_history(contents, filepath, filename, history_prefix, SRCTYPE.JSON)

	def merge_json_with_history(self, contents: BaseModel, filename: str, history_prefix: str, *path_args: str) -> str:
		filepath = self.relpath(*path_args)
		return self._merge_json_with_history(contents, filepath, filename, history_prefix)

	def write_json(self, contents: Any, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add(contents, filepath, filename, SRCTYPE.JSON)

	def write_spdx_with_history(self, spdx_doc_obj: SPDXDocument, history_prefix: str, *path_args: str) -> None:
		filepath, filename = self._splitpath(*path_args)
		self._add_with_history(spdx_doc_obj, filepath, filename, history_prefix, SRCTYPE.SPDX)

	def write_spdx(self, spdx_doc_obj: SPDXDocument, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add(spdx_doc_obj, filepath, filename, SRCTYPE.SPDX)

	def get(self, *path_args: str) -> str:
		return self._get(False, *path_args) #pytype: disable=bad-return-type

	def get_binary(self, *path_args: str) -> bytes:
		return self._get(True, *path_args) #pytype: disable=bad-return-type

	def get_json(self, *path_args: str) -> Any:
		path = self.abspath(*path_args)
		with open(path, "r") as f:
			return jsonload(f)

	def _get(self, binary: bool, *path_args: str) -> Union[bytes, str]:
		path = self.abspath(*path_args)
		flag = "b" if binary else ""
		with open(path, f'r{flag}') as f:
			return f.read()

	def absglob(self, glob: str, *path_args: str) -> Generator[Path, None, None]:
		path = self.abspath(*path_args)
		return Path(path).rglob(glob)

	def rm(self, *path_args: str) -> None:
		path = self.abspath(*path_args)
		if os.path.isdir(path):
			rmtree(path)
		elif os.path.isfile(path) or os.path.islink(path):
			os.remove(path)

	def exists(self, *path_args: str) -> bool:
		path = self.abspath(*path_args)
		return os.path.isfile(path) or os.path.isdir(path)

	def is_empty(self, *path_args: str) -> bool:
		path = self.abspath(*path_args)
		return not os.listdir(path)

	def cached(self, path_in_pool: str, is_dir: bool = False, debug_prefix: str = "") -> bool:
		if not Settings.POOLCACHED:
			self.rm(path_in_pool)
		if is_dir:
			self.mkdir(path_in_pool)
			if not self.is_empty(path_in_pool):
				logger.debug(f"{debug_prefix}Skip {path_in_pool}: Folder not empty and cache enabled.")
				return True
		elif self.exists(path_in_pool):
			logger.debug(f"{debug_prefix}Skip {path_in_pool}: Result exists and cache enabled.")
			return True
		return False

	def unpack(self, archive: Archive, dest_in_pool: str = "",  archive_in_archive: str = "", debug_prefix: str = "") -> str:
		if not dest_in_pool:
			dest_in_pool = os.path.join(os.path.dirname(archive.path), "__unpacked")

		if self.cached(dest_in_pool, is_dir=True):
			return dest_in_pool

		dest_abspath = self.abspath(dest_in_pool)
		archive_relpath = archive.path
		archive.path = self.abspath(archive.path)
		if archive_in_archive:
			logger.debug(
				f"{debug_prefix}Extracting archive {archive_in_archive} inside {archive_relpath} to {dest_in_pool}"
			)
			archive.in_archive_extract(archive_in_archive, dest_abspath)
		else:
			logger.debug(f"{debug_prefix}Extracting archive {archive_relpath} to {dest_in_pool}")
			archive.extract(dest_abspath)
		return dest_in_pool
