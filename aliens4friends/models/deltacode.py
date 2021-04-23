from .base import BaseModel
from .common import Tool

class Body(BaseModel):
	def __init__(
		self,
		same_files: list = None,
		moved_files: list = None,
		changed_files_with_no_license_and_copyright: list = None,
		changed_files_with_same_copyright_and_license: list = None,
		changed_files_with_updated_copyright_year_only: list = None,
		changed_files_with_changed_copyright_or_license: list = None,
		deleted_files_with_no_license_and_copyright: list = None,
		deleted_files_with_license_or_copyright: list = None,
		new_files_with_no_license_and_copyright: list = None,
		new_files_with_license_or_copyright: list = None
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
		old_scan_out_file: str = None,
		new_scan_out_file: str = None
	):
		self.old_scan_out_file = old_scan_out_file
		self.new_scan_out_file = new_scan_out_file

class Header(BaseModel):
	def __init__(
		self,
		compared_json_files: Compared = None,
		stats: Stats = None
	):
		self.compared_json_files = Compared.decode(compared_json_files)
		self.stats = Stats.decode(stats)

class DeltaCodeModel(BaseModel):
	def __init__(
		self,
		tool: Tool = None,
		header: Header = None,
		body: Body = None
	):
		self.tool = Tool.decode(tool)
		self.header = Header.decode(header)
		self.body = Body.decode(body)
