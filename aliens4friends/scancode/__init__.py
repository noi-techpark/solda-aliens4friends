from aliens4friends.commons.pool import Pool
from aliens4friends.commons.package import AlienPackage
from aliens4friends.commons.archive import Archive
from aliens4friends.commons.utils import bash_live
import os

def run_scancode(pool : Pool, archive : Archive, package_name, package_version_str):

	result_path = os.path.dirname(archive.path)
	result_filename = f"{package_name}_{package_version_str}.scancode.json"

	archive_unpacked = pool.mkdir(result_path, "__unpacked")
	print(f"# Extract archive and run SCANCODE on {archive_unpacked}... This may take a while!")
	if not os.listdir(archive_unpacked):
		archive.extract(archive_unpacked)
	scancode_result = os.path.join(result_path, result_filename)
	if os.path.exists(scancode_result):
		print(f"| Skipping because result already exists: {scancode_result}")
	else:
		bash_live(
			f"cd {archive_unpacked} && scancode -n4 -cli --json /userland/scanresult.json /userland",
    		prefix = "SCANCODE"
		)
		# Move scanresults into parent directory
		os.rename(os.path.join(archive_unpacked, "scanresult.json"), scancode_result)
	return scancode_result
