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
		return path

	def mkdir(self, *sub_folder: str) -> str:
		return mkdir(self.abspath(*sub_folder))

	def relpath(self, *sub_folders: str) -> str:
		if sub_folders:
			return os.path.join(*sub_folders)
		return ""

	def abspath(self, *sub_folders: str) -> str:
		if sub_folders:
			return os.path.join(self.basepath, *sub_folders)
		return self.basepath

	def _upsertlink(self, dest: str, link: str, target: str) -> None:
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
		path_args: List[str],
		history_prefix: str = "",
		new_filename: str = "",
		src_type: SRCTYPE = SRCTYPE.PATH
	) -> str:

		if src_type != SRCTYPE.PATH and not new_filename:
			raise PoolError(f"Cannot add a file without a name!")

		filename = new_filename if new_filename else os.path.basename(src)
		history_filename = history_prefix + filename

		dest = self.abspath(*path_args)
		self._add(src, [dest, "history"], history_filename, src_type)
		self._upsertlink(dest, filename, history_filename)



	def _add(
		self,
		src: Union[str, Any, bytes, SPDXDocument], # depends which src_type will be set
		path_args: List[str],
		new_filename: str = "",
		src_type: SRCTYPE = SRCTYPE.PATH
	) -> str:

		if src_type != SRCTYPE.PATH and not new_filename:
			raise PoolError(f"Cannot add a file without a name!")

		new_filename = new_filename if new_filename else os.path.basename(src)

		dest = self.abspath(*path_args)
		pooldest = self.relpath(*path_args)

		dest_full = os.path.join(dest, new_filename)
		if os.path.isfile(dest_full) and Settings.POOLCACHED:
			logger.debug(f"Pool cache active and file {pooldest} exists... skipping!")
			return dest
		self.mkdir(dest)
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

	def add(self, src: str, *path_args: str) -> str:
		return self._add(src, list(path_args))

	def add_with_history(self, src: str, history_prefix: str, *path_args: str) -> str:
		return self._add_with_history(src, list(path_args), history_prefix, src_type=SRCTYPE.PATH)

	def write_with_history(self, contents: bytes, history_prefix: str, *path_args: str) -> str:
		return self._add_with_history(contents, list(path_args), history_prefix, src_type=SRCTYPE.TEXT)

	def write(self, contents: bytes, *path_args: str) -> str:
		return self._add(contents, list(path_args[:-1]), path_args[-1], SRCTYPE.TEXT)

	def write_json_with_history(self, contents: Any, history_prefix: str, *path_args: str) -> str:
		return self._add_with_history(contents, list(path_args), history_prefix, src_type=SRCTYPE.JSON)

	def write_json(self, contents: Any, *path_args: str) -> str:
		return self._add(contents, list(path_args[:-1]), path_args[-1], SRCTYPE.JSON)

	def write_spdx_with_history(self, spdx_doc_obj: SPDXDocument, history_prefix: str, *path_args: str) -> str:
		return self._add_with_history(spdx_doc_obj, list(path_args[:-1]), history_prefix, path_args[-1], SRCTYPE.SPDX)

	def write_spdx(self, spdx_doc_obj: SPDXDocument, *path_args: str) -> str:
		return self._add(spdx_doc_obj, list(path_args[:-1]), path_args[-1], SRCTYPE.SPDX)

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
