# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import Tool
from typing import List, Dict, Optional

from deepdiff import DeepDiff

class MovedFile(BaseModel):
	def __init__(
		self,
		old_path: str,
		new_path: str
	):
		self.old_path = old_path
		self.new_path = new_path

class Body(BaseModel):
	def __init__(
		self,
		same_files: Optional[List[str]] = None,
		moved_files: Optional[List[MovedFile]] = None,
		changed_files_with_no_license_and_copyright: Optional[List[str]] = None,
		changed_files_with_same_copyright_and_license: Optional[List[str]] = None,
		changed_files_with_updated_copyright_year_only: Optional[Dict[str, DeepDiff]] = None,
		changed_files_with_changed_copyright_or_license: Optional[Dict[str, DeepDiff]] = None,
		deleted_files_with_no_license_and_copyright: Optional[List[str]] = None,
		deleted_files_with_license_or_copyright: Optional[List[str]] = None,
		new_files_with_no_license_and_copyright: Optional[List[str]] = None,
		new_files_with_license_or_copyright: Optional[List[str]] = None
	):
		self.same_files = same_files or []
		self.moved_files = moved_files or []
		self.changed_files_with_no_license_and_copyright = changed_files_with_no_license_and_copyright or []
		self.changed_files_with_same_copyright_and_license = changed_files_with_same_copyright_and_license or []
		self.changed_files_with_updated_copyright_year_only = changed_files_with_updated_copyright_year_only or {}
		self.changed_files_with_changed_copyright_or_license = changed_files_with_changed_copyright_or_license or {}
		self.deleted_files_with_no_license_and_copyright = deleted_files_with_no_license_and_copyright or []
		self.deleted_files_with_license_or_copyright = deleted_files_with_license_or_copyright or []
		self.new_files_with_no_license_and_copyright = new_files_with_no_license_and_copyright or []
		self.new_files_with_license_or_copyright = new_files_with_license_or_copyright or []


class Stats(BaseModel):
	def __init__(
		self,
		same_files: int = 0,
		moved_files: int = 0,
		changed_files_with_no_license_and_copyright: int = 0,
		changed_files_with_same_copyright_and_license: int = 0,
		changed_files_with_updated_copyright_year_only: int = 0,
		changed_files_with_changed_copyright_or_license: int = 0,
		deleted_files_with_no_license_and_copyright: int = 0,
		deleted_files_with_license_or_copyright: int = 0,
		new_files_with_no_license_and_copyright: int = 0,
		new_files_with_license_or_copyright: int = 0,
		old_files_count: int = 0,
		new_files_count: int = 0
	):
		self.same_files = same_files
		self.moved_files = moved_files
		self.changed_files_with_no_license_and_copyright = changed_files_with_no_license_and_copyright
		self.changed_files_with_same_copyright_and_license = changed_files_with_same_copyright_and_license
		self.changed_files_with_updated_copyright_year_only = changed_files_with_updated_copyright_year_only
		self.changed_files_with_changed_copyright_or_license = changed_files_with_changed_copyright_or_license
		self.deleted_files_with_no_license_and_copyright = deleted_files_with_no_license_and_copyright
		self.deleted_files_with_license_or_copyright = deleted_files_with_license_or_copyright
		self.new_files_with_no_license_and_copyright = new_files_with_no_license_and_copyright
		self.new_files_with_license_or_copyright = new_files_with_license_or_copyright
		self.old_files_count = old_files_count
		self.new_files_count = new_files_count

class Compared(BaseModel):
	def __init__(
		self,
		old_scan_out_file: Optional[str] = None,
		new_scan_out_file: Optional[str] = None
	):
		self.old_scan_out_file = old_scan_out_file
		self.new_scan_out_file = new_scan_out_file

class Header(BaseModel):
	def __init__(
		self,
		compared_json_files: Optional[Compared] = None,
		stats: Optional[Stats] = None
	):
		self.compared_json_files = Compared.decode(compared_json_files)
		self.stats = Stats.decode(stats)

class DeltaCodeModel(BaseModel):
	def __init__(
		self,
		tool: Optional[Tool] = None,
		header: Optional[Header] = None,
		body: Optional[Body] = None
	):
		self.tool = Tool.decode(tool)
		self.header = Header.decode(header)
		self.body = Body.decode(body)
