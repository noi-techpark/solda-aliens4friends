from .utils import bash
from os.path import splitext


class ArchiveError(Exception):
    pass

class Archive:

	SUPPORTED_ARCHIVES = {
		".gz": {
			"tarparam": "z"
		},
		".xz": {
			"tarparam": "J"
		},
		".bz2": {
			"tarparam": "j"
		},
		".aliensrc": {
			"tarparam": "z"
		}
	}

	def __init__(self, archive_path):
		self.path = archive_path
		self.tar_param = Archive._get_tar_param(archive_path)
		self.is_supported()

	def is_supported(self):
		_, extension = splitext(self.path)
		if not extension in self.SUPPORTED_ARCHIVES:
			raise ArchiveError(f"Archive with extension {extension} is not supported!")

	def _make_tar_cmd(self, params):
		return bash(f'tar {self.tar_param}xvf {self.path} {params}')

	def readfile(self, file_path):
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=cat')
		result = stdout.split('\n')
		return result[0], result[1:]

	def checksums(self, file_path):
		stdout, _ = self._make_tar_cmd(f'{file_path} --to-command=sha1sum')
		return Archive._parse_sha1sum(stdout)

	def in_archive_checksums(self, archive_in_archive, file_path=""):
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - {file_path} --to-command=sha1sum"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	def extract(self, dest):
		return self._make_tar_cmd(f'-C {dest} --strip 1')

	def in_archive_extract(self, archive_in_archive, dest):
		internal_cmd = f"tar {Archive._get_tar_param(archive_in_archive)}xvf - -C {dest} --strip 1"
		stdout, _ = self._make_tar_cmd(f'{archive_in_archive} --to-command="{internal_cmd}"')
		return Archive._parse_sha1sum(stdout)

	@staticmethod
	def _get_tar_param(archive_name):
		_, extension = splitext(archive_name)
		try:
			return Archive.SUPPORTED_ARCHIVES[extension]["tarparam"]
		except KeyError:
			pass
		raise ArchiveError(f"Archive type unknown for {archive_name}.")

	@staticmethod
	def _parse_sha1sum(sha1stdout):
		lines = sha1stdout.split('\n')
		files = {}
		i = 0
		while i < len(lines):
			if (
				lines[i].endswith('/')
				or not Archive._check_next_endswith(lines, i+1, '-')
			):
				i += 1
				continue
			path = '/'.join(lines[i].split('/')[1:])
			files[path] = lines[i+1].split(' ', 1)[0]
			i += 2
		return files

	@staticmethod
	def _check_next_endswith(lines, index, ends):
		if index >= len(lines) or index < 0 or not lines[index]:
			return False
		return lines[index].endswith(ends)
