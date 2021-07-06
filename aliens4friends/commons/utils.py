# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>

import subprocess
from datetime import datetime
import sys
import os
import requests
import hashlib
import logging
import traceback
from typing import List, Tuple, Type, Dict, Union, NoReturn

def bash(
	command: str,
	cwd: str = None,
	exception: Type[Exception] = Exception
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
) -> None:
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
		stdout = []
		stderr = []
		for line in iter(proc.stdout.readline, ''):
			out = line.strip()
			if not out:
				break
			stdout.append(out)
			print(f"{prefix} >>> {out}", end='\r\n')

		for line in iter(proc.stderr.readline, ''):
			out = line.strip()
			if not out:
				break
			stderr.append(out)
			print(f"{prefix} (ERROR) >>> {out}", end='\r\n')

		rc = proc.wait()
		if rc != 0:
			raise exception(
				f"{prefix} (ERROR) >>> Command {command} failed! Return code = {rc}",
				"\n".join(stdout),
				"\n".join(stderr)
			)

def sha1sum(file_path: str) -> str:
	stdout, stderr = bash(
		f'sha1sum {file_path}'
	)
	return stdout.split(' ', 1)[0]

def copy(src_filename: str, dst_filename: str) -> None:
	with open(src_filename, 'rb') as fr:
		with open(dst_filename, 'wb') as fw:
			fw.write(fr.read())

def mkdir(*sub_folders: str) -> str:
	path = os.path.join(*sub_folders)
	os.makedirs(
		path,
		mode = 0o755,
		exist_ok = True
	)
	return path

def md5(string: str) -> str:
	return hashlib.md5(string.encode('utf-8')).hexdigest()

def sha1sum_str(string):
    return hashlib.sha1(string.encode('utf-8')).hexdigest()

def get_prefix_formatted(date_time: datetime = None) -> str:
	date_time = date_time or datetime.now()
	return date_time.strftime("%Y%m%d-%H%M%S_")

def debug_with_stacktrace(logger: logging.Logger):
	if logger.getEffectiveLevel() == logging.DEBUG:
		logger.debug(traceback.format_exc())

def log_minimal_error(logger: logging.Logger, ex: Exception, prefix: str = ""):
	logger.error(f"{prefix}{ex.__class__.__name__}: {ex}")
	debug_with_stacktrace(logger)
