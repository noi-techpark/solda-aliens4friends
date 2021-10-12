# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>

from dotenv import dotenv_values, find_dotenv # pip install -U python-dotenv

class Settings:
	VERSION = "0.7.0"
	PATH_TMP = "apiresponse"
	PATH_DEB = "debian"
	PATH_USR = "userland"
	PATH_STT = "stats"
	PATH_SES = "sessions"

	DOTENV = dotenv_values(find_dotenv(usecwd=True))

	# TODO: loop thru a dictionary of default settings instead,
	# for better scalability

	try:
		POOLPATH = DOTENV["A4F_POOL"]
	except KeyError:
		POOLPATH = DOTENV["A4F_POOL"] = "/tmp/aliens4friends/"

	try:
		POOLCACHED = (DOTENV["A4F_CACHE"].lower() == "true")
	except KeyError:
		POOLCACHED = DOTENV["A4F_CACHE"] = True

	try:
		LOGLEVEL = DOTENV["A4F_LOGLEVEL"].upper()
	except KeyError:
		LOGLEVEL = DOTENV["A4F_LOGLEVEL"] = "INFO"

	try:
		SCANCODE_WRAPPER = (DOTENV["A4F_SCANCODE"].lower() == "wrapper")
		SCANCODE_COMMAND = "scancode-wrapper" if (DOTENV["A4F_SCANCODE"].lower() == "wrapper") else "scancode"
	except KeyError:
		SCANCODE_WRAPPER = DOTENV["A4F_SCANCODE"] = False
		SCANCODE_COMMAND = "scancode"

	try:
		PRINTRESULT = (DOTENV["A4F_PRINTRESULT"].lower() == "true")
	except KeyError:
		PRINTRESULT = DOTENV["A4F_PRINTRESULT"] = False

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

	try:
		SPDX_DISCLAIMER = DOTENV["SPDX_DISCLAIMER"]
	except KeyError:
		SPDX_DISCLAIMER = ""

	try:
		PACKAGE_ID_EXT = DOTENV["PACKAGE_ID_EXT"]
	except KeyError:
		PACKAGE_ID_EXT = "a4f"

	# TODO write the session_id into the .env file, or use a current-link
	#      to the actual created or chosen session_id.json
	try:
		SESSION_ID = DOTENV["A4F_SESSION_ID"]
	except KeyError:
		SESSION_ID = ""
