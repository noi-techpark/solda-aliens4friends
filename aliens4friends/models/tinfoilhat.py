from .base import BaseModel


class Container(BaseModel):
	def __init__(
		self,
		recipe: dict = None,
		tags: dict = None,
		packages: dict = None
	):
		self.recipe = recipe
		self.tags = tags
		self.packages = packages


class TinfoilHatModel(BaseModel):
	def __init__(
		self,
		container: dict = None
	):
		self._container = self.decode(container, Container, True)
