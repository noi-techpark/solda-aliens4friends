<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>
SPDX-FileCopyrightText: NOI Techpark <info@noi.bz.it>
-->

# Aliens for Friends

*Documentation: v1 from 2021-04-08*

This is a tool for Software Composition Analysis (SCA), expressly designed to
analyze `Yocto`/`bitbake` builds -- but it could be usefully adopted in any
software composition context where a package manager is missing, and where
source code provenance and license/copyright metadata are often missing, messy,
uncertain and/or imprecise.

> Our metaphor goes like this: We invite some aliens (third party software
> components), in other words unknown species, to a pool party (our fancy FLOSS
> project), and hopefully after some interaction we manage to understand if they
> are friends or foes. This way we avoid having our pool party stopped by the
> Police because of strange things they bring or do.... In the best case
> scenario, those aliens become friends :-)*

The main goal is to automatically detect as many license and copyright
information as possible, by comparing "alien" source packages with packages
found in existing trusted sources, like for instance `Debian`.

We took `Debian` as a primary "source of truth" because it has a strict policy
to include packages in its distribution (also from a FLOSS compliance
standpoint) and because it is backed by a community that continuously checks and
"audits" source code to that purpose. Other similar sources of truth may be
added in the future.

The overall idea is to avoid reinventing the wheel: if copyright and license
metadata have already been reviewed by a trusted community, it does not make
sense to redo their work by auditing the same code back to square one.

More generally, the idea is that if a similar (or same) software package has
been already included in Debian, it means that it is a well-known component, so
it is a presumed friend, and we can safely invite it to our party.

