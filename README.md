# Aliens for Friends

*Documentation: v1 from 2021-04-08*

This is a tool for Software Composition Analysis (SCA), expressly designed to
analyze Yocto/bitbake builds -- but it could be usefully adopted in any software
composition context where a package manager is missing, and where source code
provenance and license/copyright metadata are often missing, messy, uncertain
and/or imprecise.

*Our metaphor goes like this: We invite some aliens (third party software
components), that is unknown species, to a pool party (our fancy FLOSS
project), and hopefully we can after some interaction understand if they are
friends or not (to avoid having our pool party stopped by the Police because of
strange things they bring or do...). So in the best case, those aliens become
friends :-)*

The main goal is to automatically detect as many license and copyright
information as possible by comparing "alien" source packages with packages found
in existing trusted sources, like for instance Debian.

We took Debian as a primary "source of truth" beacause it has a strict policy to
include packages in its distribution (also from a FLOSS compliance standpoint)
and because it is backed by a community that continuously checks and "audits"
source code to that purpose. Other similar sources of truth may be added in the
future.

The overall idea is to avoid reinventing the wheel: if copyright and license
metadata have already been reviewed by a trusted community, it does not make
sense to redo their work by auditing the same code again and again.

More generally, the idea is that if a similar (or same) software package has
been already included in Debian, it means that it is a well-known component, so
it is a friend, and we can safely invite it to our party.


