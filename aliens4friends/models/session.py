# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from .common import Tool
from typing import List, Optional

class PackageListModel(BaseModel):
	def __init__(
		self,
		name: Optional[str] = None,
		version: Optional[str] = None,
		selected: bool = True
	) -> None:
		self.name = name
		self.version = version
		self.selected = selected

class SessionModel(BaseModel):
	def __init__(
		self,
		tool: Tool,
		session_id: str,
		package_list: Optional[List[PackageListModel]] = []
	) -> None:
		self.tool = Tool.decode(tool)
		self.session_id = session_id
		self.package_list = PackageListModel.drilldown(package_list)
