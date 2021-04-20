
from typing import Union
from .base import BaseModel, BaseModelEncoder, ModelError
from .common import License, Tool
from json import load as json_load


class SourceFile(BaseModel):
	def __init__(self, name: str = None, sha1: str = None, src_uri: str = None, files_in_archive: Union[int, bool] = False):
		self.name = name
		self.sha1 = sha1
		self.src_uri = src_uri
		self.files_in_archive = files_in_archive


class DebianMatch(BaseModel):
	def __init__(self, name: str = None, version: str = None, ip_matching_files: int = 0):
		self.name = name
		self.version = version
		self.ip_matching_files = ip_matching_files


class StatisticsFiles(BaseModel):
	def __init__(
		self,
		audit_total: int = 0,
		audit_done: int = 0,
		audit_to_do: int = 0,
		upstream_source_total: int = 0,
		unknown_provenance: int = 0,
		known_provenance: int = 0,
		total: int = 0
	):
		self.audit_total = audit_total
		self.audit_done = audit_done
		self.audit_to_do = audit_to_do
		self.upstream_source_total = upstream_source_total
		self.unknown_provenance = unknown_provenance
		self.known_provenance = known_provenance
		self.total = total


class AuditFindings(BaseModel):
	def __init__(self, main_licenses: list = None, all_licenses: list = None):
		self.main_licenses = [
			License(lic) for lic in main_licenses
		] if main_licenses else []
		self.all_licenses = all_licenses if all_licenses else []

class StatisticsLicenses(BaseModel):
	def __init__(
		self,
		license_scanner_findings: list = None,
		license_audit_findings: list = None
	):
		self.license_scanner_findings = license_scanner_findings if license_scanner_findings else []
		self.license_audit_findings = license_audit_findings if license_audit_findings else []


class Statistics(BaseModel):
	def __init__(
		self,
		files: StatisticsFiles = None,
		licenses: StatisticsLicenses = None
	):
		self.files = files if files else StatisticsFiles()
		self.licenses = licenses if licenses else StatisticsLicenses()


class LicenseFinding(BaseModel):
	def __init__(self, shortname: str = None, file_count: int = 0):
		self.shortname = License(shortname).encode()
		self.file_count = file_count

	def __lt__(self, o):
		if self.file_count < o.file_count:
			return True

		if self.file_count > o.file_count:
			return False

		return self.shortname < o.shortname


class BinaryPackage(BaseModel):
	def __init__(self, name: str = None, version: str = None, revision: str = None):
		self.name = name
		self.version = version
		self.revision = revision


class SourcePackage(BaseModel):
	def __init__(
		self,
		id: str,
		name: str = None,
		version: str = None,
		revision: str = None,
		debian_matching: DebianMatch = None,
		source_files: list = None,
		statistics: Statistics = None,
		binary_packages: list = None,
		tags: dict = None
	):
		self.id = id
		self.name = name
		self.version = version
		self.revision = revision
		self.tags = tags
		self.debian_matching = debian_matching if debian_matching else DebianMatch()
		self.statistics = statistics if statistics else Statistics()
		self.source_files = [
			SourceFile.from_json(srcf) for srcf in source_files
		] if source_files else []
		self.binary_packages = [
			#FIXME We have a list in a list; remove outer list
			BinaryPackage.from_json(binp) for binp in binary_packages[0]
		] if binary_packages else []


class Harvest(BaseModel):

	def __init__(self, tool_name: str = None, tool_version: str = None, tool_parameters: str = None):
		self.tool = Tool(tool_name, tool_version, tool_parameters)
		self.source_packages = []

	@classmethod
	def from_file(cls, path):
		with open(path, "r") as f:
			j = json_load(f)

		hrv = Harvest(**j["tool"])

		for srcpckstr in j["source_packages"]:
			srcpck = SourcePackage.from_json(srcpckstr)
			hrv.source_packages.append(srcpck)

		return hrv

	def add_source_package(self, source_package: SourcePackage):
		self.source_packages.append(source_package)
