# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from typing import List, Dict, Optional

class FossySummary(BaseModel):
	def __init__(
		self,
		id: int = 0,
		uniqueLicenses: int = 0,
		totalLicenses: int = 0,
		uniqueConcludedLicenses: int = 0,
		totalConcludedLicenses: int = 0,
		filesToBeCleared: int = 0,
		filesCleared: int = 0,
		copyrightCount: int = 0,
		clearingStatus: Optional[str] = None,
		uploadName: Optional[str] = None,
		mainLicense: Optional[str] = None
	):
		self.id = id
		self.uniqueLicenses = uniqueLicenses
		self.totalLicenses = totalLicenses
		self.uniqueConcludedLicenses = uniqueConcludedLicenses
		self.totalConcludedLicenses = totalConcludedLicenses
		self.filesToBeCleared = filesToBeCleared
		self.filesCleared = filesCleared
		self.copyrightCount = copyrightCount
		self.clearingStatus = clearingStatus
		self.uploadName = uploadName
		self.mainLicense = mainLicense

class FossyLicenseFinding(BaseModel):
	def __init__(
		self,
		filePath: Optional[str] = None,
		agentFindings: Optional[List[str]] = None,
		conclusions: Optional[List[str]] = None
	):
		self.filePath = filePath
		self.agentFindings = agentFindings
		self.conclusions = conclusions


class FossyModel(BaseModel):
	def __init__(
		self,
		origin: Optional[str] = None,
		metadata: Optional[Dict[str, str]] = None,
		summary: Optional[FossySummary] = None,
		licenses: Optional[List[FossyLicenseFinding]] = None
	):
		self.origin = origin
		self.metadata = metadata
		self.summary = FossySummary.decode(summary)
		self.licenses = FossyLicenseFinding.drilldown(licenses)
