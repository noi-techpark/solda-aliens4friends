# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import License, Tool, SourceFile
from typing import Any, Dict, List, Optional, Set, Union

class DebianMatchBasic(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
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
	def __init__(self, shortname: Optional[str] = None, file_count: int = 0) -> None:
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
		main_licenses: Optional[List[str]] = None,
		all_licenses: Optional[List[LicenseFinding]] = None
	):
		self.main_licenses = [
			License(lic).encode() for lic in main_licenses
		] if main_licenses else []
		self.all_licenses = LicenseFinding.drilldown(all_licenses)

class StatisticsLicenses(BaseModel):
	def __init__(
		self,
		license_scanner_findings: Optional[List[LicenseFinding]] = None,
		license_audit_findings: Optional[AuditFindings] = None
	) -> None:
		self.license_scanner_findings = LicenseFinding.drilldown(license_scanner_findings)
		self.license_audit_findings = AuditFindings.decode(license_audit_findings)


class Statistics(BaseModel):
	def __init__(
		self,
		files: Optional[StatisticsFiles] = None,
		licenses: Optional[StatisticsLicenses] = None
	) -> None:
		self.files = StatisticsFiles.decode(files)
		self.licenses = StatisticsLicenses.decode(licenses)


class BinaryPackage(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
		revision: Optional[str] = None,
		tags: Optional[List[str]] = None
	) -> None:
		self.name = name
		self.version = version
		self.revision = revision
		self.tags = aggregate_tags(tags)


def aggregate_tags(tags: List[str]) -> Dict[str, Union[List[str], Set[str]]]:
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
	for key in keys:
		res[key] = sorted(res[key])
	for key in [ 'distro', 'image' ]:
		new = set()
		for tag in res[key]:
			for project in res['project']:
				tag = tag.replace(f'{project}-', '')
			new.add(tag)
		res[key] = sorted(new)
	return res


class SessionState(BaseModel):
	def __init__(
		self,
		selected: bool = True,
		selected_reason: Optional[str] = "",
		uploaded: Optional[bool] = None,
		uploaded_reason: Optional[str] = ""
	) -> None:
		self.selected = selected
		self.selected_reason = selected_reason
		self.uploaded = uploaded
		self.uploaded_reason = uploaded_reason

class SourcePackage(BaseModel):
	def __init__(
		self,
		id: str,
		name: Optional[str] = None,
		version: Optional[str] = None,
		revision: Optional[str] = None,
		variant: Optional[str] = None,
		debian_matching: Optional[DebianMatchBasic] = None,
		session_state: Optional[SessionState] = None,
		source_files: Optional[List[SourceFile]] = None,
		statistics: Optional[Statistics] = None,
		binary_packages: Optional[List[BinaryPackage]] = None,
		tags: Optional[ Dict[str, Union[List[str], Set[str]]] ] = None
	):
		self.id = id
		self.name = name
		self.version = version
		self.revision = revision
		self.variant = variant
		self.debian_matching = DebianMatchBasic.decode(debian_matching)
		self.session_state = SessionState.decode(session_state)
		self.statistics = Statistics.decode(statistics)
		self.source_files = SourceFile.drilldown(source_files)
		self.binary_packages = BinaryPackage.drilldown(binary_packages)
		self.tags = aggregate_tags(tags)

class HarvestModel(BaseModel):

	def __init__(
		self,
		tool: Optional[Tool] = None,
		source_packages: Optional[List[SourcePackage]] = None
	) -> None:
		self.tool = Tool.decode(tool)
		self.source_packages = SourcePackage.drilldown(source_packages)
