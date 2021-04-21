from json import JSONEncoder, dumps, load as jsonload

class BaseModel:

	@classmethod
	def from_json(cls, json):
		if not json:
			return None
		if isinstance(json, str):
			return json
		return cls(**json)

	def encode(self):
		return self.__dict__

	def to_json(self):
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

	def decode(self, input_dict: dict, cls):
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
			return cls(**jsonload(f))


class ModelError(Exception):
	pass

class BaseModelEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, BaseModel):
			return obj.encode()
		else:
			raise ModelError(f"Unknown instance type found! --> {obj}")
