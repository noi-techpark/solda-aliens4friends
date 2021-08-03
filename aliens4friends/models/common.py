# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from .base import BaseModel
from typing import Union, Dict, Any, List

class License(BaseModel):
	def __init__(self, spdxid: str) -> None:
		RENAME = {
			"GPL-1.0" : "GPL-1.0-only",
			"GPL-1.0+" : "GPL-1.0-or-later",
			"GPL-2.0" : "GPL-2.0-only",
			"GPL-2.0+" : "GPL-2.0-or-later",
			"GPL-3.0" : "GPL-3.0-only",
			"GPL-3.0+" : "GPL-3.0-or-later",
			"LGPL-2.0" : "LGPL-2.0-only",
			"LGPL-2.0+" : "LGPL-2.0-or-later",
			"LGPL-2.1" : "LGPL-2.1-only",
			"LGPL-2.1+" : "LGPL-2.1-or-later",
			"LGPL-3.0" : "LGPL-3.0-only",
			"LGPL-3.0+" : "LGPL-3.0-or-later",
			"LPGL-2.1-or-later": "LGPL-2.1-or-later", # fix for misspelled license
		}
		try:
			self.id = RENAME[spdxid]
		except KeyError:
			self.id = spdxid

	# Override
	def encode(self) -> str:
		return self.id

class Tool(BaseModel):
	def __init__(
		self,
		name: str,
		version: str,
		parameters: Dict[str, str] = None
	) -> None:
		self.name = name
		self.version = version
        # TODO: add tool parameters used to create the file
		if parameters:
			self.parameters = parameters

class SourceFile(BaseModel):
	def __init__(
		self,
		name: str = None,
		sha1_cksum: str = None,
		git_sha1: str = None,
		src_uri: str = None,
		files_in_archive: Union[int, bool] = False,
		paths: List[str] = None
	):
		self.name = name
		self.sha1_cksum = sha1_cksum
		self.git_sha1 = git_sha1
		self.src_uri = src_uri
		self.files_in_archive = files_in_archive
		self.paths = paths
