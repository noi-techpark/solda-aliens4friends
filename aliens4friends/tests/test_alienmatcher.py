import os
from aliens4friends.alienmatcher import AlienMatcher, AlienMatcherError, VERSION
from aliens4friends.commons.package import AlienPackage, PackageError

def test_all():
    print(f"##########################################################################")
    print(f"### ALIENMATCHER v{VERSION}")
    print(f"##########################################################################")

    path = os.path.join(
        os.getcwd(),
        "tmp",
        "alberto",
        "SCA"
    )
    for filename in os.listdir(path):
        if not filename.endswith("tar.gz"):
            continue
        package_path = os.path.join(path, filename)
        try:
            package = AlienPackage(package_path)
            pool_path = os.path.join(
                os.getcwd(),
                "tmp",
                "pool"
            )
            matcher = AlienMatcher(pool_path)
            matcher.match(package)
        except (AlienMatcherError, PackageError) as ex:
            print(f"##########################################################################")
            print(f"ERROR: {filename} not matchable! --> {ex}")
            print(f"##########################################################################")

def test_single():
    print(f"##########################################################################")
    print(f"### ALIENMATCHER v{VERSION}")
    print(f"##########################################################################")

    package_path = os.path.join(
        os.getcwd(),
        "tmp",
        "alberto",
        "SCA",
        "alienacl-2.2.53.tar.gz"
        # "alienlibusb1-1.0.22.tar.gz"
    )
    package = AlienPackage(package_path)
    pool_path = os.path.join(
        os.getcwd(),
        "tmp",
        "pool"
    )
    matcher = AlienMatcher(pool_path)
    matcher.match(package, True)
