# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel

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
		clearingStatus: str = None,
		uploadName: str = None,
		mainLicense: str = None
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
		filePath: str = None,
		agentFindings: list = None,
		conclusions: list = None
	):
		self.filePath = filePath
		self.agentFindings = agentFindings
		self.conclusions = conclusions


class FossyModel(BaseModel):
	def __init__(
		self,
		origin: str = None,
		summary: FossySummary = None,
		licenses: list = None
	):
		self.origin = origin
		self.summary = FossySummary.decode(summary)
		self.licenses = FossyLicenseFinding.drilldown(licenses)
