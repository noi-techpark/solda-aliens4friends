# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import os
import logging
from json import dump as jsondump, load as jsonload
from pathlib import Path
from shutil import rmtree
from .utils import copy, mkdir
from .settings import Settings

logger = logging.getLogger(__name__)

class Pool:

	def __init__(self, basepath):
		super().__init__()
		self.basepath = os.path.abspath(basepath)
		self.mkdir()
		if not os.path.isdir(self.basepath):
			raise NotADirectoryError(
				f"Unable to create the POOL at path '{self.basepath}'."
			)

	def clnpath(self, path):
		if path.startswith(self.basepath):
			return path[len(self.basepath):]
		return path

	def mkdir(self, *sub_folder):
		return mkdir(self.abspath(*sub_folder))

	def relpath(self, *sub_folders):
		if sub_folders:
			return os.path.join(*sub_folders)
		return ""

	def abspath(self, *sub_folders):
		if sub_folders:
			return os.path.join(self.basepath, *sub_folders)
		return self.basepath

	def add(self, src, *path_args):
		dest = self.abspath(*path_args)
		pooldest = self.relpath(*path_args)
		dest_full = os.path.join(dest, os.path.basename(src))
		if os.path.isfile(dest_full) and Settings.POOLCACHED:
			logger.debug(f"Pool cache active and file {pooldest} exists... skipping!")
			return dest
		self.mkdir(dest)
		copy(src, dest_full)
		return dest

	def write(self, contents, *path_args):
		dest_folder = self.abspath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		with open(dest, 'wb+') as f:
			f.write(contents)
		return dest

	def write_json(self, contents, *path_args):
		dest_folder = self.abspath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		with open(dest, 'w') as f:
			jsondump(contents, f, indent = 2)
		return dest

	def get(self, *path_args):
		return self._get(False, *path_args)

	def get_binary(self, *path_args):
		return self._get(True, *path_args)

	def get_json(self, *path_args):
		path = self.abspath(*path_args)
		with open(path, "r") as f:
			return jsonload(f)

	def _get(self, binary, *path_args):
		path = self.abspath(*path_args)
		flag = "b" if binary else ""
		with open(path, f'r{flag}') as f:
			return f.read()

	def absglob(self, glob, *path_args):
		path = self.abspath(*path_args)
		return Path(path).rglob(glob)

	def relglob(self, glob, *path_args):
		path = self.relpath(*path_args)
		return Path(path).rglob(glob)

	def rm(self, *path_args):
		path = self.relpath(*path_args)
		if os.path.isdir(path):
			rmtree(path)
		elif os.path.isfile(path) or os.path.islink(path):
			os.remove(path)
