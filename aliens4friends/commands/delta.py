# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import os
import json
import re
import sys
import logging
from datetime import datetime
import difflib
from multiprocessing import Pool as MultiProcessingPool
from typing import List, Dict, Any, Generator
from pathlib import Path

from deepdiff import DeepDiff

from aliens4friends.commons.pool import Pool
from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

SCANCODE_VERSION = '3.2.3'

RELEVANT_FINDINGS = [
	'licenses',
	'license_expressions',
	'copyrights',
]

EMPTY_FILE_SHA1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

def get_word_list(string: str) -> List[str]:
	p = re.compile('[^\d\w]')
	only_alphanumerical_chars_str = p.sub(' ', string)
	return only_alphanumerical_chars_str.split()

def is_year(year: str) -> bool:
	if year and year.isdigit():
		return (int(year) >=1900 and int(year) <= datetime.now().year)
	else:
		return False

def get_changed_new_deleted_words(old: list, new: list) -> List[str]:
	changed_new_deleted_words = []
	d = difflib.Differ()
	diffs = d.compare(old, new)
	for diff in diffs:
		if diff.startswith('+ ') or diff.startswith('- '):
			changed_new_deleted_words.append(diff[2:])
	return changed_new_deleted_words

def only_copyright_year_has_been_updated(findings_diff: dict) -> bool:
	"""Check scan out DeepDiff to see if only copyright year has been updated
	for a specific file and no other changes have been made to license and
	copyright statements.

	Apart from values_changed, DeepDiff checks if there are also items added or
	removed etc. (see https://zepworks.com/deepdiff/current/basics.html) but
	here we
	1) look for diffs where there are *only* values_changed
	2) check if those values_changed affect only copyright statements
	3) check if the only changed word element in the copyright statement is the
	copyright year
	"""
	if not findings_diff.get('values_changed'):
		return False
	for diff_type in findings_diff:
		if diff_type != 'values_changed':
			return False
	for elem, diff in findings_diff['values_changed'].items():
		if not elem.startswith("root['copyrights']"):
			return False
		if elem.endswith("['value']"):
			old = get_word_list(diff['old_value'])
			new = get_word_list(diff['new_value'])
		else:
			old = get_word_list(diff['old_value']['value'])
			new = get_word_list(diff['new_value']['value'])
		changed_new_deleted_words = get_changed_new_deleted_words(old, new)
		for word in changed_new_deleted_words:
			if not is_year(word):
				return False
	return True

def get_paths_and_relevant_findings(scan_out: dict) -> Dict[str, Dict[str, Any]]:
	root = scan_out['files'][0]['path']
	p = re.compile(f'^{root}/')
	paths_and_relevant_findings = {}
	for file in scan_out['files']:
		if file['type'] != 'file':
			continue
		path = p.sub('', file['path']) # remove root folder from path
		findings = {f: file[f] for f in RELEVANT_FINDINGS}
		paths_and_relevant_findings.update({
			path: {'sha1': file['sha1'], 'findings': findings}
		})
	return paths_and_relevant_findings

def any_dict_value(d: dict) -> bool:
	"""Returns true if any key in dictionary contains a non-empty value"""
	return any([d[k] for k in d])

class DeltaCodeNGException(Exception):
	pass

