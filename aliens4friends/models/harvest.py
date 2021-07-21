# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel, BaseModelEncoder, ModelError
from .common import License, Tool, SourceFile
from typing import Any, Dict, List

class DebianMatchBasic(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		ip_matching_files: int = 0
	) -> None:
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


class LicenseFinding(BaseModel):
	def __init__(self, shortname: str = None, file_count: int = 0) -> None:
		self.shortname = License(shortname).encode()
		self.file_count = file_count

	def __lt__(self, o):
		if self.file_count < o.file_count:
			return True

		if self.file_count > o.file_count:
			return False

		return self.shortname < o.shortname


class AuditFindings(BaseModel):
	def __init__(
		self,
		main_licenses: List[str] = None,
		all_licenses: List[LicenseFinding] = None
	):
		self.main_licenses = [
			License(lic).encode() for lic in main_licenses
		] if main_licenses else []
		self.all_licenses = LicenseFinding.drilldown(all_licenses)

class StatisticsLicenses(BaseModel):
	def __init__(
		self,
		license_scanner_findings: List[LicenseFinding] = None,
		license_audit_findings: AuditFindings = None
	) -> None:
		self.license_scanner_findings = LicenseFinding.drilldown(license_scanner_findings)
		self.license_audit_findings = AuditFindings.decode(license_audit_findings)


class Statistics(BaseModel):
	def __init__(
		self,
		files: StatisticsFiles = None,
		licenses: StatisticsLicenses = None
	) -> None:
		self.files = StatisticsFiles.decode(files)
		self.licenses = StatisticsLicenses.decode(licenses)


class BinaryPackage(BaseModel):
	def __init__(
		self,
		name: str = None,
		version: str = None,
		revision: str = None,
		tags: List[str] = None
	) -> None:
		self.name = name
		self.version = version
		self.revision = revision
		self.tags = aggregate_tags(tags)


def aggregate_tags(tags: List[str]) -> Dict[str, Any]:
	if not tags:
		return {}

	keys = ['project', 'release', 'distro', 'machine', 'image']
	res = {key: set() for key in keys}
	for i, key in enumerate(keys):
		for elem in tags:
			try:
				res[key].add(elem.split("/")[i])
			except IndexError:
				pass
	return res


class SourcePackage(BaseModel):
	def __init__(
		self,
		id: str,
		name: str = None,
		version: str = None,
		revision: str = None,
		variant: str = None,
		debian_matching: DebianMatchBasic = None,
		source_files: List[SourceFile] = None,
		statistics: Statistics = None,
		binary_packages: List[BinaryPackage] = None,
		tags: List[str] = None
	):
		self.id = id
		self.name = name
		self.version = version
		self.revision = revision
		self.variant = variant
		self.debian_matching = DebianMatchBasic.decode(debian_matching)
		self.statistics = Statistics.decode(statistics)
		self.source_files = SourceFile.drilldown(source_files)
		self.binary_packages = BinaryPackage.drilldown(binary_packages)
		self.tags = aggregate_tags(tags)

class HarvestModel(BaseModel):

	def __init__(
		self,
		tool: Tool = None,
		source_packages: List[SourcePackage] = None
	) -> None:
		self.tool = Tool.decode(tool)
		self.source_packages = SourcePackage.drilldown(source_packages)
