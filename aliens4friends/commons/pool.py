# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
import logging
from json import dump as jsondump, load as jsonload
from pathlib import Path
from shutil import rmtree
from typing import Generator, Any, Union, List

from spdx.document import Document as SPDXDocument

from .utils import copy, mkdir
from .settings import Settings

from aliens4friends.models.base import BaseModelEncoder
from aliens4friends.commons.spdxutils import write_spdx_tv

logger = logging.getLogger(__name__)

class SRCTYPE:
	JSON = 0
	TEXT = 1
	PATH = 2
	SPDX = 3

class PoolError(Exception):
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

	def clnpath(self, path: str) -> str:
		if path.startswith(self.basepath):
			return path[len(self.basepath):]

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
			os.symlink(os.path.relpath(target, dest), link)



	def _add_with_history(
		self,
		src: Union[str, Any, bytes, SPDXDocument], # depends which src_type will be set
		dir_in_pool: str,
		link_filename: str,
		history_prefix: str,
		src_type: SRCTYPE
	) -> str:
		history_filename = history_prefix + link_filename
		history_path = os.path.join(dir_in_pool, "history")
		self._add(src, history_path, history_filename, src_type)
		self._upsertlink(dir_in_pool, link_filename, history_filename)


	def _add(
		self,
		src: Union[str, Any, bytes, SPDXDocument], # depends which src_type will be set
		dir_in_pool: str,
		new_filename: str,
		src_type: SRCTYPE
	) -> str:

		dest = self.abspath(dir_in_pool)
		dest_full = os.path.join(dest, new_filename)

		if os.path.isfile(dest_full) and Settings.POOLCACHED:
			logger.debug(f"Pool cache active and file {self.clnpath(dest)} exists... skipping!")
			return dest

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
			write_spdx_tv(src, dest)
		else:
			raise PoolError("Unknown source type to be written into the pool")
		return dest

	def _splitpath(self, *path_args: str) -> [str, str]:
		relpath = self.relpath(*path_args)
		return os.path.dirname(relpath), os.path.basename(relpath)


	def add(self, src: str, *path_args: str) -> str:
		filename = os.path.basename(src)
		filepath = self.relpath(*path_args)
		return self._add(src, filepath, filename, SRCTYPE.PATH)

	def add_with_history(self, src: str, history_prefix: str, *path_args: str) -> str:
		filename = os.path.basename(src)
		filepath = self.relpath(*path_args)
		return self._add_with_history(src, filepath, filename, history_prefix, SRCTYPE.PATH)

	def write_with_history(self, contents: bytes, history_prefix: str, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add_with_history(contents, filepath, filename, history_prefix, SRCTYPE.TEXT)

	def write(self, contents: bytes, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add(contents, filepath, filename, SRCTYPE.TEXT)

	def write_json_with_history(self, contents: Any, history_prefix: str, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add_with_history(contents, filepath, filename, history_prefix, SRCTYPE.JSON)

	def write_json(self, contents: Any, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add(contents, filepath, filename, SRCTYPE.JSON)

	def write_spdx_with_history(self, spdx_doc_obj: SPDXDocument, history_prefix: str, *path_args: str) -> str:
		filepath, filename = self._splitpath(*path_args)
		return self._add_with_history(spdx_doc_obj, filepath, filename, history_prefix, SRCTYPE.SPDX)

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

	def relglob(self, glob: str, *path_args: str) -> Generator[Path, None, None]:
		path = self.relpath(*path_args)
		return Path(path).rglob(glob)

	def rm(self, *path_args: str) -> None:
		path = self.relpath(*path_args)
		if os.path.isdir(path):
			rmtree(path)
		elif os.path.isfile(path) or os.path.islink(path):
			os.remove(path)
