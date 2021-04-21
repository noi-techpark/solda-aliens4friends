from .base import BaseModel, BaseModelEncoder, ModelError
from .common import License, Tool, SourceFile

class DebianMatchBasic(BaseModel):
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
	def __init__(
		self,
		main_licenses: list = None,
		all_licenses: list = None
	):
		self.main_licenses = [
			License(lic).encode() for lic in main_licenses
		] if main_licenses else []
		self.all_licenses = self.drilldown(all_licenses, LicenseFinding)

class StatisticsLicenses(BaseModel):
	def __init__(
		self,
		license_scanner_findings: list = None,
		license_audit_findings: AuditFindings = None
	):
		self.license_scanner_findings = self.drilldown(license_scanner_findings, LicenseFinding)
		self.license_audit_findings = self.decode(license_audit_findings, AuditFindings)


class Statistics(BaseModel):
	def __init__(
		self,
		files: StatisticsFiles = None,
		licenses: StatisticsLicenses = None
	):
		self.files = self.decode(files, StatisticsFiles)
		self.licenses = self.decode(licenses, StatisticsLicenses)


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
		debian_matching: DebianMatchBasic = None,
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
		self.debian_matching = self.decode(debian_matching, DebianMatchBasic)
		self.statistics = self.decode(statistics, Statistics)
		self.source_files = self.drilldown(source_files, SourceFile)

		#FIXME This is a hack! We have a list in a list; remove outer list
		if (
			binary_packages
			and isinstance(binary_packages, list)
			and len(binary_packages) > 0
			and isinstance(binary_packages[0], list)
		):
			binary_packages = binary_packages[0]

		self.binary_packages = self.drilldown(binary_packages, BinaryPackage)


class HarvestModel(BaseModel):

	def __init__(
		self,
		tool: Tool = None,
		source_packages: list = None
	):
		self.tool = self.decode(tool, Tool)
		self.source_packages = source_packages if source_packages else []
