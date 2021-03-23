from dotenv import dotenv_values, find_dotenv # pip install -U python-dotenv

class Settings:
	DOTENV = dotenv_values(find_dotenv())

	try:
		POOLPATH = DOTENV["A4F_POOL"]
	except KeyError:
		POOLPATH = DOTENV["A4F_POOL"] = "/tmp/aliens4friends/"

	try:
		POOLCACHED = bool(DOTENV["A4F_CACHE"])
	except KeyError:
		POOLCACHED = DOTENV["A4F_CACHE"] = True

	try:
		LOGLEVEL = DOTENV["A4F_LOGLEVEL"].upper()
	except KeyError:
		LOGLEVEL = DOTENV["A4F_LOGLEVEL"] = "INFO"

