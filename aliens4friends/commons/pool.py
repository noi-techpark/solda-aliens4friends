import os
from .utils import copy, mkdir

class Pool:

	def __init__(self, basepath):
		super().__init__()
		self.basepath = os.path.abspath(basepath)
		self.mkdir()
		if not os.path.isdir(self.basepath):
			raise NotADirectoryError(
				f"Unable to create the POOL at path '{self.basepath}'."
			)

	def mkdir(self, *sub_folder):
		return mkdir(self.subpath(*sub_folder))

	def subpath(self, *sub_folders):
		if sub_folders:
			return os.path.join(self.basepath, *sub_folders)
		return self.basepath

	def add(self, src, *path_args):
		dest = self.subpath(*path_args)
		self.mkdir(dest)
		copy(src, os.path.join(dest, os.path.basename(src)))
		return dest

	def write(self, contents, *path_args):
		dest_folder = self.subpath(*path_args[:-1])
		dest = os.path.join(dest_folder, path_args[-1])
		self.mkdir(dest_folder)
		with open(dest, 'wb+') as f:
			f.write(contents)
		return dest

	def get(self, *path_args):
		return self._get(False, *path_args)

	def get_binary(self, *path_args):
		return self._get(True, *path_args)

	def _get(self, binary, *path_args):
		path = self.subpath(*path_args)
		flag = "b" if binary else ""
		with open(path, f'r{flag}') as f:
			return f.read()
