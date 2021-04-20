from json import JSONEncoder, dumps

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


class ModelError(Exception):
	pass

class BaseModelEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, BaseModel):
			return obj.encode()
		else:
			raise ModelError(f"Unknown instance type found! --> {obj}")
