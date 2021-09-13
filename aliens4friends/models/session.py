# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import Tool
from typing import List, Optional, TypeVar

_TSessionPackageModel = TypeVar('_TSessionPackageModel', bound='SessionPackageModel')
class SessionPackageModel(BaseModel):
	def __init__(
		self,
		name: str,
		version: str,
		variant: str = "",
		selected: bool = True,
		selected_reason: Optional[str] = "",
		uploaded: Optional[bool] = None,
		uploaded_reason: Optional[str] = ""
	) -> None:
		self.name = name
		self.version = version
		self.variant = variant
		self.selected = selected
		self.selected_reason = selected_reason
		self.uploaded = uploaded
		self.uploaded_reason = uploaded_reason

	def __eq__(self, o: _TSessionPackageModel) -> bool:
		return (
			self.name == o.name
			and self.version == o.version
			and self.variant == o.variant
		)

class SessionModel(BaseModel):
	def __init__(
		self,
		tool: Tool,
		session_id: str,
		package_list: Optional[List[SessionPackageModel]] = []
	) -> None:
		self.tool = Tool.decode(tool)
		self.session_id = session_id
		self.package_list = SessionPackageModel.drilldown(package_list)
