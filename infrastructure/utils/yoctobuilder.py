#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from typing import Tuple, Type

import yaml

PROGNAME = "yoctobuilder"

def main():
	print("YOCTO BUILDER: started...", flush=True)

	parser = argparse.ArgumentParser(
		prog=PROGNAME,
		conflict_handler='resolve',
	)
	parser.add_argument(
		"configyaml",
		help="Configuration yaml file",
		default="yoctobuilder.yml",
		nargs="?"
	)
	args = parser.parse_args()

	with open(args.configyaml, 'r') as f:
		yml = yaml.safe_load(f)

	print("YOCTO BUILDER: Yaml parsed...", flush=True)

	cache_dir = yml['cache_dir']
	failed_flavours = []

	for flavour_id, flavour in yml['flavours'].items():

		if os.path.isfile(f'.success-yoctobuild-{flavour_id}'):
			print(f'{flavour_id} already exists... skipping')
			continue

		amount = len(flavour['machines']) * len(flavour['images'])
		count = 0
		failed = 0
		templateconf = f"TEMPLATECONF=../oniro/flavours/{flavour_id} "
		print(f'YOCTO BUILDER: Processing flavour {flavour_id} (with {amount} machine/image combinations)', flush=True)
		for machine_id in flavour['machines']:

			print(f'YOCTO BUILDER: [{flavour_id}] Processing machine {machine_id}')
			if os.path.isfile(f'.success-yoctobuild-{flavour_id}-{machine_id}'):
				print(f'{flavour_id}-{machine_id} already exists... skipping')
				continue

			bash(
				f"{templateconf} . ./oe-core/oe-init-build-env build-{flavour_id}-{machine_id}"
			)
			_conf_update(flavour_id, machine_id, cache_dir, flavour['configs'])

			for image_id in flavour['images']:
				print(f'YOCTO BUILDER: [{flavour_id}][{machine_id}] Processing image {image_id}', flush=True)
				if os.path.isfile(f'.success-yoctobuild-{flavour_id}-{machine_id}-{image_id}'):
					print(f'{flavour_id}-{machine_id}-{image_id} already exists... skipping')
					continue
				try:
					bash_live(
						f'{templateconf} . ./oe-core/oe-init-build-env build-{flavour_id}-{machine_id}; '
						f'bitbake {image_id}'
					)
					count += 1
					print(f'YOCTO BUILDER: {count}/{amount} done!')
					bash(f'touch .success-yoctobuild-{flavour_id}-{machine_id}-{image_id}')
					try:
						bash(f'rm .failure-yoctobuild-{flavour_id}-{machine_id}-{image_id}')
					except:
						pass
				except Exception:
					bash(f'touch .failure-yoctobuild-{flavour_id}-{machine_id}-{image_id}')
					failed += 1

			if failed == 0:
				bash(f'touch .success-yoctobuild-{flavour_id}-{machine_id}')

		if failed == 0:
			bash(f'touch .success-yoctobuild-{flavour_id}')
		else:
			failed_flavours.append(flavour_id)

	print("YOCTO BUILDER: READY. Summary:")
	out, _ = bash('ls .success-yoctobuild* .failure-yoctobuild* 2>/dev/null | sort')
	print(out)
	if not failed_flavours:
		sys.exit(0)
	else:
		sys.stderr.write(f"There are failed builds for {', '.join(failed_flavours)}\n")
		sys.exit(1)


def _conf_update(flavour, machine, cache_dir, configs = None):
	#FIXME We should copy the first local.conf to local.conf.orig and for each step
	#      use that for substitution, and not re-substitute already changed files,
	#      which could lead to unknown errors.
	filepath = f'build-{flavour}-{machine}/conf/local.conf'
	if not os.path.isfile(f'{filepath}.bak'):
		bash(f'cp {filepath} {filepath}.bak')

	CONF_PARAMS = [
		f'MACHINE ?= "{machine}"',
		'#INHERIT += "own-mirrors"',
		'#SOURCE_MIRROR_URL',
		'#SSTATE_MIRRORS',
		f'SSTATE_DIR ?= "{cache_dir}/sstate-cache"',
		f'DL_DIR ?= "{cache_dir}/downloads"'
	]

	conf_params = { c: False for c in CONF_PARAMS }

	with open(filepath, "w") as fout:
		orig_lines = []
		vars_changed = []
		with open(f"{filepath}.bak", "r") as fin:
			for line in fin:
				orig_lines.append(line)
				for par in conf_params:
					p = par.split()
					var = " ".join(p[:2])
					if par.startswith("#") and line.startswith(par[1:]):
						conf_params[par] = True
						line = f"#{line}" # comment out
					elif (
						len(p) > 2
						and line.startswith(var)
						or (line.startswith(f"#{var}") and var not in vars_changed)
					):
						conf_params[par] = True
						vars_changed.append(var)
						line = f"{par}\n"
					elif len(p) < 3 and line.startswith(f"#{par}"):
							conf_params[par] = True
							line = line[1:] # uncomment

				fout.write(line)
		cfglist = configs['_all'] if '_all' in configs else []
		cfglist += configs[machine] if machine in configs else []
		cfglist += [
			par for par, found in conf_params.items()
			if (not found) and len(par.split()) > 2 and (not par.startswith("#"))
		]
		for line in cfglist:
			if line not in orig_lines:
				fout.write(f'\n{line}\n')


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
		stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
		universal_newlines=True
	) as proc:
		while True:
			output = proc.stdout.readline()
			if output == '' and proc.poll() is not None:
				break
			out = output.strip()
			if out:
				print(out, flush=True)

		rc = proc.wait()
		if rc != 0:
			raise exception(
				f"{prefix} (ERROR) >>> Command {command} failed! Return code = {rc}"
			)

if __name__ == "__main__":
	main()
