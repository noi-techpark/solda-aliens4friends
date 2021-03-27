from dotenv import dotenv_values, find_dotenv # pip install -U python-dotenv

class Settings:
	DOTENV = dotenv_values(find_dotenv())

	# TODO: loop thru a dictionary of default settings instead,
	# for better scalability

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

	try:
		SCANCODE_WRAPPER = DOTENV["A4F_SCANCODE"].upper() == "WRAPPER"
	except KeyError:
		SCANCODE_WRAPPER = DOTENV["A4F_SCANCODE"] = False

	try:
		PRINTRESULT = bool(DOTENV["A4F_PRINTRESULT"])
	except KeyError:
		PRINTRESULT = DOTENV["A4F_PRINTRESULT"] = True

	try:
		SPDX_TOOLS_CMD = DOTENV["SPDX_TOOLS_CMD"]
	except KeyError:
		SPDX_TOOLS_CMD = DOTENV["SPDX_TOOLS_CMD"] = "java -jar /usr/local/lib/spdx-tools-2.2.5-jar-with-dependencies.jar"

	try:
		FOSSY_USER = DOTENV["FOSSY_USER"]
	except KeyError:
		FOSSY_USER = DOTENV["FOSSY_USER"] = 'fossy'

	try:
		FOSSY_PASSWORD = DOTENV["FOSSY_PASSWORD"]
	except KeyError:
		FOSSY_PASSWORD = DOTENV["FOSSY_PASSWORD"] = 'fossy'

	try:
		FOSSY_GROUP_ID = DOTENV["FOSSY_GROUP_ID"]
	except KeyError:
		FOSSY_GROUP_ID = DOTENV["FOSSY_GROUP_ID"] = 3

	try:
		FOSSY_SERVER = DOTENV["FOSSY_SERVER"]
	except KeyError:
		FOSSY_SERVER = DOTENV["FOSSY_SERVER"] = 'http://localhost/repo'
