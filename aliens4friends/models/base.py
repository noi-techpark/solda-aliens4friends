from json import JSONEncoder, dumps, load as jsonload

class BaseModel:

	@classmethod
	def from_json(cls, json):
		if not json:
			return None
		if isinstance(json, str):
			return json
		return cls(**json)

	def encode(self) -> dict:
		"""Create dictionaries out of objects with attributes as keys and then
		drill down into values and do their encoding. If a _container attribute
		exists, return it as-is, to also allow dictionaries inside the encoded
		hierarchy. This is useful for keys that are actually not object fields,
		but names of json objects.

		Returns: dict: dictionary representation of this instance
		"""
		if hasattr(self, "_container"):
			return self._container
		return self.__dict__

	def to_json(self) -> str:
		return dumps(self, cls=BaseModelEncoder)

	def drilldown(self, input_list: list, cls):
		if not input_list:
			return []

		if not isinstance(input_list, list):
			raise ModelError(f"We can only drilldown into a list: {type(input_list)} given!")

		if isinstance(input_list[0], cls):
			return input_list

		return [
			cls(**d) for d in input_list
		]

	def decode(self, input_dict: dict, cls, inner_cls = False):
		if not input_dict:
			return cls()

		if isinstance(input_dict, cls) and not inner_cls:
			return input_dict

		if not isinstance(input_dict, dict):
			raise ModelError(f"We can only decode a dict: {type(input_dict)} given!")

		if inner_cls:
			return {
				k: cls(**v) for k, v in input_dict.items()
			}
		return cls(**input_dict)

	@classmethod
	def from_file(cls, path: str):
		with open(path) as f:
			jl = jsonload(f)
		try:
			return cls(**jl)
		except TypeError:
			return cls(jl)


class ModelError(Exception):
	pass

class BaseModelEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, BaseModel):
			return obj.encode()
		else:
			raise ModelError(f"Unknown instance type found! --> {obj}")