- [Aliens for Friends](#aliens-for-friends)
	- [Workflow](#workflow)
		- [Step #1: Create an Alien Package](#step-1-create-an-alien-package)
		- [Step #2: Configure the tool](#step-2-configure-the-tool)
		- [Step #3: Add the Alien to the pool](#step-3-add-the-alien-to-the-pool)
		- [Step #4: Find a matching Debian source package](#step-4-find-a-matching-debian-source-package)
		- [Step #5: Scan the code to detect license/copyright information](#step-5-scan-the-code-to-detect-licensecopyright-information)
		- [Step #6: Find differences between Aliens and their matching packages](#step-6-find-differences-between-aliens-and-their-matching-packages)
		- [Step #7: Enrich the result with tinfoilhat](#step-7-enrich-the-result-with-tinfoilhat)
		- [Step #8: Harvest all results and create a final report](#step-8-harvest-all-results-and-create-a-final-report)
	- [Installation of Scancode](#installation-of-scancode)
		- [Native](#native)
		- [Wrapper](#wrapper)

## Workflow

We start with an example. Assume we have a source code package called `zlib` in
version `1.2.11-r0`, and want to determine license and copyright information.



### Step #1: Create an Alien Package

First thing to do is to create a so-called Alien Package. If you use bitbake as
a building system, you can use the scripts contained in the [TinfoilHat
prject](https://git.ostc-eu.org/oss-compliance/toolchain/tinfoilhat).

Let's assume that our alien package is named `zlib-1.2.11-r0.aliensrc`. The
file-extension `.aliensrc` is mandatory, the name is arbitrary. An alien package
is a tar-ball, with no-compression. It must have an internal structure like
the following:

```
├── aliensrc.json
└── files
    ├── ldflags-tests.patch
    ├── run-ptest
    └── zlib-1.2.11.tar.xz
```

The file `aliensrc.json` is mandatory; it should be added for first, at the beginning of the tarball file (so it can be faster extracted) and contains all metadata information of this alien package.

<p><details>
<summary><b>click to see aliensrc.json data structure example</b></summary>

```python
{
    "version": 1,                   # the version of this json spec
    "source_package": {             # the data part of this source package
        "name": [                   # some packages have more than one name, ordered by priority (top=most important)
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
                       "package_arch": "armv7vet2hf-neon",
                       "author": null,
                       "homepage": "http://zlib.net/",
                       "summary": "Zlib Compression Library",
                       "description": "Zlib is a general-purpose, patent-free, lossless data compression library which is used by many different programs.",
                       "license": "Zlib",
                       "depends": "virtual/arm-poky-linux-musleabi-gcc virtual/arm-poky-linux-musleabi-compilerlibs virtual/libc ",
                       "provides": "zlib ",
                       "cve_product": null
		},
        "files": [                  # files, that are included in the "files" folder inside the alien package
            {
                "name": "zlib-1.2.11.tar.xz",
                                    # the file name
                "sha1": "e1cb0d5c92da8e9a8c2635dfa249c341dfd00322",
                                    # file checksum (only sha1 is supported)
                "src_uri": "https://downloads.sourceforge.net/libpng/zlib/1.2.11/zlib-1.2.11.tar.xz",
                                    # the provenance, that is, the place where the upstram package came from
                "files_in_archive": 253
                                    # The file count inside the tarball archive
            },
            {
                "name": "ldflags-tests.patch",
                "sha1": "f370a10d1a454cdcd07a8d164fe0d65b32b6d2a9",
                "src_uri": "file://ldflags-tests.patch",
                                    # the provenance: in this case "unknown",
                                    # since the file was just added from a filesystem
                "files_in_archive": false
                                    # false, if no archive, 0 if the archive is empty
            }
        ]
    }
}
```

</details></p>

One archive in the `files` list is considered the main archive, which will be
compared to trusted source repositories. The tool scans also files of additional
archives, but those archives are not used to find matching archives on Debian or
other source repos. In case of multiple archives, possible parameters attached to the
`src_uri` can be used (if known) to determine which is the main archive (this is
bitbake-specific, though).

### Step #2: Configure the tool

Execute:
```sh
aliens4friends config > .env
```

This creates a `.env` file with the default configuration options, if the `.env`
did not exist before. You can now open that file and change as you like it.

See `aliens4friends config --help` for details.


### Step #3: Add the Alien to the pool

Execute:
```sh
aliens4friends add zlib-1.2.11-r0.aliensrc
```

This will add the package to our pool (party). All data that comes from the user will be stored in the folder `userland` with sub-folders named `<package-name>/<package-version>`. So in our case `userland/zlib/1.2.11-r0`. Intermediate results also land in this directory.

See `aliens4friends add --help` for details.

### Step #4: Find a matching Debian source package

- INPUT: `.aliensrc` files inside the pool
- OUTPUT: `.alienmatcher.json` file inside the `userland` pool path regarding
  the current processed package.

Execute:
```sh
aliens4friends match
```

This will search a match for any package, that has been added to the pool. If
you want to restrict the search use `glob_name` and `glob_version` parameters.
For example:

```sh
aliens4friends match 'zlib*'
```

See `aliens4friends match --help` for details.

### Step #5: Scan the code to detect license/copyright information

- INPUT: `.aliensrc` files inside the pool, and if possible `.alienmatcher.json`
  results.
- OUTPUT: `.scancode.json` files inside the `debian` or `userland` pool path
  regarding the current processed package.

For this to work, you need to have
[Scancode](https://github.com/nexB/scancode-toolkit) installed. See chapter
[Installation of Scancode](#installation-of-scancode) for details.

Execute (this might take several minutes):
```sh
aliens4friends scan
```

The scan will be executed on the alien source package's main archive, and if a
match was found on Debian during `match`, also on that source package.

See `aliens4friends scan --help` for details.

### Step #6: Find differences between Aliens and their matching packages

With "differences" we mean in terms of licensing/copyright/intellectual property...

- INPUT: `.scancode.json` files inside `debian` and `userland` pool paths which
  must match
- OUTPUT: `.deltacode.json` file inside `userland`

Execute:
```sh
aliens4friends delta
```

See `aliens4friends delta --help` for details.

### Step #7: Enrich the result with tinfoilhat

This is a Yocto-specific step. Add `.tinfoilhat.json` results to the pool for
more details inside the final result.

Execute:
```sh
aliens4friends add zlib-1.2.11-r0.tinfoilhat.json
```

### Step #8: Harvest all results and create a final report

- INPUT: `.deltacode.json`, `.scancode.json`, `.fossy.json` and `.alienmatcher.json` files
- OUTPUT: `POOL/stats/<some-dated-name>.json` as report for our graphical Dashboard

Execute:
```sh
aliens4friends harvest
```

See `aliens4friends harvest --help` for details.

## Installation of Scancode

We have two possibilities:

### Native
Set the `.env` config: `A4F_SCANCODE=native`
At the moment only version
[3.2.3](https://github.com/nexB/scancode-toolkit/releases/tag/v3.2.3) is
supported. Follow the instructions inside the official [Scancode
README](https://github.com/nexB/scancode-toolkit#readme) to install it.

### Wrapper
If you do not want to install it, you can also use our scancode
docker wrapper. Set the `.env` config: `A4F_SCANCODE=wrapper`

1) Change directory: `cd <this-repos-root-dir>/scancode`
2) Build the image: `docker build -t scancode .`
3) Test it: `docker run -it scancode --help`
4) Link it into your `$PATH`

Full example which uses the current directory as working directory of Scancode:
```
docker run -it -v $PWD:/userland scancode -n4 -cli --json /userland/scanresult.json /userland
```
- `/userland` is the internal working path.
- The output will have the owner/group id, that was defined during the build.
- See `scancode/Dockerfile` for details.

The easieast way is to use the `scancode-wrapper` shell script. See comments
inside that script for details.
