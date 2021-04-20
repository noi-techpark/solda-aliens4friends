from json import JSONEncoder, dumps

class BaseModel:

	@classmethod
	def from_json(cls, json_dict):
		return cls(**json_dict)

	def encode(self):
		return self.__dict__

	def to_json(self):
		return dumps(self, cls=BaseModelEncoder)


class BaseModelError(Exception):
	pass

class BaseModelEncoder(JSONEncoder):
	def default(self, obj):
		if isinstance(obj, BaseModel):
			return obj.encode()
		else:
			raise BaseModelError(f"Unknown instance type found! --> {obj}")
