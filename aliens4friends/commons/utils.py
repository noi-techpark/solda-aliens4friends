import subprocess
import sys
import os
import requests
import hashlib
from typing import List, Tuple, Type, Dict, Union, NoReturn

SUPPORTED_ARCHIVES = {
    ".gz": {
        "tarparam": "z"
    },
    ".xz": {
        "tarparam": "J"
    },
    ".bz2": {
        "tarparam": "j"
    }
}

def is_supported_archive(archive):
    _, extension = os.path.splitext(archive)
    return extension in SUPPORTED_ARCHIVES

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

def archive_readfile(archive_path, file_path):
    stdout, stderr = bash(
        f'tar {_get_tar_param(archive_path)}xvf {archive_path} {file_path} --to-command=cat'
    )
    result = stdout.split('\n')
    return result[0], result[1:]

def archive_checksums(archive_path, file_path):
    stdout, stderr = bash(
        f'tar {_get_tar_param(archive_path)}xvf {archive_path} {file_path} --to-command=sha1sum'
    )
    return _parse_sha1sum(stdout)

def archive_in_archive_checksums(archive_path, archive_in_archive, file_path=""):
    stdout, stderr = bash(
        f'tar {_get_tar_param(archive_path)}xvf {archive_path} {archive_in_archive} --to-command="tar {_get_tar_param(archive_in_archive)}xvf - {file_path} --to-command=sha1sum"'
    )
    return _parse_sha1sum(stdout)

def archive_extract(archive_path, dest):
    stdout, stderr = bash(
        f"tar {_get_tar_param(archive_path)}xvf {archive_path} -C {dest} --strip 1"
    )
    return stdout, stderr

def archive_in_archive_extract(archive_path, archive_in_archive, dest):
    stdout, stderr = bash(
        f'tar {_get_tar_param(archive_path)}xvf {archive_path} {archive_in_archive} --to-command="tar {_get_tar_param(archive_in_archive)}xvf - -C {dest} --strip 1"'
    )
    return _parse_sha1sum(stdout)

def _get_tar_param(archive_name):
    _, extension = os.path.splitext(archive_name)
    try:
        return SUPPORTED_ARCHIVES[extension]["tarparam"]
    except KeyError:
        pass
    raise UtilsError(f"Archive type unknown for {archive_name}.")

def _parse_sha1sum(sha1stdout):
    lines = sha1stdout.split('\n')
    files = {}
    i = 0
    while i < len(lines):
        if lines[i].endswith('/') or not _check_next_endswith(lines, i+1, '-'):
            i += 1
            continue
        path = '/'.join(lines[i].split('/')[1:])
        files[path] = lines[i+1].split(' ', 1)[0]
        i += 2
    return files

def _check_next_endswith(lines, index, ends):
    if index >= len(lines) or index < 0 or not lines[index]:
        return False
    return lines[index].endswith(ends)
