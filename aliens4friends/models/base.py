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
		drill down into values and do their encoding.

		Returns: dict: dictionary representation of this instance
		"""
		return self.__dict__

	def to_json(self) -> str:
		return dumps(self, cls=BaseModelEncoder)

	@classmethod
	def drilldown(cls, input_list: list):
		if not input_list:
			return []

		if not isinstance(input_list, list):
			raise ModelError(f"We can only drilldown into a list: {type(input_list)} given!")

		if isinstance(input_list[0], cls):
			return input_list

		return [
			cls(**d) for d in input_list
		]

	@classmethod
	def decode(cls, input_dict: dict):
		if not input_dict:
			return cls()

		if isinstance(input_dict, cls):
			return input_dict

		if not isinstance(input_dict, dict):
			raise ModelError(f"We can only decode a dict: {type(input_dict)} given!")

		return cls(**input_dict)

	@classmethod
	def from_file(cls, path: str):
		with open(path) as f:
			jl = jsonload(f)
		try:
			return cls(**jl)
		except TypeError:
			return cls(jl)


class DictModel(BaseModel):
	subclass = None
	def __init__(
		self,
		container: dict
	):
		self._container = self.decode(container)

	@classmethod
	def from_file(cls, path: str):
		with open(path) as f:
			jl = jsonload(f)
		return cls(jl)

	@classmethod
	def decode(cls, input_dict: dict):
		if not input_dict:
			return {}

		if not isinstance(input_dict, dict):
			raise ModelError(f"We can only decode a dict: {type(input_dict)} given!")

		if not cls.subclass:
			return input_dict

		return {
			k: cls.subclass(**v) for k, v in input_dict.items()
		}



class ModelError(Exception):
	pass

class BaseModelEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, BaseModel):
			return obj.encode()
		else:
			raise ModelError(f"Unknown instance type found! --> {obj}")
