# SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
# SPDX-License-Identifier: Apache-2.0

import sys, os, logging, time, urllib.request, zipfile, json, re

from datetime import datetime

from .version import Version

logging.basicConfig(format='%(name)s:slug=%(message)s', level=logging.INFO)
logger = logging.getLogger("cvecheck")

class CveCheckerError(Exception):
	pass

class CveChecker:

	slug = ''

	candidates = {}
	aliens = {}

	version = ".*"
	vendor = ".*"
	appname = ".*"

	startfrom=2002

	SUPPORTSLUG = 'cpe:2.3:a:'
	CVES_TO_DATE = datetime.now().year
	CACHE_VALID_S = 86400
	FILEIDENT = "nvdcve-1.1-"
	NIST_JSON_FEEDS = "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-"

	def __init__(self, config) -> None:

		self.slug = self.SUPPORTSLUG + config['vendor'] + ":" + config['product'] + ":.*"

		self.vendor = config['vendor']
		self.appname = config['product']
		self.version = config['version']
		self.startfrom = config['from']
		self.harvest_file = config['harvest']
		self.tmpdir = config['tmpdir']

		if config['harvest'] or self.appname != '.*':
			self.updateCveFeeds()
		else:
			raise CveCheckerError(f'{self.slug} please provide a product name')



	def run(self) -> bool:
		self.pipeline()
		if not bool(self.candidates):
			logger.info(f'{self.slug} success! no vulnerabilities found')
			return False
		else:
			logger.info(f'{self.slug} {len(self.candidates["aliens"]["identified"])} identified aliens')
			logger.info(f'{self.slug} {len(self.candidates["aliens"]["review"])} strange friends')
			return True

	def pipeline(self) -> None:
		logger.info(f'{self.slug} search v {self.version}')
		self.searchCandidates()
		if bool(self.candidates):
			self.filterCandidates()
			self.writeResult()

	def patchHarvest(self) -> None:
		logger.info(f"reading {self.harvest_file}")
		harvest = self.loadHarvestList(self.harvest_file)
		for i in harvest["source_packages"]:

			if "cve_metadata" not in i:
				logger.error(f"old harvest.json? sourcepackage must contain valid cve_metadata")
				break

			# TODO: respect variants present in harvest cve_metadata
			self.appname = i["name"]
			self.version = i["cve_metadata"]["cve_version"]
			self.slug = self.SUPPORTSLUG + self.vendor + ":" + self.appname + ":.*"

			found = self.run()

			if found:
				i["cve_metadata"]["result"] = self.candidates["aliens"].copy()

		return harvest

  # identifying CPE matches to applicability statements
	def filterCandidates(self) -> None:

		# exact matches
		self.aliens['identified'] = []
		# manual review / unsupported cases
		self.aliens['review'] = []

		logger.info(f"{self.slug} found " + str(len(self.candidates[self.slug])) + " potential vulnerabilities, filtering... ")

		for i in self.candidates[self.slug]:
			# identified flag / needle is affected
			identified = False
			# manual flag / if edge case is not implemented
			manual = False

			logger.info(f"{self.slug} checking {i['id']}")
			nodes = i['data']['configurations']['nodes']
			version = i['data']['configurations']['CVE_data_version']

			# flag and ignore unsupported version
			if version != '4.0':
				logger.error(f"{self.slug} wrong cve data version: {version}")
				manual = True
				continue

			# look at each configurations nodes...
			for n in nodes:

				# TODO: support child node configurations
				if len(n['children']) > 0:
					manual = True
					logger.debug(f"{self.slug}   review flag: {len(n['children'])} childrens of existing node!")

				# TODO: support AND operator, if necessary (no existing hardware or os atm (?), must considered )
				if n['operator'] != "OR":
					manual = True
					logger.debug(f"{self.slug}   review flag: ignoring cpe-match: unsupported operator {n['operator']}")
					continue

				# ...for direct matches (child configurations ignored at this point)...
				for m in n['cpe_match']:
					logger.debug(f"{self.slug}   check {m['cpe23Uri']}")
					# ...ignore match if not vulnerable...
					if not m['vulnerable']:
						logger.debug(f"{self.slug}     ignoring  {m['cpe23Uri']}, not vulnerable")
						continue

					# ...and ignore os specific matches, until AND operator gets supported...
					if not self.SUPPORTSLUG in m['cpe23Uri']:
						logger.debug(f"{self.slug}     ignoring  {m['cpe23Uri']}, OS specific")
						continue

					cpe23 = m['cpe23Uri'].split(":")

					affected_version = cpe23[5]
					affected_appname = cpe23[4]
					affected_vendor = cpe23[3]

					# ...ignore wrong app matches...
					if affected_appname != self.appname:
						continue

					# ...if we search for no specific version...
					if self.version == ".*":
						identified = True
						continue

					logger.debug(f"{self.slug}     search for version: {self.version}")

					needle = Version(self.version)
					version = Version(affected_version)
					direct_similarity = needle.similarity(version)

					logger.info(f"{self.slug}     version similarity {direct_similarity}")

					inside_boundaries = False
					rangebound = False

					if "versionStartIncluding" in m:
						start = m['versionStartIncluding']
						vstart = Version(start)
						inside_boundaries = needle > vstart or needle == vstart
						rangebound = True
						logger.info(f"{self.slug}     affected from including {start}")
					if "versionStartExcluding" in m:
						start = m['versionStartExcluding']
						vstart = Version(start)
						inside_boundaries = needle > vstart
						rangebound = True
						logger.info(f"{self.slug}     affected from excluding {start}")
					if "versionEndIncluding" in m:
						end = m['versionEndIncluding']
						vend = Version(end)
						inside_boundaries = needle < vend or needle == vend
						rangebound = True
						logger.info(f"{self.slug}     affected until including {end}")
					if "versionEndExcluding" in m:
						end = m['versionEndExcluding']
						vend = Version(end)
						inside_boundaries = needle < vend
						rangebound = True
						logger.info(f"{self.slug}     affected until excluding {end}")

					identified = inside_boundaries;
					if inside_boundaries:
						logger.info(f"{self.slug}     EXACT MATCH: Boundaries")

					# no version boundaries
					if not rangebound:
						logger.info(f"{self.slug}     affected version {cpe23[5]}")

						# wildcard or match, an unquoted asterisk in an attribute-value string SHALL be interpreted as a multi-character wild card
						if cpe23[5] == "*" or direct_similarity == 100:
							identified = True
							logger.info(f"{self.slug}     EXACT MATCH: Direct")
							continue
						# similar but no match, only if needle is smaller than version
						elif direct_similarity > 0 and needle < version:
							logger.info(f"{self.slug}     FUZZY MATCH: Version similarity")
							manual = True
							continue
						else:
							continue

			if identified:
				self.aliens['identified'].append(i)
			if manual and not identified:
				self.aliens['review'].append(i)

		self.candidates['aliens'] = self.aliens


	def writeResult(self) -> None:
		del self.candidates[self.slug]
		with open('results/result.'+ self.appname +'.json', 'w') as outfile:
			outfile.write(json.dumps(self.candidates, indent=4, sort_keys=True))
			outfile.close

	def updateCveFeeds(self) -> bool:
		logger.debug(f'{self.slug} getting fresh cve feeds from: {self.NIST_JSON_FEEDS}')
		start = self.startfrom
		while self.CVES_TO_DATE >= start:
			feed_uri = self.NIST_JSON_FEEDS + str(start) + ".json.zip";
			package_filename = self.tmpdir+"/cve"+str(start)+".zip";
			json_filename = self.tmpdir+"/"+self.FILEIDENT+str(start)+".json";

			# check cache
			if os.path.isfile(json_filename):
				st=os.stat(json_filename)
				mtime=time.time() - st.st_mtime
				logger.debug(f'{self.slug} feed exists, age: {mtime}')
				if mtime > self.CACHE_VALID_S:
					self.removeFileIfExists(package_filename)
				else:
					logger.debug(f'{self.slug} feed up to date!')
					start = start + 1
					continue

			logger.info(f'{self.slug} downloading {feed_uri}')
			try:
				urllib.request.urlretrieve(feed_uri, package_filename)
				with zipfile.ZipFile(package_filename, 'r') as cvejson:
					logger.error(f'{self.slug} extract: {cvejson}')
					cvejson.extractall(self.tmpdir)
			except:
				logger.error(f'{self.slug} download error')

			start = start + 1

		return True

	def validCveFormat(self, i) -> bool:
		if i["cve"]["data_format"] != "MITRE":
			return False
		if i["cve"]["data_type"] != "CVE":
			return False
		if i["cve"]["data_version"] != "4.0":
			return False
		return True

	def loadHarvestList(self, file) -> dict:
		if os.path.isfile(file):
			feed = open(file, encoding='utf-8')
			data = json.load(feed)
			return data
		else:
			return {}

	def searchCandidates(self) -> None:
		self.candidates = {}

		start = self.startfrom

		while self.CVES_TO_DATE >= start:
			json_feed = self.tmpdir+"/"+self.FILEIDENT+str(start)+".json";
			logger.info(f'{self.slug} scanning feed: {json_feed}')
			if os.path.isfile(json_feed):
				feed = open(json_feed, encoding='utf-8')
				data = json.load(feed)
				for i in data["CVE_Items"]:
					if not self.validCveFormat(i):
						logger.error(f'{self.slug} Wrong CVE datatype: MITRE/CVE/4.0 support only')
						continue

					cveid = i["cve"]["CVE_data_meta"]["ID"]
					config_string = json.dumps(i["configurations"])

					if re.search(self.slug, config_string):
						if self.slug not in self.candidates:
							self.candidates[self.slug] = []

						self.candidates[self.slug].append(
							{
								"id" : cveid,
								"data" : i,
							}
						)
			else:
				logger.error(f'{self.slug} feed not found (?!)')

			start = start + 1;

	def removeFileIfExists(self, package_filename) -> None:
		try:
			os.remove(package_filename)
		except OSError as e:
			logger.warning(f'{self.slug} {package_filename} remove error: {e.errno}')
