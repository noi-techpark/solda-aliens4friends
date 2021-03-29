# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import logging
import requests
from uuid import uuid4
from time import sleep
from urllib.parse import urlencode
from datetime import datetime, timedelta

from fossology import Fossology, fossology_token
from fossology import uploads, jobs, report
from fossology.obj import ReportFormat, TokenScope, Upload

from aliens4friends.commons.settings import Settings

logger = logging.getLogger(__name__)

class FossyWrapperException(Exception):
	pass

class FossyWrapper:
	def __init__(self):
		self.fossy_session = requests.Session()
		self.fossyUI_login()
		self.fossology = self._connect2fossyAPI()

	def fossyUI_login(self):
		self.fossy_session.cookies.clear()
		self.fossy_session.post(
			f"{Settings.FOSSY_SERVER}/?mod=auth",
			data={"username": Settings.FOSSY_USER, "password": Settings.FOSSY_PASSWORD},
		)
		if not self.fossy_session.cookies:
			raise FossyWrapperException(
				"can't connect to fossology WebUI: "
				"maybe wrong Settings.FOSSY_USER or Settings.FOSSY_PASSWORD?"
			)

	def _get_fossy_token(self):
		try:
			token_expire = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
			self.fossy_token = fossology_token(
				Settings.FOSSY_SERVER,
				Settings.FOSSY_USER,
				Settings.FOSSY_PASSWORD,
				token_name=f"{uuid4()}",
				token_scope=TokenScope.WRITE,
				token_expire=token_expire,
			)
		except Exception:
			raise FossyWrapperException(
				"something is wrong with "
				"fossology server; I can connect to WebUI but I can't generate "
				"a token with FOSSY_USER and FOSSY_PASSWORD"
			)

	def _connect2fossyAPI(self):
		self._get_fossy_token()
		try:
			return Fossology(Settings.FOSSY_SERVER, self.fossy_token, Settings.FOSSY_USER)
		except Exception:
			raise FossyWrapperException(
				"something is wrong with "
				"fossology server; I can generate a token but I can't connect "
				"to fossology REST API with it"
			)

	def _wait_for_jobs_completion(self, upload: Upload):
		all_completed = False
		jobs = []
		# FIXME: add time limit?
		while not all_completed:
			sleep(10)
			try:
				jobs = self.fossology.list_jobs(upload=upload, page_size=2000)
			except Exception:
				pass
			if jobs:
				all_completed = True
				for job in jobs:
					# FIXME: handle also killed jobs
					if job.status == "Processing" or job.status == "Started":
						all_completed = False
						break

	def report_import(self, upload: Upload, spdxrdf_path: str):
		"""import SPDX RDF report file into Fossology, via webUI"""
		# TODO: upstream: add missing REST API for reportImport in Fossology
		logger.info(f"uploading '{spdxrdf_path}' to Fossology")
		# package has been uploaded to fossology but there may no
		# corresponding entry in the upload_clearing table
		# (that we need to in order to make reportImport actually work).
		# We force Fossology to update upload_clearing table by
		# calling upload_summary
		summary = self.fossology.upload_summary(upload)
		# Login again to fossology, since a lot of time may be passed, and
		# login cookie could be expired
		self.fossyUI_login()
		res = self.fossy_session.post(
			f"{Settings.FOSSY_SERVER}/?mod=ui_reportImport",
			data={
				"addNewLicensesAs": "license",
				"addLicenseInfoFromInfoInFile": "true",
				"addLicenseInfoFromConcluded": "true",
				"addConcludedAsDecisions": "true",
				"addConcludedAsDecisionsOverwrite": "true",
				"addCopyrights": "true",
				"oldfolderid": f"{upload.folderid}",
				"uploadselect": f"{upload.id}",
			},
			files={"report": open(spdxrdf_path, "rb")},
		)
		if "<title>Show Jobs</title>" not in res.text:
			raise FossyWrapperException("reportImport failed")
		logger.info("monitoring reportImport job status...")
		self._wait_for_jobs_completion(upload)

	def get_upload(self, name, version, revision):
		"""Get Fossology Upload object from pakage name and version,
		assuming that uploadname follows the scheme
		<name>?ver=<version>-<revision> (urlencoded)
		assuming that uploadnames are unique in queried Fossology instance"""
		query = urlencode({"ver": f"{version}-{revision}"})
		upload = f'{name}?{query}'
		uploads = {u.uploadname: u for u in self.fossology.list_uploads()}
		return uploads.get(upload)

	def get_license_findings_conclusions(self, upload: Upload):
		logger.info(
			"getting license findings and conclusions for upload "
			f"{upload.uploadname} (id={upload.id})"
		)
		params = { "agent": ["monk", "nomos", "ojo", "reportImport"] }
		res = self.fossology.session.get(f"{self.fossology.api}/uploads/{upload.id}/licenses", params=params)
		if res.status_code == 200:
			return res.json()
		elif res.status_code == 403:
			raise FossyWrapperException(
				f"Can't get licenses for upload {upload.uploadname} (id={upload.id}): not authorized"
			)
		elif res.status_code == 412:
			raise FossyWrapperException(
				f"Can't get licenses for upload {upload.uploadname} (id={upload.id}): some agents have not been scheduled yet"
			)
		elif res.status_code == 503:
			raise FossyWrapperException(
				f"Unpack agent for {upload.uploadname} (id={upload.id}) didn't start yet"
			)
		else:
			raise FossyWrapperException(
				f"Unknown error: Fossology API returned status code {res.status_code}"
			)
