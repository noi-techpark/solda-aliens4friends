# SPDX-FileCopyrightText: Peter Moser <p.moser@noi.bz.it>
#
# SPDX-License-Identifier: Apache-2.0

from json import JSONEncoder, dumps, load as jsonload

class BaseModel:
	"""
		Base model to create class instances out of json input data, or to write
		pre-defined json from this model definition
	"""

	def encode(self) -> dict:
		"""Create dictionaries out of objects with attributes as keys and then
		drill down into values and do their encoding.

		Returns:
			dict: dictionary representation of this instance
		"""
		return self.__dict__

	def to_json(self) -> str:
		"""Create a JSON string out of this object.

		Returns:
			str: JSON of this object
		"""
		return dumps(self, cls=BaseModelEncoder)

	@classmethod
	def drilldown(cls, input_list: list):
		"""Walk through the input_list, and decode each element according to the
		given class (cls). If the elements are already cls, just return the list as-is.

		Args:
			input_list (list): A list of objects, that should be decoded

		Raises:
			ModelError: input_list must either be None or list, raise this error otherwise

		Returns:
			cls: returns an instance of this class (cls)
		"""
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
		"""Create an instance of this class (cls) with the input values given by
		input_dict. If the input_dict is already cls, just return it. If it is
		None, create a default object out of cls.

		Args:
			input_dict (dict): json representation of this class (cls) or None

		Raises:
			ModelError: input_dict must either be None or dict, raise this error otherwise

		Returns:
			cls: class instance of cls
		"""
		if not input_dict:
			return cls()

		if isinstance(input_dict, cls):
			return input_dict

		if not isinstance(input_dict, dict):
			raise ModelError(f"We can only decode a dict: {type(input_dict)} given!")

		return cls(**input_dict)

	@classmethod
	def from_file(cls, path: str):
		"""Load json input file and decode its content into this class cls

		Args:
			path (str): path to the json file

		Returns:
			cls: class instance of cls
		"""
		with open(path) as f:
			jl = jsonload(f)
		try:
			return cls(**jl)
		except TypeError:
			return cls(jl)


class DictModel(BaseModel):
	"""
		Dictionary model to create class instances out of json input data, or to
		write pre-defined json from this model definition. This model is used,
		when the keys of a json object are not meant to be object attributes,
		but names or when attributes have a form that is not json-key
		compatible. Just give the subclass attribute, which defines the class
		type of each value inside the dictionary.
	"""

	subclass = None		# subclass of the values inside this dict model

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
		"""Create an instance of the given subclass for each input values given
		by input_dict, and put that into _container field. If the input_dict is
		None, just return an empty dictionary.

		Args:
			input_dict (dict): json representation of this class (cls) or
				               None. The values must be a json-representation of
							   subclass

		Raises:
			ModelError: input_dict must either be None or dict, raise this error otherwise

		Returns:
			dict of subclass: a dictionary where each value has type subclass
		"""
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
