# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 Alberto Pianon <pianon@array.eu>

import logging
import requests
from uuid import uuid4
from time import sleep
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

from fossology import Fossology, fossology_token
from fossology.obj import ReportFormat, TokenScope, Upload
from fossology.folders import Folder

from aliens4friends.commons.settings import Settings
from aliens4friends.commons.spdxutils import parse_spdx_tv_str
from tenacity import RetryError

logger = logging.getLogger(__name__)

AGENTS: Dict[str, str] = {
	"copyright_email_author": "copyright",
	"ecc": "ecc",
	"keyword": "keyword",
	"nomos": "nomos",
	"monk": "monk",
	"ojo": "ojo",
	#"package": "pkgagent",
}

class FossyWrapperException(Exception):
	pass

class FossyWrapper:
	def __init__(self) -> None:
		self.fossy_session = requests.Session()
		self.fossyUI_login()
		self.fossology = self._connect2fossyAPI()

	def fossyUI_login(self) -> None:
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

	def _get_fossy_token(self) -> None:
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

	def _connect2fossyAPI(self) -> Fossology:
		self._get_fossy_token()
		try:
			return Fossology(Settings.FOSSY_SERVER, self.fossy_token, Settings.FOSSY_USER)
		except Exception:
			raise FossyWrapperException(
				"something is wrong with "
				"fossology server; I can generate a token but I can't connect "
				"to fossology REST API with it"
			)

	def _wait_for_jobs_completion(self, upload: Upload) -> None:
		all_completed = False
		jobs = []
		count = 0
		while not all_completed:
			count += 1
			if count > 6*60*4:
				raise FossyWrapperException(
					f"timeout (4h) for job completion for upload {upload.id}"
				)
			sleep(10)
			try:
				jobs, _ = self.fossology.list_jobs(upload=upload,all_pages=True)
			except Exception:
				pass
			if jobs:
				all_completed = True
				for job in jobs:
					d = datetime.strptime(f"{job.queueDate}00", "%Y-%m-%d %H:%M:%S.%f%z")
					delta = d - datetime.now(d.tzinfo)
					if delta.days < -2: # ignore old jobs
						continue
					# FIXME: handle also killed jobs
					if job.status == "Processing" or job.status == "Started":
						all_completed = False
						break

	def get_or_create_folder(self, folder: str) -> Folder:
		logger.info(f'get or create folder "{folder}"')
		parent = self.fossology.rootFolder
		components = folder.split("/")
		for component in components:
			parent = self.fossology.create_folder(parent, component)
		return parent

	def check_already_uploaded(self, uploadname: str) -> Optional[Upload]:
		logger.info(f"[{uploadname}] Checking if it has already been uploaded")
		all_uploads, _ = self.fossology.list_uploads(all_pages=True)
		for upload in all_uploads:
			if uploadname == upload.uploadname:
				return upload

	def upload(self, filename: str, folder: Folder, description: str = '') -> Upload:
		logger.info(f"[{filename}] Uploading the file to Fossology")
		try:
			upload = self.fossology.upload_file(
				folder,
				file=filename,
				ignore_scm=True,
				description=description
			)
		except RetryError:
			raise FossyWrapperException(
				"Can't upload package to fossology. Is fossology scheduler running?"
			)
		logger.info(f"upload id is {upload.id}")
		return upload

	def rename_upload(self, upload: Upload, newuploadname: str) -> None:
		self.fossyUI_login()
		res = self.fossy_session.post(
			(
				f"{Settings.FOSSY_SERVER}/?mod=upload_properties"
				f"&folder={upload.folderid}&upload={upload.id}"
			),
			data={
				"oldfolderid": f"{upload.folderid}",
				"upload_pk": f"{upload.id}",
				"uploadselect": f"{upload.id}",
				"newname": f"{newuploadname}",
				"newdesc": f"{upload.description}",
			},
		)
		if "Upload Properties successfully changed" not in res.text:
			raise FossyWrapperException("upload renaming failed")

	def get_not_scheduled_agents(self, upload: Upload) -> List[str]:
		res = self.fossy_session.get(
			f"{Settings.FOSSY_SERVER}?mod=upload_agent_options&upload={upload.id}"
		)
		html = BeautifulSoup(res.content, 'html.parser')
		return [
			option.attrs["value"].replace("agent_","") #pytype: disable=attribute-error
			for option in html.find_all("option")
		]

	def schedule_fossy_scanners(self, upload: Upload) -> None:
		logger.info(f"[{upload.uploadname}] checking already scheduled scanners")
		not_scheduled = self.get_not_scheduled_agents(upload)
		analysis = {}
		agents = []
		for agent, alias in AGENTS.items():
			if alias in not_scheduled:
				analysis.update({agent: True})
				agents.append(agent)
			else:
				analysis.update({agent: False})
		logger.info(f"[{upload.uploadname}] scheduling {agents}")
		specs = { "analysis": analysis }
		if not agents:
			logger.info(
				f"[{upload.uploadname}] not scheduling anything, all agents"
				" already scheduled before"
			)
			return
		if "ojo" in agents:
			specs.update({"decider": {"ojo_decider": True}})
		try:
			folder = self.fossology.detail_folder(upload.folderid)
			self.fossology.schedule_jobs(
				folder, upload, specs, wait=True
			)
		except RetryError:
			raise FossyWrapperException(
				"Can't schedule jobs on fossology. Is fossology scheduler running?"
			)
		logger.info(
			"waiting for scanner job completion "
			"(it may take a lot of time, if upload size is big)"
		)
		self._wait_for_jobs_completion(upload)


	def report_import(self, upload: Upload, spdxrdf_path: str) -> None:
		"""import SPDX RDF report file into Fossology, via webUI"""
		# TODO: upstream: add missing REST API for reportImport in Fossology
		logger.info(f"Uploading '{spdxrdf_path}' to Fossology")
		# package has been uploaded to fossology but there may no
		# corresponding entry in the upload_clearing table
		# (that we need to in order to make reportImport actually work).
		# We force Fossology to update upload_clearing table by
		# calling upload_summary
		self.fossology.upload_summary(upload)
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

	def get_upload(self, uploadname: str) -> Optional[Upload]:
		"""Get Fossology Upload object from pakage name and version,
		assuming that uploadname follows the scheme <name>@<version>, and
		assuming that uploadnames are unique in queried Fossology instance"""
		return self.check_already_uploaded(uploadname)

	def get_license_findings_conclusions(self, upload: Upload):
		logger.info(
			f"[{upload.uploadname}] Getting license findings and conclusions "
			f"for upload with id={upload.id}"
		)
		agents = ["monk", "nomos", "ojo", "reportImport"]
		for a in self.get_not_scheduled_agents(upload):
			if a in agents:
				agents.remove(a)
		if not self.check_already_imported_report(upload):
			agents.remove("reportImport")
		return self.get_licenses(upload, agents) if agents else []

	def check_already_imported_report(self, upload: Upload):
		return self.get_licenses(upload, ["reportImport",], test=True)

	@staticmethod
	def _process_licenses(new_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""convert json to old 1.0.16 API format, for backwards compatibility"""
		old_json = []
		for el in new_json:
			old_json.append({
				"filePath": el["filePath"],
				"agentFindings": el["findings"]["scanner"],
				"conclusions": el["findings"]["conclusion"]
			})
		return old_json

	def get_licenses(self, upload: Upload, agents: list, test: bool = False) -> Union[bool, Any]:
		params = { "agent":  agents}
		res = self.fossology.session.get(f"{self.fossology.api}/uploads/{upload.id}/licenses", params=params)
		if res.status_code == 200:
			if test:
				return True
			return self._process_licenses(res.json())
		elif res.status_code == 403:
			raise FossyWrapperException(
				f"Can't get licenses for upload {upload.uploadname} (id={upload.id}): not authorized"
			)
		elif res.status_code == 412:
			if test:
				return False
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

	@staticmethod
	def _process_summary(new_json: Dict[str, Any])-> Dict[str, Any]:
		"""convert json to old 1.0.16 API format, for backwards compatibility"""
		new_json.pop("assignee", None)
		return new_json # not necessary, it is already passed by reference, but
		                # it shouldn't harm

	def get_summary(self, upload: Upload) -> Any:
		res = self.fossology.session.get(f"{self.fossology.api}/uploads/{upload.id}/summary")
		return res.json()

	def get_spdxtv(self, upload: Upload):
		logger.info(f"[{upload.uploadname}] Generating spdx report")
		rep_id = self.fossology.generate_report(
			upload=upload,
			report_format=ReportFormat.SPDX2TV
		)
		self._wait_for_jobs_completion(upload)
		logger.info(f"[{upload.uploadname}] Downloading spdx report")
		report_text, _ = self.fossology.download_report(rep_id)
		doc, _ = parse_spdx_tv_str(report_text)
		return doc