class DeltaCodeNG:

	def __init__(self, old_scan_out_file: str, new_scan_out_file: str, result_file: str) -> None:
		"""Class to compare two scancode json output files resulting from the
		scan of two similar package versions, in order to assess their
		similarity as to license and copyright statements.
		It aims at replacing the unmaintaned eltaCode project, but it's very
		early stage, for now.
		It leverarages the power of DeepDiff to compare different objects:
		https://zepworks.com/deepdiff/current/diff.html

		:param old_scan_out_file: scancode json output filename generated by the
		scan of the older version of a package
		:param new_scan_out_file: scancode json output filename generated by the
		scan of the newer version of the same package
		:param result_file: filename where to output deltacode results (in json
		format)

		Example usage:
		d = DeltaCodeNG('foo-1.1.0.json', 'foo-1.1.4.json', results.json')
		d.compare()
		d.write_results()
		print(f'Results written to results.json')
		print('Stats:')
		d.print_stats()
		"""
		self.old = self._import(old_scan_out_file)
		self.new = self._import(new_scan_out_file)
		self.new_sha1_map = { v['sha1']: path for path, v in self.new.items() }
		# TODO: create a model class for results
		self.res = {
			"tool": {
				"name": __name__,
				"version": Settings.VERSION
			},
			'header': {
				'compared_json_files': {
					'old_scan_out_file': old_scan_out_file,
					'new_scan_out_file': new_scan_out_file,
				},
				'stats': {}
			},
			'body': {
				'same_files': [],
				'moved_files': {},
				'changed_files_with_no_license_and_copyright': [],
				'changed_files_with_same_copyright_and_license': [],
				'changed_files_with_updated_copyright_year_only': {},
				'changed_files_with_changed_copyright_or_license': {},
				'deleted_files_with_no_license_and_copyright': [],
				'deleted_files_with_license_or_copyright': [],
				'new_files_with_no_license_and_copyright': [],
				'new_files_with_license_or_copyright': [],
			}
		}
		self.result_file = result_file

	def _import(self, scan_out_file: str) -> dict:
		with open(scan_out_file) as f:
			scan_out = json.load(f)
		if (
			scan_out['headers'][0]['tool_name'] == "scancode-toolkit"
			and scan_out['headers'][0]['tool_version'] == SCANCODE_VERSION
		):
			return get_paths_and_relevant_findings(scan_out)
		else:
			raise DeltaCodeNGException(
				f'wrong ScanCode version for {scan_out_file},'
				f' must be {SCANCODE_VERSION}'
			)

	def _fix_finding_diffs_for_json_serialization(self, findings_diff: dict) -> None:
		if findings_diff.get("type_changes"):
			del findings_diff["type_changes"]

	def compare(self) -> dict:
		moved = []
		for path in self.old:
			sha1 = self.old[path]['sha1']
			if (sha1 != EMPTY_FILE_SHA1
					and sha1 in self.new_sha1_map
					and path != self.new_sha1_map[sha1]):
				old_path = path
				new_path = self.new_sha1_map[sha1]
				self.res['body']['moved_files'].update({
					'old_path': old_path,
					'new_path': new_path
				})
				moved.append(new_path)
			if self.new.get(path):
				if (self.old[path]['sha1'] == self.new[path]['sha1']):
					self.res['body']['same_files'].append(path)
				else:
					findings_diff = DeepDiff(
						self.old[path]['findings'],
						self.new[path]['findings'],
						ignore_order=True,
						exclude_regex_paths = r"root\['[^']+'\]\[\d+\]\['\w+_line'\]"
					)
					if not findings_diff:
						if not any_dict_value(self.old[path]['findings']):
							self.res['body']['changed_files_with_no_license_and_copyright'].append(path)
						else:
							self.res['body']['changed_files_with_same_copyright_and_license'].append(path)
					elif only_copyright_year_has_been_updated(findings_diff):
						self._fix_finding_diffs_for_json_serialization(findings_diff)
						self.res['body']['changed_files_with_updated_copyright_year_only'].update({path: findings_diff})
					else:
						self._fix_finding_diffs_for_json_serialization(findings_diff)
						self.res['body']['changed_files_with_changed_copyright_or_license'].update({path: findings_diff})
			else:
				if not any_dict_value(self.old[path]['findings']):
					self.res['body']['deleted_files_with_no_license_and_copyright'].append(path)
				else:
					self.res['body']['deleted_files_with_license_or_copyright'].append(path)
		for path in self.new:
			if not self.old.get(path) and path not in moved:
				if not any_dict_value(self.new[path]['findings']):
					self.res['body']['new_files_with_no_license_and_copyright'].append(path)
				else:
					self.res['body']['new_files_with_license_or_copyright'].append(path)
		self.add_stats()
		return self.res

	def add_stats(self) -> None:
		for k,v in self.res['body'].items():
			self.res['header']['stats'].update({k: len(v)})
		self.res['header']['stats'].update({
			'old_files_count': len(list(self.old.keys())),
			'new_files_count': len(list(self.new.keys()))
		})

	def print_stats(self) -> None:
		for stat in self.get_stats():
			print(stat)

	def get_stats(self) -> Generator[str, None, None]:
		for k,v in self.res['body'].items():
			yield (f'{k}: {len(v)}')

	def write_results(self) -> None:
		with open(self.result_file, "w") as f:
			json.dump(self.res, f, indent=2)

	@staticmethod
	def execute(glob_name: str = "*", glob_version: str = "*") -> None:
		pool = Pool(Settings.POOLPATH)
		multiprocessing_pool = MultiProcessingPool()
		multiprocessing_pool.map(  #pytype: disable=wrong-arg-types
			DeltaCodeNG._execute,
			pool.absglob(f"userland/{glob_name}/{glob_version}/*.alienmatcher.json")
		)

	@staticmethod
	def _execute(path: Path) -> None:
		pool = Pool(Settings.POOLPATH)
		package = f"{path.parts[-3]}-{path.parts[-2]}"
		try:
			with open(path, "r") as jsonfile:
				j = json.load(jsonfile)
		except Exception as ex:
			logger.error(f"[{package}] Unable to load json from {path}.")
			return

		try:
			m = j["debian"]["match"]
			a = j["aliensrc"]
			result_path = pool.relpath(
				"userland",
				a["name"],
				a["version"],
				f'{a["name"]}-{a["version"]}.deltacode.json'
			)
			if os.path.isfile(result_path) and Settings.POOLCACHED:
				logger.debug(f"[{package}] Skip {pool.clnpath(result_path)}. Result exists and cache is enabled.")
				return
			logger.info(
				f"[{package}] calculating delta between debian package"
				f" {m['name']}-{m['version']} and alien package"
				f" {a['name']}-{a['version']}"
			)
			deltacode = DeltaCodeNG(
				pool.relpath(
					"debian",
					m["name"],
					m["version"],
					f'{m["name"]}-{m["version"]}.scancode.json'
				),
				pool.relpath(
					"userland",
					a["name"],
					a["version"],
					f'{a["name"]}-{a["version"]}.scancode.json'
				),
				result_path
			)
			result = deltacode.compare()
			deltacode.write_results()
			logger.debug(f'[{package}] Results written to {result_path}')
			for stat in deltacode.get_stats():
				logger.debug(f'[{package}] Stats: {stat}')
			if Settings.PRINTRESULT:
				print(json.dumps(result, indent=2))
		except KeyError as ex:
			if not j["debian"].get("match"):
				logger.warning(f"[{package}] no debian match to compare here")
			else:
				logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
		except Exception as ex:
			logger.error(f"[{package}] {ex.__class__.__name__}: {ex}")
