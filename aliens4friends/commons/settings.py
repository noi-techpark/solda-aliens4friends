from dotenv import dotenv_values, find_dotenv # pip install -U python-dotenv

class Settings:
	DOTENV = dotenv_values(find_dotenv())
	POOLPATH = DOTENV["A4F_POOL"] or "/tmp/aliens4friends/"
	POOLCACHED = bool(DOTENV["A4F_CACHE"]) or True
