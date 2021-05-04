# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

from .utils import bash
from os.path import splitext
from typing import Dict, Tuple, List

class ArchiveError(Exception):
	pass

class Archive:

	SUPPORTED_ARCHIVES: Dict[str, Dict[str, str]] = {
		".gz": {
			"tarparam": "z"
		},
		".tgz": {
			"tarparam": "z"
		},
		".xz": {
			"tarparam": "J"
		},
		".bz2": {
			"tarparam": "j"
		},
		".aliensrc": {
			"tarparam": ""
		}
	}

	def __init__(self, archive_path: str) -> None:
		self.path: str = archive_path
		self.tar_param: str = Archive._get_tar_param(archive_path)
		self.is_supported()

	def is_supported(self) -> None:
		_, extension = splitext(self.path)
		if not extension in self.SUPPORTED_ARCHIVES:
			raise ArchiveError(f"Archive with extension {extension} is not supported!")

	def _make_tar_cmd(self, params: str) -> Tuple[str, str]:
		return bash(f'tar {self.tar_param}xvf {self.path} {params}', exception=ArchiveError)

	def readfile(self, file_path: str) -> List[str]:
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=cat')
		return stdout.split('\n')[1:]

	def checksums(self, file_path: str) -> Dict[str, str]:
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=sha1sum')
		return Archive._parse_sha1sum(stdout)

	def in_archive_checksums(self, archive_in_archive: str, file_path: str = "") -> Dict[str, str]:
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - {file_path} --to-command=sha1sum"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	def in_archive_rootfolder(self, archive_in_archive: str) -> str:
		"""Get internal archive rootfolder, eg. 'foo-1.0.0/'"""
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}tf -"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}" | grep -v -E "^files/" | cut -d"/" -f 1 | uniq')
		r = stdout.split('\n')
		if '' in r:
			r.remove('')
		if len(r) != 1:
			return '' # suited to be used with (and ignored by) os.path.join
		return r[0]

	def rootfolder(self) -> str:
		"""Get archive rootfolder, eg. 'foo-1.0.0/'"""
		stdout, _ = bash(f'tar {self.tar_param}tf {self.path} | cut -d"/" -f 1 | uniq')
		r = stdout.split('\n')
		if '' in r:
			r.remove('')
		if len(r) != 1:
			return '' # suited to be used with (and ignored by) os.path.join
		return r[0]

	def extract(self, dest: str) -> Tuple[str, str]:
		return self._make_tar_cmd(f'-C {dest} --strip 1')

	def extract_raw(self, dest: str) -> Tuple[str, str]:
		return self._make_tar_cmd(f'-C {dest}')

	def in_archive_extract(self, archive_in_archive: str, dest: str) -> Dict[str, str]:
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - -C {dest} --strip 1"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	def list(self) -> List[str]:
		stdout, _ = bash(f'tar {self.tar_param}tf {self.path}', exception=ArchiveError)
		l = stdout.split('\n')
		if '' in l:
			l.remove('')
		return l

	@staticmethod
	def _get_tar_param(archive_name: str) -> str:
		_, extension = splitext(archive_name)
		try:
			return Archive.SUPPORTED_ARCHIVES[extension]["tarparam"]
		except KeyError:
			pass
		raise ArchiveError(f"Archive type unknown for {archive_name}.")

	@staticmethod
	def _parse_sha1sum(sha1stdout: str) -> Dict[str, str]:
		lines = sha1stdout.split('\n')
		files = {}
		i = 0
		while i < len(lines):
			if (
				lines[i].endswith('/')
				or not Archive._check_next_endswith(lines, i+1, '-')
			):
				i += 1
				continue
			path = '/'.join(lines[i].split('/')[1:])
			files[path] = lines[i+1].split(' ', 1)[0]
			i += 2
		return files

	@staticmethod
	def _check_next_endswith(lines: List[str], index: int, ends: str) -> bool:
		if index >= len(lines) or index < 0 or not lines[index]:
			return False
		return lines[index].endswith(ends)
