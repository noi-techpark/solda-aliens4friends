
from typing import Union
from .base import BaseModel, BaseModelEncoder
from .common import License, Tool
from json import load as json_load


class SourceFile(BaseModel):
	def __init__(self, name: str, sha1: str, src_uri: str, files_in_archive: Union[int, bool]):
		self.name = name
		self.sha1 = sha1
		self.src_uri = src_uri
		self.files_in_archive = files_in_archive


class DebianMatch(BaseModel):
	def __init__(self, name: str, version: str, ip_matching_files: int = 0):
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
		*args, **kwargs # ignore this, we just need it for "total"
	):
		self.audit_total = audit_total
		self.audit_done = audit_done
		self.audit_to_do = audit_to_do
		self.upstream_source_total = upstream_source_total
		self.unknown_provenance = unknown_provenance
		self.known_provenance = known_provenance

	@property
	def total(self):
		return self.unknown_provenance + self.known_provenance


class AuditFindings(BaseModel):
	def __init__(self):
		self.main_licenses = None
		self.all_licenses = None


class StatisticsLicenses(BaseModel):
	def __init__(
		self,
		license_scanner_findings: list = None,
		license_audit_findings: list = None
	):
		self.license_scanner_findings = [
			LicenseFinding.from_json(licf) for licf in license_scanner_findings
		]
		self.license_audit_findings = AuditFindings()
		self.license_audit_findings.main_licenses = license_audit_findings["main_licenses"]
		self.license_audit_findings.all_licenses = [
			LicenseFinding.from_json(licf) for licf in license_audit_findings["all_licenses"]
		]


class Statistics(BaseModel):
	def __init__(
		self,
		files: StatisticsFiles = None,
		licenses: StatisticsLicenses = None
	):
		self.files = StatisticsFiles.from_json(files)
		self.licenses = StatisticsLicenses.from_json(licenses)


class LicenseFinding(BaseModel):
	def __init__(self, shortname: License, file_count: int):
		self.shortname = License(shortname)
		self.file_count = file_count


class BinaryPackage(BaseModel):
	def __init__(self, name: str, version: str, revision: str):
		self.name = name
		self.version = version
		self.revision = revision


class SourcePackage(BaseModel):
	def __init__(
		self,
		id: str,
		name: str,
		version: str,
		revision: str,
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
		self.debian_matching = DebianMatch.from_json(debian_matching)
		self.statistics = Statistics.from_json(statistics)
		self.source_files = [
			SourceFile.from_json(srcf) for srcf in source_files
		]
		self.binary_packages = [
			#FIXME We have a list in a list; remove outer list
			BinaryPackage.from_json(binp) for binp in binary_packages[0]
		]


class Harvest(BaseModel):

	def __init__(self, tool_name: str, tool_version: str, tool_parameters: str = None):
		self.tool = Tool(tool_name, tool_version, tool_parameters)
		self.source_packages = []

	@classmethod
	def from_file(cls, path):
		with open(path, "r") as f:
			j = json_load(f)

		try:
			parameters = j["tool"]["parameters"]
		except KeyError:
			parameters = None
		hrv = Harvest(j["tool"]["name"], j["tool"]["version"], parameters)

		for srcpckstr in j["source_packages"]:
			srcpck = SourcePackage.from_json(srcpckstr)
			hrv.source_packages.append(srcpck)

		return hrv
