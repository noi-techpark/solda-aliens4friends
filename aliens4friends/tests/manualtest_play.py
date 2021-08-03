from aliens4friends.models.base import BaseModel
from aliens4friends.models.aliensrc import AlienSrc


# from json import dumps, load as jsonload, JSONEncoder

# class ModelError(Exception):
# 	pass

# class BaseModel2:
# 	@classmethod
# 	def from_json(cls, json):
# 		if not json:
# 			return None
# 		if isinstance(json, str):
# 			return json
# 		return cls(**json)

# 	def encode(self) -> dict:
# 		"""Create dictionaries out of objects with attributes as keys and then
# 		drill down into values and do their encoding. If a _container attribute
# 		exists, return it as-is, to also allow dictionaries inside the encoded
# 		hierarchy. This is useful for keys that are actually not object fields,
# 		but names of json objects.

# 		Returns: dict: dictionary representation of this instance
# 		"""
# 		if hasattr(self, "_container"):
# 			return self._container
# 		return self.__dict__

# 	def to_json(self) -> str:
# 		return dumps(self, cls=BaseModelEncoder2)

# 	@classmethod
# 	def drilldown(cls, input_list: list):
# 		if not input_list:
# 			return []

# 		if not isinstance(input_list, list):
# 			raise ModelError(f"We can only drilldown into a list: {type(input_list)} given!")

# 		if isinstance(input_list[0], cls):
# 			return input_list

# 		return [
# 			cls(**d) for d in input_list
# 		]

# 	@classmethod
# 	def decode(cls, input_dict: dict):
# 		if not input_dict:
# 			return cls()

# 		if isinstance(input_dict, cls):
# 			return input_dict

# 		if not isinstance(input_dict, dict):
# 			raise ModelError(f"We can only decode a dict: {type(input_dict)} given!")

# 		return cls(**input_dict)

# 	@classmethod
# 	def from_file(cls, path: str):
# 		with open(path) as f:
# 			jl = jsonload(f)
# 		return cls(**jl)

# 	def __init__(self, *args, **kwargs):
# 		print(self.__class__.__dict__)
# 		print(args)

# 		annot = self.__annotations__
# 		for k, v in kwargs.items():
# 			if k not in annot:
# 				raise ModelError(f"Wrong parameter '{k}'. Unable to build model {type(self)}.")
# 			subclas = annot[k]
# 			if issubclass(subclas, BaseModel2):
# 				if isinstance(v, dict):
# 					v = subclas(**v)
# 				else:
# 					v = subclas(v)
# 			setattr(self, k, v)

# class BaseModelEncoder2(JSONEncoder):
# 	def default(self, obj):
# 		if isinstance(obj, BaseModel2):
# 			return obj.encode()
# 		else:
# 			raise ModelError(f"Unknown instance type found! --> {obj}")

# class Tool2(BaseModel2):
# 	name: str
# 	version: str
# 	parameters: str

# class HarvestModel2(BaseModel2):
# 	tool: Tool2
# 	source_packages: list


# h = HarvestModel2.from_file("tmp/test-harvest.json")

# print(h.tool.name)
# print(h.tool.version)

# h = HarvestModel2(tool=Tool2(name="X", version="11"))
# print(h.tool.name)
# print(h.tool.version)

# # h = TinfoilHatModel.from_file("tmp/pool3/userland/acl/2.2.53-r0/acl-2.2.53-r0.tinfoilhat.json")

# print(h.to_json())

dd = {
	"version": 3
}
x = AlienSrc(**dd)

print(x.to_json())


# class X(BaseModel):
# 	z: int = 3
# 	pass

# class Y(BaseModel):
# 	a: X
# 	b: str

# 	def __init__(self, *args, **kwargs):
# 		for x in args:
# 			print(x)

# 		print(self.__class__.__dict__)
# 		for k, v in kwargs.items():
# 			if hasattr(self, k):
# 				print(f"{k} :: {v}")


# dd = {
# 	"a": X(4),
# 	"b": "3000",
# 	"c": 3
# }

# y = Y(**dd)

# class S:
# 	pass

# class A(S):
# 	pass

# class B:
# 	x: A = None


# b1 = B()
# b1.x = 10
# print(b1.x)

# b2 = B()
# b2.x = 13
# print(b1.x)
# print(b2.x)

# print(issubclass(B.__annotations__["x"], S))

# import json

# class CE(json.JSONEncoder):
# 	def default(self, obj):
# 		if isinstance(obj, DebianMatch):
# 		else:
# 			return obj.__dict__

# class DebianMatch:
# 	def __init__(self, name: str, version: str, ip_matching_files: int = 0):
# 		self.name = name
# 		self.version = version
# 		self.ip_matching_files = ip_matching_files

# 	@classmethod
# 	def from_json(cls, json_dict):
# 		return cls(**json_dict)

# 	def __str__(self):
# 		return json.dumps(self.__dict__)

# class X:
# 	def __init__(self, c):
# 		self.c = DebianMatch(c, ".", 7)
# 	def __str__(self):
# 		return json.dumps(self.__dict__, cls=CE)



# dm = DebianMatch("A", "B", 3)

# x = X("VV")

# print(x)

