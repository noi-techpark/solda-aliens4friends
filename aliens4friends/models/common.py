from .base import BaseModel

class License(BaseModel):
	def __init__(self, spdxid: str):
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
	def encode(self):
		return self.id

class Tool(BaseModel):
	def __init__(self, name: str, version: str, parameters: str = None):
		self.name = name
		self.version = version
		if parameters:
			self.parameters = parameters