- [Aliens for Friends](#aliens-for-friends)
  - [Requirements and Installation](#requirements-and-installation)
  - [Workflow](#workflow)
    - [Step 1: Create an Alien Package](#step-1-create-an-alien-package)
    - [Step 2: Configure the tool](#step-2-configure-the-tool)
    - [Step 3: Create a session](#step-3-create-a-session)
    - [Step 4: Add the Alien to the pool](#step-4-add-the-alien-to-the-pool)
      - [.aliensrc file](#aliensrc-file)
      - [.tinfoilhat file](#tinfoilhat-file)
    - [Step 5: Find a matching Debian source package](#step-5-find-a-matching-debian-source-package)
      - [Option 1: aliens4friends match](#option-1-aliens4friends-match)
      - [Option 2: aliens4friends snapmatch](#option-2-aliens4friends-snapmatch)
      - [Option 3: aliens4friends match and snapmatch combined](#option-3-aliens4friends-match-and-snapmatch-combined)
    - [Step 6: Scan the code to detect license/copyright information](#step-6-scan-the-code-to-detect-licensecopyright-information)
    - [Step 7: Find differences between Alien Packages and the corresponding Debian matching packages](#step-7-find-differences-between-alien-packages-and-the-corresponding-debian-matching-packages)
    - [Step 8: Create Debian SPDX file from debian/copyright file](#step-8-create-debian-spdx-file-from-debiancopyright-file)
    - [Step 9: Create Alien SPDX file out of Debian SPDX file (reusing license metadata)](#step-9-create-alien-spdx-file-out-of-debian-spdx-file-reusing-license-metadata)
    - [Step 10: Upload to Fossology, schedule Fossology scanners, import Alien/Debian SPDX to Fossology](#step-10-upload-to-fossology-schedule-fossology-scanners-import-aliendebian-spdx-to-fossology)
    - [Step 11: Generate final SPDX file, after human review](#step-11-generate-final-spdx-file-after-human-review)
    - [Step 12: Harvest all results and create a final report](#step-12-harvest-all-results-and-create-a-final-report)
  - [Special commands](#special-commands)
    - [CVEcheck](#cvecheck)
      - [Result of CVE checks](#result-of-cve-checks)
      - [Procedure](#procedure)
      - [todos & caveats](#todos--caveats)
      - [disclaimer](#disclaimer)
      - [info](#info)
    - [Session](#session)
      - [Filter](#filter)
      - [Locking](#locking)
      - [Adding variants](#adding-variants)
      - [Generate a static csv report](#generate-a-static-csv-report)
    - [Mirror](#mirror)
  - [Installation and execution with docker](#installation-and-execution-with-docker)
  - [Manual installation and execution on your host machine](#manual-installation-and-execution-on-your-host-machine)
    - [Installation of Scancode](#installation-of-scancode)
      - [Native](#native)
      - [Wrapper](#wrapper)
    - [Installation of the spdx-tools](#installation-of-the-spdx-tools)
    - [Installation of Tinfoilhat](#installation-of-tinfoilhat)
    - [Installation of Aliensrc Creator](#installation-of-aliensrc-creator)
    - [Installation of Fossology (as docker container)](#installation-of-fossology-as-docker-container)
      - [With docker-compose](#with-docker-compose)
      - [With Docker](#with-docker)
- [Gitlab CI of a complete pipeline with Yocto and Aliens4Friends](#gitlab-ci-of-a-complete-pipeline-with-yocto-and-aliens4friends)
  - [Install docker and docker-compose on a Linux machine](#install-docker-and-docker-compose-on-a-linux-machine)
  - [Install a Gitlub Runner on a Linux machine](#install-a-gitlub-runner-on-a-linux-machine)
  - [Configure the Gitlab Runner](#configure-the-gitlab-runner)
  - [Configure a Gitlab container registry](#configure-a-gitlab-container-registry)
  - [Known limitations](#known-limitations)
    - [Only use a single branch to trigger the pipeline](#only-use-a-single-branch-to-trigger-the-pipeline)
    - [Time consuming operations](#time-consuming-operations)
  - [Contributor's FAQ](#contributors-faq)
    - [I want to understand how the Debian matching works](#i-want-to-understand-how-the-debian-matching-works)
    - [I want to add a new sub-command to Aliens4Friends](#i-want-to-add-a-new-sub-command-to-aliens4friends)
      - [Command line definition](#command-line-definition)
      - [Mirror Command Execution Configuration](#mirror-command-execution-configuration)
      - [Mirror business logic](#mirror-business-logic)
    - [Verbose and quiet output of commands](#verbose-and-quiet-output-of-commands)
    - [String formatting](#string-formatting)
  - [References](#references)

## Requirements and Installation

We provide also a docker-based development and execution environment. Go to
[Development with Docker](#development-with-docker) for further details. If you
prefer to install everything on your host machine, continue reading...

To install `aliens4friends`, just do, on a `debian|ubuntu` machine:

```bash
sudo apt install python3-pip libpq-dev

echo "[easy_install]
zip_ok = False" > ~/.distutils.cfg # required for flanker dependency

git clone https://git.ostc-eu.org/oss-compliance/toolchain/aliens4friends.git
cd aliens4friends
pip3 install --user setuptools wheel
pip3 install --user .
. ~/.profile
a4f &>/dev/null # required for flanker initialization
```

A couple of external dependencies are needed:

- Scancode v3.2.3
- spdx-tools (java executable) v2.2.5
- Fossology v3.9.0
- Optional: Tinfoilhat and Aliensrc Creater

The dedicated section [Installation and execution with docker](#installation-and-execution-with-docker) **or**
[Manual installation and execution on your host machine](#manual-installation-and-execution-on-your-host-machine)
shows you how to install those extra tools.

## Workflow

Let's start with an example. Assume we have a source code package called `zlib`
in version `1.2.11-r0`, and want to collect license and copyright information.

An implementation and further details can be found in our [OSS Compliance Pipeline]
repository.

### Step 1: Create an Alien Package

First thing to do is to create a so-called "Alien Package". If you use bitbake
as a building system, you can use the scripts contained in the [TinfoilHat]
project.

Let's assume that our alien package is named `zlib-1.2.11-r0.aliensrc`. The
file-extension `.aliensrc` is mandatory, the name is arbitrary. An alien package
is a tarball with no compression. It must have an internal structure like the
following:

```
├── aliensrc.json
└── files
    ├── ldflags-tests.patch
    └── zlib-1.2.11.tar.xz
```

The file `aliensrc.json` is **mandatory**; it should be **added first**, at the
beginning of the tarball file (so it can be extracted faster) and contains all
metadata information of this alien package.

<p><details>
<summary><b>click to see aliensrc.json data structure example</b></summary>

<!--  hacky trick: using python syntax highlightning to be able to put comments, not allowed in json -->

```python
{
    "version": 1,                   # the version of this json spec
    "source_package": {             # the data part of this source package
        "name": [                   # some packages have more than one name/alias, ordered by priority (top=most important)
            "zlib"
        ],
        "version": "1.2.11-r0",
        "manager": "bitbake",       # the build system from where we extracted this source package
        "metadata": {               # any metadata (tipically, metadata extracted from the build system).
                                    # This structure is not defined, nor mandatory
            "name": "zlib",
            "base_name": "zlib",
            "version": "1.2.11",
            "revision": "r0",
            "variant": "1eea2d14",
            "author": null,
            "homepage": "http://zlib.net/",
            "summary": "Zlib Compression Library",
            "description": "Zlib is a general-purpose, patent-free, lossless data compression library which is used by many different programs.",
            "license": "Zlib"
        },
        "files": [                  # files, that are included in the "files" folder inside the alien package
            {
                # the file name
                "name": "zlib-1.2.11.tar.xz",

                # This is the commit SHA, if the src_uri has a "git://" scheme
                "git_sha1": null,

                # file checksum (only sha1 is supported)
                "sha1_cksum": "e1cb0d5c92da8e9a8c2635dfa249c341dfd00322",

                # the provenance, that is, the place where the upstream package came from
                "src_uri": "https://downloads.sourceforge.net/libpng/zlib/1.2.11/zlib-1.2.11.tar.xz",

                # The file count inside the tarball archive
                "files_in_archive": 253,

                # This array contains file paths of this file inside the .aliensrc tar archive
                # Example for a configuration file, can also be "tagged" for various
                # project/version/flavors/machine/image hierarchies.
				# An empty array means, that this file does not have duplicates with different
				# content, but the same file name.
                "paths": []
            },
            {
                "name": "ldflags-tests.patch",
                "git_sha1": null,
                "sha1_cksum": "f370a10d1a454cdcd07a8d164fe0d65b32b6d2a9",

                # the provenance: in this case "unknown", since the file was just added from a filesystem
                "src_uri": "file://ldflags-tests.patch",

                # false, if no archive, 0 if the archive is empty
                "files_in_archive": false,

                "paths": []
            }
        ],

        # Tags to be shown on our Dashboard, used for filtering of packages
        # The hierarchy is as follows (defined in the yoctobuild matrix):
        # - project
        # - version: branch-name, last-tag on that branch, count of commits until the final
        #   commit with hash g507268c (see "git" for further information on this)
        # - flavour: linux, zephyr, etc.
        # - machine
        # - image
        "tags": [
            "oniro/v1.0.0-rc-17-g507268c/oniro-linux/qemux86-64/oniro-image-base",
            "oniro/v1.0.0-rc-17-g507268c/oniro-linux/qemux86-64/oniro-image-base-dev",
            "oniro/v1.0.0-rc-17-g507268c/oniro-linux/raspberrypi4-64/oniro-image-base",
            "oniro/v1.0.0-rc-17-g507268c/oniro-linux/raspberrypi4-64/oniro-image-base-dev",
            "oniro/v1.0.0-rc-17-g507268c/oniro-linux/raspberrypi4-64/oniro-image-base-tests",
            "...."
        ]
    }
}
```

To get more information about the **yoctobuild matrix** go to the [OSS
Compliance Pipeline repository].

</details></p>

One archive in the `files` list is considered the main archive, which will be
compared to trusted source repositories. The tool scans also files of additional
archives, but those archives are not used to find matching archives on Debian or
other source repos. In case of multiple archives, possible parameters attached
to the `src_uri` can be used (if known) to determine which is the main archive
(this is bitbake-specific, though).

### Step 2: Configure the tool

Execute:
```sh
aliens4friends config > .env
```

This creates a `.env` file with the default configuration options, if the `.env`
did not exist before. You can now open that file and change it as you like.

> **IMPORTANT** The default setting for A4F_POOL (Path to the cache pool) is
> `/tmp/aliens4friends/`. This is intended only for tests, while in production
> you should use a permanent directory, such as `~/pool` or the like.

<p><details>
<summary><b>See "aliens4friends config --help" output for details.</b></summary>

```
usage: aliens4friends config [-h]

Create a .env file in the folder, where you execute the command.

Environmental variables:
  - A4F_POOL        : Path to the cache pool
  - A4F_CACHE       : True/False, if cache should be used or overwritten (default = True)
  - A4F_DEBUG       : Debug level as seen inside the "logging" package (default = INFO)
  - A4F_SCANCODE    : wrapper/native, whether we use a natively installed scancode or
                      run it from our docker wrapper (default = native)
  - A4F_PRINTRESULT : Print results also to stdout
  - SPDX_TOOLS_CMD  : command to invoke java spdx tools (default =
                      'java -jar /usr/local/lib/spdx-tools-2.2.5-jar-with-dependencies.jar')
  - SPDX_DISCLAIMER : legal disclaimer to add into generated SPDX files (optional)
  - PACKAGE_ID_EXT  : extension to append to package IDs in harvest.json file (optional, arbitrary)
  - FOSSY_USER,
    FOSSY_PASSWORD,
    FOSSY_GROUP_ID,
    FOSSY_SERVER    : parameters to access fossology server
                      (defaults: 'fossy', 'fossy', 3, 'http://localhost/repo').

optional arguments:
  -h, --help  show this help message and exit
```

</details></p>

### Step 3: Create a session

A session is used to have a list of packages that we want to process. This list
can then be manipulated. Packages can be filtered, selected or status/statistics
about them can be stored inside the session cache. A session can later be loaded
to continue a work, previously put down.

<p><details>
<summary><b>See "aliens4friends session --help" output for details.</b></summary>

```
usage: aliens4friends session [-h] [--force] [-f FILTER | -c | -n | --report REPORT | --lock | --unlock | --add-variants] [-s SESSION]
                              [glob_name] [glob_version]

positional arguments:
  glob_name             Wildcard pattern to filter by package names. Do not forget to quote it!
  glob_version          Wildcard pattern to filter by package versions. Do not forget to quote it!

optional arguments:
  -h, --help            show this help message and exit
  --force               Force a lock or unlock operation
  -f FILTER, --filter FILTER
                        Filter the package list inside the given session (use -s SESSION for that)
  -c, --create          Create and fill a session from a given ID or random string (if absent)
  -n, --new             Create a new empty session from a given ID or random string (if absent)
  --report REPORT       Generate a csv report on the session's packages (collecting also Fossology metadata), and save it to REPORT
  --lock                Lock the selected session with a runtime specific LOCK key, ex. the pipeline ID stored inside an A4F_LOCK_KEY env-
                        var
  --unlock              Unlock the selected session, if the A4F_LOCK_KEY env-var matches the current lock
  --add-variants        Add any possible variants for each package found in current session
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```
</details></p>

A session has a unique ID, and can be empty at first. We can get a random
session ID, or provide our own. In this example, our own session ID is called
`MYSESSION`.
```sh
aliens4friends session -ns MYSESSION
```

If you like to use some packages from the pool previously added, you can also
create a session from existing Aliensrc packages like this:
```sh
aliens4friends session -cs MYSESSION 'ac*' '*'
```

...or create a session with the whole pool:
```sh
aliens4friends session -cs MYSESSION '*' '*'
```

Keep in mind that if you want to use wildcards, you should put the search
parameters within quotes, otherwise bash will expand them locally and not on the
pool.

### Step 4: Add the Alien to the pool

#### .aliensrc file
- INPUT: `.aliensrc` file, generated through [TinfoilHat]
Execute:
```sh
aliens4friends add -s MYSESSION zlib-1.2.11-r0.aliensrc
```

#### .tinfoilhat file
Enrich the result with tinfoilhat
- INPUT: `.tinfoilhat.json` file, generated through [TinfoilHat]

This is a Yocto/BitBake-specific step. Add `.tinfoilhat.json` results to the
pool to get more details to be included in the final statistics.

`.tinfoilhat.json` files contain data that are specific to the particular
bitbake project that is being scanned, such as `DISTRO`, `IMAGE_NAME` and
`MACHINE` tags, as well as metadata about binary packages generated from the
analyzed  sources. For more details, refer to the [TinfoilHat] project
documentation.

Execute:

```sh
aliens4friends add -s MYSESSION zlib-1.2.11-r0.tinfoilhat.json
```


This will add the package to our pool (party). All data that comes from the user
will be stored in the folder `userland` with sub-folders named
`<package-name>/<package-version>`. So in our case `userland/zlib/1.2.11-r0`.
Intermediate results also land in this directory.

*Please note, only if both files, `aliensrc` and `tinfoilhat` exist, the package
gets added to the session package list.*

<p><details>
<summary><b>See "aliens4friends add --help" output for details.</b></summary>

```
usage: aliens4friends add [-h] [-f] [-i] [-v | -q] [--dryrun] -s SESSION [FILES [FILES ...]]

positional arguments:
  FILES                 The Alien Packages (also wildcards allowed)

optional arguments:
  -h, --help            show this help message and exit
  -f, --force           Force AlienSrc package overwrite.
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 5: Find a matching Debian source package

- INPUT: `.aliensrc` files inside the pool
- OUTPUT: `.alienmatcher.json` or `.snapmatch.json` files inside the `userland`
  pool path regarding the current processed package, depending which Debian API
  we use: the current Debian repository or the history repository with all
  snapshots of all time.

The matching can be done in three different ways against two different APIs:
- Option 1: `aliens4friends match`: fast, but has only the most recent package versions
  for each distribution, that is, it might not be a perfect match
- Option 2: `aliens4friends snapmatch`: slow, but has all Debian packages of all time,
  that is, it is more probable to find a nicely matching package and version
- Option 3: Another possibility is to first run the `match` command, and then
  filter out all packages, that have already a good matching candidate (high
  matching score), and run the `snapmatch` command only against the other
  packages.

#### Option 1: aliens4friends match

Execute:
```sh
aliens4friends match -s MYSESSION
```

This will search a match for any package that has been added to the session. If
you want to restrict the search use the `session` command with the `--filter`
option first.

<p><details>
<summary><b>See "aliens4friends match --help" output for details.</b></summary>

```
usage: aliens4friends match [-h] [-i] [-v | -q] [--dryrun] [-p] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

<p><details>
<summary><b>click to see .alienmatcher.json output data structure example</b></summary>

<!--  hacky trick: using python syntax highlightning to be able to put comments, not allowed in json -->

```python
{
  "tool": {                         # name and version of alienmatcher tool
    "name": "aliens4friends.commons.alienmatcher",
    "version": "0.7.0"
  },
  "aliensrc": {
    "name": "zlib",                 # name of the aliensrc package
    "version": "1.2.11-r0",         # version of the aliensrc package
    "alternative_names": [],        # possible alternative names/aliases of the package to search for in Debian
    "internal_archive_name": "zlib-1.2.11.tar.xz",
                                    # main upstream source archive
                                    # (a matching source archive will be searched in Debian)
    "filename": "zlib-1.2.11-r0.aliensrc",
                                    # filename of the aliensrc package already added to the pool
    "files": [                      # this section corresponds to the `files` section of aliensrc.json
      {
        "name": "zlib-1.2.11.tar.xz",
        "sha1_cksum": "e1cb0d5c92da8e9a8c2635dfa249c341dfd00322",
		"git_sha1": null,
        "src_uri": "https://downloads.sourceforge.net/libpng/zlib/1.2.11/zlib-1.2.11.tar.xz",
        "files_in_archive": 253,
		"paths": []
      },
      {
        "name": "ldflags-tests.patch",
        "sha1_cksum": "f370a10d1a454cdcd07a8d164fe0d65b32b6d2a9",
		"git_sha1": null,
        "src_uri": "file://ldflags-tests.patch",
        "files_in_archive": false,
		"paths": []
      },
      {
        "name": "run-ptest",
        "sha1_cksum": "8236e92debcc7a83144d0c4a3b51e0aa258acc7f",
		"git_sha1": null,
        "src_uri": "file://run-ptest",
        "files_in_archive": false,
		"paths": []
      }
    ]
  },
  "match": {
	"name": "zlib",               # name of the matching debian package
	"version": "1.2.11.dfsg-1",   # version of the matching debian package
    "score": 100.0,				  # The overall score of matching between the name and
								  # version of packages
    "package_score": 100,		  # The score of the package name matching alone
    "version_score": 100,         # The score of the package version matching alone
	"debsrc_debian": "debian/zlib/1.2.11.dfsg-1/zlib_1.2.11.dfsg-1.debian.tar.xz",
								# debian source tarball, downloaded from debian source repos
								# - in case of Debian Format 1.0, this is a .diff.gz file
								# - in case of Debian Format 1.0/3.0 native, this value is null
	"debsrc_orig": "debian/zlib/1.2.11.dfsg-1/zlib_1.2.11.dfsg.orig.tar.gz",
								# original source tarball, downloaded from debian source repos
								# - in case of Debian Format 1.0/3.0 native, this is the only
								#   archive and it does not have `.orig.` in the filename
	"dsc_format": "3.0 (quilt)",  # Debian package format
	"version_candidates": [
		{                           # examined matching candidates in Debian repos
			"version": "1.2.11.dfsg-2",
			"distance": 10,           # distance from aliensrc is calculated based on version
			"is_aliensrc": false
		},
		{
			"version": "1.2.11.dfsg-1",
			"distance": 10,
			"is_aliensrc": false
		},
		{
			"version": "1.2.11-r0",
			"distance": 0,
			"is_aliensrc": true
		},
		{
			"version": "1.2.8.dfsg-5",
			"distance": 300,
			"is_aliensrc": false
		},
		{
			"version": "1.2.8.dfsg-2",
			"distance": 300,
			"is_aliensrc": false
		}
	]
  },
  "errors": []                      # possible error messages of the alienmatcher tool
}
```

</details></p>

#### Option 2: aliens4friends snapmatch

Execute:
```sh
aliens4friends snapmatch -s MYSESSION
```

This will search a match for any package that has been added to the session. If
you want to restrict the search use the `session` command with the `--filter`
option first.

<p><details>
<summary><b>See "aliens4friends snapmatch --help" output for details.</b></summary>

```
usage: aliens4friends snapmatch [-h] [-i] [-v | -q] [--dryrun] [-p] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

<p><details>
<summary><b>click to see .snapmatch.json output data structure example</b></summary>

Most of the fields are identical to the `.alienmatcher.json` format. We describe
the others in the comments below:

<!--  hacky trick: using python syntax highlightning to be able to put comments, not allowed in json -->

```python
{
  "tool": {
    "name": "aliens4friends.commands.snapmatch",
    "version": "0.7.0"
  },
  "aliensrc": {
    "name": "zlib",
    "version": "1.2.11-r0",
    "filename": "zlib-1.2.11-r0-1eea2d14.aliensrc",
    "internal_archive_name": "zlib-1.2.11.tar.xz",
    "alternative_names": [],
    "files": [
      {
        "name": "zlib-1.2.11.tar.xz",
        "sha1_cksum": "e1cb0d5c92da8e9a8c2635dfa249c341dfd00322",
        "git_sha1": null,
        "src_uri": "https://downloads.sourceforge.net/libpng/zlib/1.2.11/zlib-1.2.11.tar.xz",
        "files_in_archive": 253,
        "paths": []
      },
      {
        "name": "ldflags-tests.patch",
        "sha1_cksum": "f370a10d1a454cdcd07a8d164fe0d65b32b6d2a9",
        "git_sha1": null,
        "src_uri": "file://ldflags-tests.patch",
        "files_in_archive": false,
        "paths": []
      },
      {
        "name": "run-ptest",
        "sha1_cksum": "8236e92debcc7a83144d0c4a3b51e0aa258acc7f",
        "git_sha1": null,
        "src_uri": "file://run-ptest",
        "files_in_archive": false,
        "paths": []
      }
    ]
  },
  "match": {
    "name": "zlib",
    "version": "1:1.2.11.dfsg-1",
    "score": 99.5,
    "distance": 0,
    "package_score": 100,
    "version_score": 99,
    "package_score_ident": "Ident or alias match",	  # Reason of the package name score above
    "version_score_ident": "Version distance <= 10",  # Reason of the package version score above
    "debsrc_debian": "debian/zlib/1:1.2.11.dfsg-1/zlib_1.2.11.dfsg-1.debian.tar.xz",
    "debsrc_orig": "debian/zlib/1:1.2.11.dfsg-1/zlib_1.2.11.dfsg.orig.tar.gz",
    "dsc_format": "3.0 (quilt)",
	# Same structure as the "aliensrc/files" section above, but for the remote
	# Debian repositories of the matching package
    "srcfiles": [
      {
        "name": "zlib_1.2.11.dfsg-1.dsc",
        "sha1_cksum": "f2bea8c346668d301c0c7745f75cf560f2755649",
        "git_sha1": null,
        "src_uri": "https://snapshot.debian.org/file/f2bea8c346668d301c0c7745f75cf560f2755649",
        "files_in_archive": false,
        "paths": [
          "/pool/main/z/zlib"
        ]
      },
      {
        "name": "zlib_1.2.11.dfsg.orig.tar.gz",
        "sha1_cksum": "1b7f6963ccfb7262a6c9d88894d3a30ff2bf2e23",
        "git_sha1": null,
        "src_uri": "https://snapshot.debian.org/file/1b7f6963ccfb7262a6c9d88894d3a30ff2bf2e23",
        "files_in_archive": false,
        "paths": [
          "/pool/main/z/zlib"
        ]
      },
      {
        "name": "zlib_1.2.11.dfsg-1.debian.tar.xz",
        "sha1_cksum": "c3b2bac9b1927fde66b72d4f98e4063ce0b51f34",
        "git_sha1": null,
        "src_uri": "https://snapshot.debian.org/file/c3b2bac9b1927fde66b72d4f98e4063ce0b51f34",
        "files_in_archive": false,
        "paths": [
          "/pool/main/z/zlib"
        ]
      }
    ]
  },
  "errors": []
}
```
</details></p>

#### Option 3: aliens4friends match and snapmatch combined

We run first the `match` command, because it is fast and finds often already a
good enough matching package on Debian.

Execute:
```sh
aliens4friends match -s MYSESSION
```

Our `session.json` has now a list of packages with their matching score, that is
a indicator how close one of our AlienPackages are to a Debian package. The
score is a number between 0 and 100. Lets say we agree that we need only to
search for a better match for packages with a score below 80. So we can filter
out all packages, that have already a good matching candidate (high matching
score).

Execute:
```sh
aliens4friends session --filter score-gt=80 -s MYSESSION
```

Hint: See [Session Filters](#session-filters) if you want to know more.

Finally, we run the `snapmatch` command against the remaining packages.
Execute:
```sh
aliens4friends snapmatch -s MYSESSION
```


### Step 6: Scan the code to detect license/copyright information

- INPUT: `.aliensrc` files inside the pool, and if possible `.alienmatcher.json`
  or `.snapmatch.json` results.
- OUTPUT: `.scancode.json` and `.scancode.spdx` files inside the `userland` pool
  path of the currently processed package (and also inside the corresponding
  `debian` pool path of the matching debian package, if any). For
  `.scancode.json` data structure, please refer to ScanCode documentation and
  source code. For `.scancode.spdx` data structure, please refer to SPDX specs.

For this to work, you need to have
[ScanCode](https://github.com/nexB/scancode-toolkit) v3.2.3 installed. See
chapter
[Installation of Scancode](#installation-of-scancode) for details.

Execute

This might take several minutes, hours or even days, depending on your machine's
horsepower and on the number and size of packages to scan; please keep in mind
that ScanCode will use all the available cores of your machine during scan:

```sh
aliens4friends scan -s MYSESSION
```

The scan will be executed on the alien source package's main archive, and if a
match was found on Debian during `match` or `snapmatch`, also on that source
package. The default matcher used is `snapmatch`, but with the
`--use-oldmatcher` parameter it is possible to switch to `match`.

<p><details>
<summary><b>See "aliens4friends scan --help" output for details.</b></summary>

```
usage: aliens4friends scan [-h] [-i] [-v | -q] [--dryrun] [-p] [--use-oldmatcher] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  --use-oldmatcher      Use the old alienmatcher.json input files, not snapmatch.json.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 7: Find differences between Alien Packages and the corresponding Debian matching packages

By "differences", we mean the differences in terms of
licensing/copyright/intellectual property, so we just care if license and
copyright statements (if any) have changed, not if just code has changed.


- INPUT: `.scancode.json` files inside `userland` and `debian` pool paths
  related to each alien package and its corresponding debian package, and also
  `.alienmatcher.json` or `.snapmatch.json` results.
- OUTPUT: `.deltacode.json` file inside `userland`

Execute:

```sh
aliens4friends delta -s MYSESSION
```

The default matcher used is `snapmatch`, but with the `--use-oldmatcher`
parameter it is possible to switch to `match`.

<p><details>
<summary><b>See "aliens4friends delta --help" output for details.</b></summary>

```
usage: aliens4friends delta [-h] [-i] [-v | -q] [--dryrun] [-p] [--use-oldmatcher] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  --use-oldmatcher      Use the old alienmatcher.json input files, not snapmatch.json.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

<p><details>
<summary><b>click to see .deltacode.json output data structure example</b></summary>

<!--  hacky trick: using python syntax highlightning to be able to put comments, not allowed in json -->

```python
{
  "tool": {
    "name": "aliens4friends.commons.deltacodeng",
    "version": "0.7.0"
  },
  "header": {
    "compared_json_files": {
      "old_scan_out_file": "/home/user/pool/debian/zlib/1.2.11.dfsg-1/zlib-1.2.11.dfsg-1.scancode.json",
      "new_scan_out_file": "/home/user/pool/userland/zlib/1.2.11-r0/zlib-1.2.11-r0.scancode.json"
                    # this tool could be used also in other contexts, eg. to compare two
                    # different version of the same package, so the compared packages are
                    # generically named "old" and "new"
                    # In this specific use case, "old" means "debian package" and "new" means
                    # "alien package"
    },
    "stats": {
      "same_files": 108,
      "moved_files": 2,
      "changed_files_with_no_license_and_copyright": 0,
      "changed_files_with_same_copyright_and_license": 0,
      "changed_files_with_updated_copyright_year_only": 0,
      "changed_files_with_changed_copyright_or_license": 0,
      "deleted_files_with_no_license_and_copyright": 0,
                    # "deleted" means "files found in the matching debian package, but not in the alien package"
      "deleted_files_with_license_or_copyright": 0,
      "new_files_with_no_license_and_copyright": 86,
      "new_files_with_license_or_copyright": 59,
                    # "new" means "files found in the alien package, but not in the debian matching package"
                    # (usually you have a value > 0 here when debian package maintaners stripped out some
                    # source files for Debian policy reasons - eg. files related to unsupported platforms etc.)
      "old_files_count": 108,
                    # total files found in the debian package
      "new_files_count": 253
                    # total files found in the alien package
    }
  },
  "body": {
    "same_files": [
      "adler32.c",
      "ChangeLog",
      "CMakeLists.txt",
      # [...]
      "test/minigzip.c",
      "watcom/watcom_f.mak",
      "watcom/watcom_l.mak"
    ],
    "moved_files": {
      "old_path": "zconf.h",
      "new_path": "zconf.h.in"
    },
    "changed_files_with_no_license_and_copyright": [],
    "changed_files_with_same_copyright_and_license": [],
    "changed_files_with_updated_copyright_year_only": {},
                    # findings here would not include just a list, but a dictionary where the key
                    # is the filename, and the value is a dictionary with diff results
    "changed_files_with_changed_copyright_or_license": {},
                    # same as above
    "deleted_files_with_no_license_and_copyright": [],
    "deleted_files_with_license_or_copyright": [],
    "new_files_with_no_license_and_copyright": [
      "contrib/ada/readme.txt",
      "contrib/ada/zlib.gpr",
      "win32/Makefile.bor",
      # [...]
      "win32/VisualC.txt",
      "win32/zlib.def"
    ],
    "new_files_with_license_or_copyright": [
      "contrib/ada/buffer_demo.adb",
      "contrib/ada/mtest.adb",
      # [...]
      "win32/Makefile.msc",
      "win32/README-WIN32.txt",
      "win32/zlib1.rc"
    ]
  }
}
```

</details></p>

### Step 8: Create Debian SPDX file from debian/copyright file

- INPUT: debian source files downloaded by [match or
  snapmatch](#step-5-find-a-matching-debian-source-package)
- OUTPUT: `.debian.spdx` and `_debian_copyright` file in the `debian` pool path
  of the debian package

All Debian packages should have a machine readable `debian/copyright` file
following [DEP5
specs](https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/),
containing copyright and license metadata for each source file found in the
package. Such copyright and license metadata are reviewed by the maintainers of
the Debian package and by the community, as OSS license compliance is a key part
of the Debian Project from the very beginning.

`Debian2SPDX` takes care of extracting and parsing `debian/copyright` and
`debian/control` files, and to convert all metadata found in them in SPDX
format.

In case `debian/copyright` is not machine-parseable, or if there are any parsing
errors, `.debian.spdx` file cannot be created. In any case, as a convenience,
Debian2SPDX extracts the `debian/copyright` file from debian source archives
into the `debian` pool path of the debian package, to allow manual inspection.

Execute:

```sh
aliens4friends spdxdebian -s MYSESSION
```

The default matcher used is `snapmatch`, but with the `--use-oldmatcher`
parameter it is possible to switch to `match`.

<p><details>
<summary><b>See "aliens4friends spdxdebian --help" output for details.</b></summary>

```
usage: aliens4friends spdxdebian [-h] [-i] [-v | -q] [--dryrun] [-p] [--use-oldmatcher] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  --use-oldmatcher      Use the old alienmatcher.json input files, not snapmatch.json.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 9: Create Alien SPDX file out of Debian SPDX file (reusing license metadata)

- INPUT: `.scancode.spdx` and `.deltacode.spdx` files in the `userland` pool
  path of the alien package, and `.debian.spdx` file in the `debian` pool path
  of the matching debian package, and also `.alienmatcher.json` or
  `.snapmatch.json` results.
- OUTPUT: `.alien.spdx` file in the `userland` pool path of the alien package.

If the alien package has no main source archive, or if there is no matching
debian package, this step cannot be performed.

If similarity between the alien package's main internal source archive and the
debian matching package is > 30%,  `debian/copyright` license and copyright
metadata are applied to all alien package files that match with debian package
files, from an IP compliance perspective (such metadata are applied as
[ConcludedLicense](https://spdx.github.io/spdx-spec/4-file-information/#45-concluded-license),
because they have been reviewed by a trusted community). If similarity is > 92%,
also license metadata concerning the whole package are applied. If similarity is
100%, all metadata are applied.

For the non matching files, results from the `.scancode.spdx` file are applied
instead, but as [LicenseInfoInFile], as they come from an automated scanner and
not from a human review.

If similarity is < 30%, only `.scancode.spdx` results are applied instead,
always as [LicenseInfoInFile].

[LicenseInfoInFile]: https://spdx.github.io/spdx-spec/4-file-information/#46-license-information-in-file

Similarity is calculated by adding the following stats found in
`.deltacode.json` file:

```
same_files
moved_files
changed_files_with_no_license_and_copyright
changed_files_with_same_copyright_and_license
changed_files_with_updated_copyright_year_only
```

The same categories (excluding `moved_files`) are used to define what a
"matching file" is, from an IP compliance perspective, and decide whether
to apply `debian/copyright` metadata or not, for each alien package file.

Execute:

```sh
aliens4friends spdxalien -s MYSESSION
```

The default matcher used is `snapmatch`, but with the `--use-oldmatcher`
parameter it is possible to switch to `match`.

<p><details>
<summary><b>See "aliens4friends spdxalien --help" output for details.</b></summary>


```
usage: aliens4friends spdxalien [-h] [-i] [-v | -q] [--dryrun] [--apply-debian-full] [-p] [--use-oldmatcher] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  --apply-debian-full   apply all debian/copyright decisions as LicenseConcluded in full, without any filter
  -p, --print           Print result also to stdout.
  --use-oldmatcher      Use the old alienmatcher.json input files, not snapmatch.json.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 10: Upload to Fossology, schedule Fossology scanners, import Alien/Debian SPDX to Fossology

- INPUT: `.aliensrc` and (if available) `.alien.spdx` files in the `userland`
  pool path of the package
- OUTPUT: `.fossy.json` file with metadata obtained through Fossology API

In this step all source files contained in the `files` folder within the
`.aliensrc` package/tarball are  uploaded to Fossology.

Before performing this step, you should have configured environment variables in
your `.env` file (see above, Step 2) in order to allow `aliens4friends` to
access your fossology server (particularly, `FOSSY_USER`, `FOSSY_PASSWORD`,
`FOSSY_GROUP_ID`, `FOSSY_SERVER`; such parameters default to, respectively,
'fossy', 'fossy', 3 and 'http://localhost/repo', that are suited to access a
local test instance of Fossology installed via docker).

For reasons related to Fossology's policy on uploaded archives unpacking, the
whole content of the `files/` folder is packed into a single temporary `.tar.xz`
file (without the leading `files/` path component) and uploaded to Fossology.
By using that specific format (`.tar.xz`) we are sure that Fossology does not
create any subfolder while unpacking the main source archive (so we'll get
"clean" file paths in the final SPDX report that Fossology will generate at a
later stage).

The resulting upload is renamed following the scheme `<name>@<version>` (where
name and version refer to the uploaded alien package). Such upload name must be
unique within Fossology, and if an upload named `<name>@<version>` is already
found in Fossology, it is not uploaded again, assuming that it is exactly the
same source package. This naming scheme is both human-readable and
machine-parseable, and it is a subset of the more comprehensive [purl
scheme](https://github.com/package-url/purl-spec).

Fossology automated license and copyright scanners (`monk`, `nomos`, `ojo` and
`copyright`) are launched, as well as the `ojo_decider` agent, that
automatically makes `LicenseConcluded` decisions based on REUSE/SPDX tags found
in files. This way, a REUSE compliant package will not need any further human
review; and a partially REUSE compliant package will need review only for the
files  that have no REUSE/SPDX tag.

Then the `.alien.spdx` file generated by the previous step is converted to the
RDF/XML format with [java spdx-tools](https://github.com/spdx/tools)[^javatools]
(because Fossology requires such format) and imported into Fossology. This
way ScanCode copyright and license findings are imported into Fossology, thus
enriching Fossology's scanners results License and copyright; license
and copyright information found in the matching Debian package (if any) are
automatically applied as `LicenseConcluded` decisions.

This way, if a package is ~100% matching to the corresponding Debian
package, the package will not need any further human review on Fossology. If
matching is only partial, at least the matching files (from a license and
copyright standpoint, see Step 8) will not need human review.

Finally, Fossology audit/review data are downloaded from Fossology API and
saved, in json format, within a `.fossy.json` file.

[^javatools]: Python spdx tools, widely used in this project, have incomplete
spdx/rdf support

Execute:

```sh
aliens4friends upload --folder my-folder-on-fossology -s MYSESSION
```

<p><details>
<summary><b>click to see .fossy.json output data structure example</b></summary>

```python
{
  "origin": "http://localhost/repo",
  "summary": {
    "id": 300,                          # upload id within Fossology
    "uploadName": "acl@2.2.53-r0",
    "mainLicense": "GPL-2.0-or-later",
    "uniqueLicenses": 46,
    "totalLicenses": 626,
    "uniqueConcludedLicenses": 2,
    "totalConcludedLicenses": 232,
    "filesToBeCleared": 0,              # files that haven't been reviewed yet
                                        # (red dots, in Fossology)
    "filesCleared": 232,                # total files that requires human review,
                                        # including those already reviewed
                                        # (red + green dots, in Fossology)
    "clearingStatus": "Open",
    "copyrightCount": 2532              # number of copyright statements
  },
  "licenses": [
    {
      "filePath": "acl@2.2.53-r0/acl-2.2.53.tar.gz/acl-2.2.53.tar/acl-2.2.53/README",
      "agentFindings": [
        "GPL-2.0-or-later",
        "GPL-2.0-or-later"
      ],
      "conclusions": [
        "GPL-2.0-or-later"
      ]
    },
    # [... all files contained in the package ...]
  ]
}
```

</details></p>

<p><details>
<summary><b>See "aliens4friends upload --help" output for details.</b></summary>

```
usage: aliens4friends upload [-h] [-i] [-v | -q] [--dryrun] [--description DESCRIPTION] --folder FOLDER -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  --description DESCRIPTION
                        Fossology upload description
  --folder FOLDER       Fossology folder where to upload Alien Packages
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 11: Generate final SPDX file, after human review

- INPUT: `.aliensrc` file, and `.alien.spdx` file (if available)
- OUTPUT:
      - `.fossy.json` file with metadata obtained through Fossology API after
        human review
      - `.final.spdx` file, containing:
          - automated scanner findings
          - REUSE-compliance-based decisions
          - debian/copyright-based decisions
          - human auditor decisions recorded by Fossology

In this step, after human auditor review on Fossology, all metadata collected in
the previous steps, both from automated and from human sources, and metadata
processed by human auditors, are all put together in order to generate a final
SPDX file reflecting the audit progress on that package.

An intermediate SPDX file is generated from Fossology, patched to be fully SPDX
compliant,[^fossology1] and then integrated with package-level metadata coming
from `.aliensrc` and `.alien.spdx` files.[^fossology2]

[^fossology1]: Fossology still uses some deprecated license identifiers and
file paths are not represented in a way conformant to SPDX specs.

[^fossology2]: Even if `.alien.spdx` was imported into Fossology at Step 9,
Fossology does not collect package-level metadata from imported SPDX files, so
such metadata need to be added again at this Step 11.

Execute:

```sh
aliens4friends fossy -s MYSESSION
```

<p><details>
<summary><b>See "aliens4friends fossy --help" output for details.</b></summary>

```
usage: aliens4friends fossy [-h] [--sbom] [-i] [-v | -q] [--dryrun] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  --sbom                Create a SPDX Bill Of Material (sbom) file
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

### Step 12: Harvest all results and create a final report

- INPUT: `.deltacode.json`, `.scancode.json`, `.fossy.json`, `.snapmatch.json`
  and `.alienmatcher.json` files
- OUTPUT: `POOL/stats/<some-dated-name>.harvest.json` as report for the graphical Dashboard

Execute:

```sh
aliens4friends harvest -s MYSESSION
```

The default matcher used is `snapmatch`, but with the `--use-oldmatcher`
parameter it is possible to switch to `match`.

<p><details>
<summary><b>See "aliens4friends harvest --help" output for details.</b></summary>

```
usage: aliens4friends harvest [-h] [-i] [-v | -q] [--dryrun] [-p] [--add-missing] [--filter-snapshot FILTER_SNAPSHOT] [-b WITH_BINARIES [WITH_BINARIES ...]] [-o OUTPUT] [--use-oldmatcher] -s SESSION

optional arguments:
  -h, --help            show this help message and exit
  -i, --ignore-cache    Ignore the cache pool and overwrite existing results and tmp files. This overrides the A4F_CACHE env var.
  -v, --verbose         Show debug output. This overrides the A4F_LOGLEVEL env var.
  -q, --quiet           Show only warnings and errors. This overrides the A4F_LOGLEVEL env var.
  --dryrun              Log operations to be done without doing anything
  -p, --print           Print result also to stdout.
  --add-missing         Add missing input files to the report while harvesting.
  --filter-snapshot FILTER_SNAPSHOT
                        keep only tagged releases plus the given snapshot release
  -b WITH_BINARIES [WITH_BINARIES ...], --with-binaries WITH_BINARIES [WITH_BINARIES ...]
                        Add only given binary_packages to the report while harvesting, separate multiple entries with space.
  -o OUTPUT, --output OUTPUT
                        Write results into this path
  --use-oldmatcher      Use the old alienmatcher.json input files, not snapmatch.json.
  -s SESSION, --session SESSION
                        Use a session to create a list of packages, otherwise all packages inside the pool are used
```

</details></p>

## Special commands

### CVEcheck

- INPUT: `POOL/stats/<some-dated-name>.harvest.json`
- OUTPUT: `POOL/stats/<some-dated-name>.harvest.cve.json` as report for the graphical Dashboard

Check potential security vulnerabilities for debian-like software packages. The
command searches the current national vulnerability database
([NIST](https://nvd.nist.gov/vuln/data-feeds)) and try to find potential
security vulnerabilities for the searched software product. Local copies of NIST
database feeds will be updated once every 24h.

The retrieved CVE's can be searched by `vendor`, `product` and `version`.
Alternatively, an existing `harvest.json` can be parsed and automatically
supplemented with appropriate results.

Execute:

```sh
aliens4friends cvecheck --harvest my-harvest-file-inside-the-pool.harvest.json
```

or

```sh
aliens4friends cvecheck --vendor intel --product sgx_dcap --version 1.10.100.4
```

<p><details>
<summary><b>See "aliens4friends cvecheck --help" output for details.</b></summary>

```
usage: aliens4friends cvecheck [-h] [--product [PRODUCT]] [--version [VERSION]] [--vendor [VENDOR]] [--startfrom [STARTFROM]] [--harvest [HARVEST]]

optional arguments:
  -h, --help            show this help message and exit
  --product [PRODUCT]   Product slug
  --version [VERSION]   Version slug
  --vendor [VENDOR]     Vendor slug
  --startfrom [STARTFROM]
                        Only CVEs after YYYY
  --harvest [HARVEST]   harvest.json file name in pool. If option is set,
                        single arguments will be ignored and harvest.json will be
                        scanned instead. A .cve.json will be saved in pool stats dir
```
</details></p>

#### Result of CVE checks

The result data contains 2 areas:
- `identified`: Clearly identified and applicable CVE's for the software in
  question.
- `review`: Special cases not currently covered or applicability configurations
  not clearly interpretable (for manual review).

#### Procedure

- if existing feeds are older than one day, the feeds are updated
- all feeds will be parsed and potential candidates are prefiltered by vendor +
  product
- all potentially applicable candidates are searched for affected version ranges
  and false positives are eliminated as far as possible
- for this purpose, the applicability criteria available in the cve's are
  evaluated. The entire filter logic is located in `cve_check.py`
  (`filterCandidates()`) and is extensively documented
- applicable cve's are saved 1:1 as result in json format or added to
  harvest.json, depending on operating mode

#### todos & caveats

Currently, only the search for software is supported. The evaluation is
therefore incomplete in certain cases:
- Applicability criteria: AND operator is not supported (assuming that CVE's,
  which are only applicable in combination with a specific hardware or operating
  system, are not needed for current frameworks).
- Applicability criteria: Nested nodes (childs) are not supported.
- Whitelist support: Existing whitelists for filtering wrong entries are not yet
  respected.
- Support CPE2.3 special characters: `- & ?`
- Reduction of data sets - Only relevant result data

All special cases not covered are written separately to any results for manual checking.

#### disclaimer
This program is intended as an aid in identifying potentially affected software
applications and versions. Any results are not and can never be complete, and
are therefore considered indicative only.

#### info
Evaluation and applicability of application criteria:
https://stackoverflow.com/questions/56680580/nvd-json-feeds-tags-meaning-and-their-purpose

CPE 2.3 formatted string binding:
https://www.govinfo.gov/content/pkg/GOVPUB-C13-c213837a04c3bcc778ebfd420c6a3f2a/pdf/GOVPUB-C13-c213837a04c3bcc778ebfd420c6a3f2a.pdf

### Session

#### Filter

You can filter out packages from the current session's package list with

```sh
aliens4friends session -s <session-name> --filter [FILTER_NAME]
```

Filters are:
- `score-gt=[a-number]`: to filter out all package with a score greater than `a-number`
- `include-exclude=[json-file]`: to hardcode includes or excludes of packages per name
```json
  {
    "include": [],
    "exclude": []
  }
```
- `only-uploaded`: to select only packages that were uploaded to Fossology, that
  is, which were not already present on fossology. This filter is only useful
  after a `fossy` or `upload` invocation

#### Locking

You can lock your session with a key. We use the environmental variable
`A4F_LOCK_KEY` for this. This key will not be stored inside `.env`, nor in the
pool itself, because those places might be shared among different pipeline runs,
and could be overwritten accidentally. So we store it in an env-var, which is
then pipeline specific. Choose some value as lock key, that is unique to the
current pipeline run.

Locking:
```sh
A4F_LOCK_KEY=pipeline-123-abc-unique aliens4friends session -s <session-name> --lock
```

Unlocking:
```sh
A4F_LOCK_KEY=pipeline-123-abc-unique aliens4friends session -s <session-name> --unlock
```

Both commands allow also a `--force` parameter, to overwrite or remove an
existing lock regardless if the actual lock key is different then the given one.

#### Adding variants

The Dashboard shows audit progress also based on existing package variants - eg. if there are multiple package variants, but only the oldest one has been reviewed in Fossology, the Dashboard regards also the newer one as reviewed in the total file count, because in variants only some single files (patches etc.) are usually changed/added, so it's just a matter of Fossology reuse agent that needs to be scheduled in order to have also the new variant fully reviewed.

However, by harvesting only latest project snapshot's data, previous variants are not included, so the total audited file count provided by the Dashboard is not reliable.

To fix this, we may want to add all available variants to the session before running `upload|fossy` and `harvest` commands. To this purpose, we may run:

```sh
aliens4friends session - s <session-name> --add-variants
```

#### Generate a static csv report

As a convenience, one may want to quickly generate a static report concerning packages included in a specific session (including related Fossology metadata). This may be done by running:

```sh
aliens4friends session - s <session-name> --report <report-filename>
```

### Mirror

The mirror command can be used to mirror all `.tinfoilhat.json` files to a Postgres database.

To do so, make sure that the environment variables (see `.env`)

```
MIRROR_DB_HOST=127.0.0.1
MIRROR_DB_PORT=5432
MIRROR_DB_DBNAME=a4fdb
MIRROR_DB_USER=a4f
MIRROR_DB_PASSWORD=secret
```

point to a Postgres database that holds the schema definition from `infrastructure/database/tinfoilhat_mirror.sql`.

The mirror command has two operation modes: in FULL mode all records from the database
that correspond to the given session are deleted and inserted again; in DELTA mode only files
that do not yet exist in the database are inserted. In the latter case, the key is the
session identifier and full path name to the `.tinfoilhat.json` file.

Here is a sample invocation to import all `.tinfoilhat.json` files from a session identified
by "initial_import" in FULL mode:

```sh
aliens4friends mirror --mode FULL --session "initial_import"
```

After inserting the files for this example run (416 files, 2.1 GB) the output was:

```
aliens4friends:slug=# ALIENS4FRIENDS v0.7.0 with cache pool ~/a4fpool
aliens4friends.commands.command:slug=MIRROR: Start with session 'initial_import'.
aliens4friends.commands.mirror:slug=Mirror(Command) class created
aliens4friends.commands.mirror:slug=connected to Postgres database
aliens4friends.commands.mirror:slug=FULL mode: delete/vacuum done in 38.524 sec
aliens4friends.commands.mirror:slug=100 files processed
aliens4friends.commands.mirror:slug=200 files processed
aliens4friends.commands.mirror:slug=300 files processed
aliens4friends.commands.mirror:slug=400 files processed
aliens4friends.commands.mirror:slug=416 files processed in 69.644 sec
aliens4friends.commands.mirror:slug=disconnected from Postgres database
```

The command is verbose by default, use --quiet to suppress the output.

## Installation and execution with docker

In the root folder of this project, execute the following command, which will
start all docker containers that you need for local development and testing.
Please note, this is not meant to be used on production machines.

```sh
docker-compose up -d
```

Now you have several services at hand:

1) Fossology: Go to `http://localhost:8999` (user = `fossy`; password = `fossy`)
2) Postgres Database for Fossology: \
   `PGPASSWORD=fossy psql -h localhost -p 5555 -U fossy fossology` \
   The data storage is inside `fossydb/`
3) A toolchain docker container that incorporates the following services:
   1) Scancode \
      `docker-compose run --rm toolchain scancode ...`
   3) Aliens4Friends mounted from host machine \
      `docker-compose run --rm toolchain a4f ...`
   5) Spdx Java Tool \
      `docker-compose run --rm toolchain spdxtool ...`

Alternatively you can also install and run `a4f` locally, and just use scancode
from within the container. See [Installation of Scancode/Wrapper](#wrapper) for
further information.

Example `.env` file for docker development (minimal):

```ini
A4F_POOL=${PWD}/your-pool
A4F_LOGLEVEL=DEBUG
FOSSY_SERVER=http://fossology
```

For other configuration options execute `a4f config`.


## Manual installation and execution on your host machine

These steps are not required if you have opted for the Docker Installation
described in chapter [Installation and execution with docker](#installation-and-execution-with-docker).

We assume that you execute `aliens4friends` with `bin/a4f`, and that you have
all requirements installed. See [Requirements and Installation](#requirements-and-installation).

### Installation of Scancode

We have two possibilities:

#### Native

Set the `.env` config: `A4F_SCANCODE=native`

Presently,  only version
[3.2.3](https://github.com/nexB/scancode-toolkit/releases/tag/v3.2.3) is
supported. Follow the instructions inside the official [Scancode
README](https://github.com/nexB/scancode-toolkit#readme) to install it; use
the recommended installation method, not the pip method.

If for any reason the recommended installation method did not work, you can try
this method:

(on Ubuntu)

```bash
apt install python3-pip python3-dev bzip2 xz-utils zlib1g libxml2-dev libxslt1-dev libpopt0 build-essential
```

(on Debian)

```bash
apt install python3-pip python3-dev libbz2-1.0 xz-utils zlib1g libxml2-dev libxslt1-dev libpopt0 build-essential
```

then:

```bash
pip3 install setuptools wheel click==6.7 bitarray==0.8.1 \
  pygments==2.4.2 commoncode==20.10.20 pluggy==0.13.1 \
  extractcode==20.10 plugincode==20.9 typecode==20.10.20 \
  dparse2==0.5.0.4 scancode-toolkit[full]==3.2.3

cd /usr/local/lib/python3.8/dist-packages/scancode

patch -p1 << EOT
--- a/cli.py
+++ b/cli.py
@@ -27,6 +27,9 @@
 from __future__ import print_function
 from __future__ import unicode_literals

+import warnings
+warnings.filterwarnings("ignore")
+
 # Import first because this import has monkey-patching side effects
 from scancode.pool import get_pool
EOT

cd -

scancode --reindex-licenses # required for scancode initialization
```

It should work with python 3.6 or later versions; with later versions, you may
get some warnings when executing it, but it should work anyway.

#### Wrapper

If you do not want to install it, you can also use our scancode
docker wrapper. Set the `.env` config: `A4F_SCANCODE=wrapper`

1) Change directory: `cd <this-repos-root-dir>/infrastructure/docker`
2) Build the image: `docker build -t scancode -f scancode.dockerfile .`
3) Test it:
   - `docker run -it scancode --version` --> Output must be: `ScanCode version 3.2.3`
   - `../utils/scancode-wrapper --version` --> Output must be: `ScanCode version 3.2.3`
4) Link the `scancode-wrapper`
   - either the script's directory into your `$PATH`
   - or the script itself into `/usr/local/bin` with \
     `cd /usr/local/bin/; ln -s <this-repos-root-dir>/infrastructure/utils/scancode-wrapper` as root

Full example which uses the current directory as working directory of Scancode:

```
docker run -it -v $PWD:/userland scancode -n4 -cli --json /userland/scanresult.json /userland
```

- `/userland` is the internal working path.
- The output will have the owner/group id, that was defined during the build.
- See `infrastructure/docker/scancode.dockerfile` for details.

The easiest way is to use the `scancode-wrapper` shell script. See comments
inside that script for details at `infrastructure/utils`.

### Installation of the spdx-tools

As root:

```shell
apt install -y openjdk-11-jre

wget -P /usr/local/lib \
   https://github.com/spdx/tools/releases/download/v2.2.5/spdx-tools-2.2.5-jar-with-dependencies.jar
```

### Installation of Tinfoilhat

wget -O /usr/local/bin/tinfoilhat https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/master/tinfoilhat.py
chmod +x /usr/local/bin/tinfoilhat

### Installation of Aliensrc Creator

wget -O /usr/local/bin/aliensrc_creator https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat/-/raw/master/aliensrc_creator.py
chmod +x /usr/local/bin/aliensrc_creator

### Installation of Fossology (as docker container)

A Fossology 3.9.0 instance is required to run substantial parts of the workflow.
Please refer to Fossology documentation to deploy it.  Fossology version must be
3.9.0, for API compatibility.

#### With docker-compose

Just run `docker-compose up fossology` inside the root folder of this project.

#### With Docker

The following commands will install a Fossology 3.9.0 docker container in your
demo machine, optimized to import huge SPDX files (required to run the
Aliens4Friends workflow).

```shell
docker pull noitechpark/fossology-on-steroids
docker volume create fossy-var
docker volume create fossy-srv
docker run -d \
  --name fossology_a4f \
  --mount source=fossy-var,target=/var \
  --mount source=fossy-srv,target=/srv \
  -p 127.0.0.1:80:80 \
  -p 443:443 \
  noitechpark/fossology-on-steroids
```

The port 80 is open only locally, just to allow Aliens4Friends to locally
connect to Fossology API without the need of configuring an SSL certificate.

The Fossology WebUI will be accessible at `https://<MACHINE_FQDN_OR_IP>/repo`
with the default user name and password `fossy`/`fossy` (change it at first
login).

# Gitlab CI of a complete pipeline with Yocto and Aliens4Friends

To execute a complete Gitlab CI pipeline as described in `.gitlab-ci.yml`, you
need a strong machine with at least 16GB RAM, 1TB hard-disk, and a multi-core CPU.

## Install docker and docker-compose on a Linux machine

As root:
```sh
apt update
apt install apt-transport-https ca-certificates curl software-properties-common gnupg2
curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
apt update
apt install docker-ce
```

To test it, do:
```sh
systemctl status docker
docker -v
```

If you need the docker command as a non-root user (`$USER`), execute these commands:
```sh
sudo usermod -aG docker $USER
docker container run hello-world
```
... the last command is to test a non-root-user execution.

## Install a Gitlub Runner on a Linux machine

1) Go to your project's Gitlab page, and follow the following path: \
   `Settings > CI/CD > Runners > Expand` and install a docker runner on your
   Linux machine. Instruction can be found in the manual of Gitlab.

2) Give it two labels, namely: `soldademo` and `docker`. These are examples, but
   make sure, if you change them, that you also adapt the `.gitlab-ci.yml` file,
   and a name `soldademo-docker`.

## Configure the Gitlab Runner

You need to configure it for two things:
1) Give access to the host's docker deamon
2) Mount the `/build` directory in a read-write mode into it

On your Gitlab Runner host open `/etc/gitlab-runner/config.toml` as root, and
add/change the following lines under `[[runners]]...name = "soldademo-docker"`:
```toml
[runners.docker]
    tls_verify = false
    image = "debian:10"
    privileged = true
    disable_entrypoint_overwrite = false
    oom_kill_disable = false
    disable_cache = false
    volumes = ["/cache", "/build:/build:rw", "/a4fpool:/a4fpool:rw", "/var/run/docker.sock:/var/run/docker.sock"]
```

Where `/build` is your hosts build directory, where `yocto/bitbake` stores its
outputs, caches, downloads etc. In addition, `aliens4friends` has its pool
inside `/a4fpool`. If you need also other pools, to exploit other runner's
caches, mount that too. For example, add `"/ostc:/ostc"` to the `volumes` array.
Read access is sufficient here.

`"/var/run/docker.sock:/var/run/docker.sock"` on the other hand is used to
access the docker daemon on the host. We need also to set `privileged = true`
to make it work.

The log output can be really long, so to see everything we need also to
increase the `output_limit = 102400` inside `[[runners]]`.

## Configure a Gitlab container registry

The `dockerize` stages inside `.gitlab-ci.yml` need a container registry to upload
its images. We use the Gitlab registry for this example. Just make sure that the
`CI_REGISTRY_IMAGE` points to the correct repository.

## Known limitations

### Only use a single branch to trigger the pipeline

Parallel runs are not supported at the moment, because we pass artifacts from one stage
to a subsequent one with a single directory. Also yocto builds in a single path are not
supported. So set the `only` attribute to a single branch inside `.gitlab-ci.yml`.

### Time consuming operations

These pipelines are not meant to run very often, because at the moment with all
flavours, images, and machine combinations to complete a full pipeline it will
take several hours. Hereby, the yoctobuild, Scancode and Fossology upload part
take the most time.

## Contributor's FAQ

This chapter describes some aspects for contributors to this projects. Since we
are not able to write about every part of this project in detail, we list
contributor questions here, and respond to them in a lean manner. Happy hacking,
folks :-)

### I want to understand how the Debian matching works

Debian matching is a process to gather Copyright and License information by
matching the name and version of a given software package to the Debian
repository APIs.

Here two APIs exist:
1) The [Snapshot API](https://snapshot.debian.org) has all ever used
   packages of Debian in a single storage\
   Implementation: [snapmatcher.py](aliens4friends/commons/snapmatcher.py)
2) The [most-recent API](https://api.ftp-master.debian.org) has only the
   most recent versions of each package per Debian release\
   Implementation: [alienmatcher.py](aliens4friends/commons/alienmatcher.py)

API (1) is slow, but has all packages, and can therefore provide better matching
results. API (2) is fast, but might lack a good matching score at the end. See
Aliens4Friends' [match command](#step-5-find-a-matching-debian-source-package)
for further details.

As for the rest both matching algorithms work very similar:
1) Retrieve a list of Debian packages
2) Use the [calc.py#fuzzy_package_score](aliens4friends/commons/calc.py) to get
   a matching score of the package name alone, comparing the given package name
   and all packages coming from point (1)
3) Take the best candidate package, and retrieve all available version strings
4) Calculate a distance between the actual package version and all version strings
5) Find the nearest neighbor with the smallest distance
6) Download the matching package from Debian and unpack it into the pool's `debian` folder
7) Retrieve Debian package information by parsing the various Debian archive descriptions:
   - Format `1.0`
   - Format `3.0 (quilt)`
   - Format `3.0 (native)`

We use the Aliens4Friends pool cache for these operations, so we do not download
or process packages that have already been addressed beforehand. The cache can
be disabled.

A known restriction at the moment is, that we only deal with packages that have
a single archive internally, because we want to find the primary archive first
on our side, before we look at Debian's side for a match.

### I want to add a new sub-command to Aliens4Friends

Lets start from an example command, called `mirror`, which has one special
command line argument: `--mode`. It supports also all *default* and *session*
arguments. The implementation details are not important here, so we skip them.

#### Command line definition
The command line definition can be found under `__main__.py`, here we have two
types of methods, one starting with `parser_` and the other having just the name
of the command as name. In our case, `parser_mirror` describes how to CLI looks
like:

```python
	def parser_mirror(self, cmd: str) -> None:
		self.parsers[cmd] = self.subparsers.add_parser(
			cmd,
			help="Mirror tinfoilhat JSON files to the PostgreSQL database"
		)
		self.parsers[cmd].add_argument(
			"--mode",
			choices=["FULL", "DELTA"],
			default="FULL",
			help="truncate table and mirror all files (FULL) or just mirror files that are not yet present (DELTA)"
		)
    # Add support for the default and session CLI arguments
		self._args_defaults(self.parsers[cmd])
		self._args_session(self.parsers[cmd])
```

...and the `mirror` method just calls the corresponding `execute` method:

```python
	def mirror(self) -> bool:
		return Mirror.execute(
			self.args.session,
			self.args.dryrun,
			self.args.mode
		)
```

#### Mirror Command Execution Configuration

We put these configuration under `commands`. In our case the file is
`mirror.py`, inside we declare a class named `Mirror`, which inherits `Command`.
An actual stub could look like this:

```python
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: ......

import logging

from aliens4friends.commands.command import Command, Processing
from aliens4friends.commons.pool import FILETYPE
from aliens4friends.commons.settings import Settings

# Logger for this file, do not write to stdout/stderr directly for logging purposes
# The default arguments for verbose or quiet outputs are handled via log levels:
# debug, warning and error
logger = logging.getLogger(__name__)

# Exception class for this command only
class MirrorError(Exception):
	pass

class Mirror(Command):

  # Initialize this mirror command, define the processing type, session-id
  # and dry-run options
	def __init__(
    self,
    session_id: str,
    dryrun: bool,
    mode: str
    # eventually add other CLI arguments here
  ):
		# Processing mode should be LOOP: Describe the reason...
		super().__init__(session_id, Processing.LOOP, dryrun)

		# the command line argument --mode, no checks needed,
    # already done by argparse
		self.mode = mode

  # Execute the whole command...
	@staticmethod
	def execute(
		session_id: str = "",
		dryrun: bool = True,
		mode: str = "FULL"
    # eventually add other CLI arguments here
	) -> bool:
		"""
		...write your documentation here...
		"""

		cmd = Mirror(session_id, dryrun, mode)

		if cmd.dryrun:
			# dryrun: return right away, but first call exec_with_paths() to have the files logged
      # just listen all paths or write some log output
			return cmd.exec_with_paths(FILETYPE.TINFOILHAT)

    # Do you need a setup before processing all paths? Put it here...

    # call "run" for each path in a list. If your command, just needs a single call
    # just use "cmd.exec()"
		result = cmd.exec_with_paths(FILETYPE.TINFOILHAT)

    # Do you need to finalize or cleanup after processing all pathrs? Put it here...

		return result

  # Called ones for each path, or just a single time if the command
  # is a one-time shot: See cmd.exec_with_paths or cmd.exec for details.
	def run(self, path: str) -> Union[str, bool]:
		try:
      # Your business logic...
      # If simple, put it here directly, if complex or has logic that can be reused in another command,
      # introduce another class inside "commons"...
		except Exception as ex:
			error = f"fatal error: description of the error: {ex}"
			logger.error(error)
			raise MirrorError(error)
		return True

	def hint(self) -> str:
		# if a mirror command does not get any input, a comment is printed
    # with this hint about what commands the user should have run first
		return "session/add"
```

#### Mirror business logic

If simple, put it into `run` directly, if complex or has logic that can be
reused in another command, introduce another class inside "commons", and call
that then in `run`. See comments above...

### Verbose and quiet output of commands

The `--verbose` and `--quiet` flags just use the log levels `debug` and
`warning` respectively. If you omit these CLI arguments, the default level
`info` is used. So, in your code start your Python file with

```python
import logging

logger = logging.getLogger(__name__)
```

Then, just the log method you need. Consider, `error` as something unrecoverable,
which should maybe also raise an exception. `warning` something that can also be
skipped in certain circumstances, or from which we have a recover strategy. An
`info` log should be something to make the user understand that the process is
still running or to gather some statistics while running, `debug` on the other
hand should just be used when we want to find bugs. Remove eventual `debug` log
calls, that are only useful for the very first implementation.

### String formatting

We opted for the f-string format, so please stick to it for most cases. If you
need some special formatting, where `str.format()` or modulo (`%`) are better
suited, you can still use it though.

For example, `print(f"Hello, {name}")` and not `print("Hello, %s" % name)`.


## References

<!-- Add all references here, so they can be used throughout this document without the URL -->
[TinfoilHat]: https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat
[OSS Compliance Pipeline]: https://git.ostc-eu.org/oss-compliance/pipelines

- [TinfoilHat]
- [OSS Compliance Pipeline]

