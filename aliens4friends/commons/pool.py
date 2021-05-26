# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
import logging
from json import dump as jsondump, load as jsonload
from pathlib import Path
from shutil import rmtree
from typing import Generator, Any, Union

from spdx.document import Document as SPDXDocument

from .utils import copy, mkdir
from .settings import Settings

from aliens4friends.models.base import BaseModelEncoder
from aliens4friends.commons.spdxutils import write_spdx_tv

logger = logging.getLogger(__name__)

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

	def add_with_history(self, src: str, history_prefix: str, *path_args: str) -> str:
		return self.add(src, *path_args)

	def add(self, src: str, *path_args: str) -> str:
		dest = self.abspath(*path_args)
		pooldest = self.relpath(*path_args)
		dest_full = os.path.join(dest, os.path.basename(src))
		if os.path.isfile(dest_full) and Settings.POOLCACHED:
			logger.debug(f"Pool cache active and file {pooldest} exists... skipping!")
			return dest
		self.mkdir(dest)
		copy(src, dest_full)
		return dest

	def write_with_history(self, contents: bytes, history_prefix: str, *path_args: str) -> str:
		return self.write(contents, *path_args)

	def write(self, contents: bytes, *path_args: str) -> str:
		dest_folder = self.abspath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		with open(dest, 'wb+') as f:
			f.write(contents)
		return dest

	def write_json_with_history(self, contents: Any, history_prefix: str, *path_args: str) -> str:
		return self.write_json(contents, *path_args)

	def write_json(self, contents: Any, *path_args: str) -> str:
		dest_folder = self.abspath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		with open(dest, 'w') as f:
			jsondump(contents, f, indent = 2, cls=BaseModelEncoder)
		return dest

	def write_spdx_with_history(self, spdx_doc_obj: SPDXDocument, history_prefix: str, *path_args: str) -> str:
		return self.write_spdx(spdx_doc_obj, *path_args)

	def write_spdx(self, spdx_doc_obj: SPDXDocument, *path_args: str) -> str:
		dest_folder = self.abspath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		write_spdx_tv(spdx_doc_obj, dest)
		return dest

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
