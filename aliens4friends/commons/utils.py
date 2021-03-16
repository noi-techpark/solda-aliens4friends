import subprocess
import sys
import os
import requests
import hashlib
from typing import List, Tuple, Type, Dict, Union, NoReturn

class ArchiveError(Exception):
    pass

class Archive:

	SUPPORTED_ARCHIVES = {
		".gz": {
			"tarparam": "z"
		},
		".xz": {
			"tarparam": "J"
		},
		".bz2": {
			"tarparam": "j"
		},
		".aliensrc": {
			"tarparam": "z"
		}
	}

	def __init__(self, archive_path):
		self.path = archive_path
		self.tar_param = Archive._get_tar_param(archive_path)
		self.is_supported()

	def is_supported(self):
		_, extension = os.path.splitext(self.path)
		if not extension in self.SUPPORTED_ARCHIVES:
			raise ArchiveError(f"Archive with extension {extension} is not supported!")

	def _make_tar_cmd(self, params):
		return bash(f'tar {self.tar_param}xvf {self.path} {params}')

	def readfile(self, file_path):
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=cat')
		result = stdout.split('\n')
		return result[0], result[1:]

	def checksums(self, file_path):
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=sha1sum')
		return Archive._parse_sha1sum(stdout)

	def in_archive_checksums(self, archive_in_archive, file_path=""):
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - {file_path} --to-command=sha1sum"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	def extract(self, dest):
		return self._make_tar_cmd(f'-C {dest} --strip 1')

	def in_archive_extract(self, archive_in_archive, dest):
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - -C {dest} --strip 1"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	@staticmethod
	def _get_tar_param(archive_name):
		_, extension = os.path.splitext(archive_name)
		try:
			return Archive.SUPPORTED_ARCHIVES[extension]["tarparam"]
		except KeyError:
			pass
		raise ArchiveError(f"Archive type unknown for {archive_name}.")

	@staticmethod
	def _parse_sha1sum(sha1stdout):
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
	def _check_next_endswith(lines, index, ends):
		if index >= len(lines) or index < 0 or not lines[index]:
			return False
		return lines[index].endswith(ends)



class UtilsError(Exception):
    pass

def md5(string: str) -> str:
    return hashlib.md5(string.encode('utf-8')).hexdigest()

def bash(
    command: str, cwd: str = None, exception: Type[Exception] = Exception
) -> Tuple[str, str]:
    """Run a command in bash shell, and return stdout and stderr
    :param command: the command to run
    :param cwd: directory where to run the command (defaults to current dir)
    :param exception: class to use to raise exceptions (defaults to 'Exception')
    :return: stdout and stderr of the command
    :raises: exception (see above) if command exit code != 0
    """
    out = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = out.stdout.decode()
    stderr = out.stderr.decode()
    if out.returncode != 0:
        raise exception(
            f"Command '{command}' failed. Output is:\n"
            f"{stdout}\n{stderr}"
        )
    return stdout, stderr

def bash_live(
    command: str,
    cwd: str = None,
    exception: Type[Exception] = Exception,
    prefix: str = ""
) -> NoReturn:
    """Run a command in bash shell in live mode to fetch output when it is available
    :param command: the command to run
    :param cwd: directory where to run the command (defaults to current dir)
    :param exception: Exception to raise when an error occurs
    :param prefix: Prefix of output streams
    """
    with subprocess.Popen(
        command, shell=True, executable="/bin/bash", cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True
    ) as proc:
        for line in iter(proc.stdout.readline, ''):
            out = line.strip()
            if not out:
                break
            print(f"{prefix} >>> {out}", end='\r\n')

        for line in iter(proc.stderr.readline, ''):
            out = line.strip()
            if not out:
                break
            print(f"{prefix} (ERROR) >>> {out}", end='\r\n')

        rc = proc.wait()
        if rc != 0:
            raise exception(f"{prefix} (ERROR) >>> Command {command} failed! Return code = {rc}")


def io_file_checksum(file_path):
    stdout, stderr = bash(
        f'sha1sum {file_path}'
    )
    return stdout.split(' ', 1)[0]
