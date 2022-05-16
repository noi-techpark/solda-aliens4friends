#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Alberto Pianon <pianon@array.eu>

import setuptools
from aliens4friends.commons.settings import Settings

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aliens4friends",
    version=Settings.VERSION,
    author="Alberto Pianon, Peter Moser, Martin Rabanser, Alex Complojer, Chris Mair",
    author_email="pianon@array.eu, p.moser@noi.bz.it, martin.rabanser@rmb.bz.it, alex@agon-e.com, chris@1006.org",
    description="Aliens4Friends",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://git.ostc-eu.org/oss-compliance/toolchain/aliens4friends",
    packages=setuptools.find_packages(
        exclude=('scancode/Dockerfile', 'scancode/scancode-wrapper')
    ),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires='>=3.6',
    install_requires=[
        'wheel==0.34.2',
        'numpy==1.19.5',
        'python-debian==0.1.39',
        'spdx-tools==0.6.1',
        'fossology==0.2.0',
        'python-dotenv==0.15.0',
        'packaging==20.9',
        'flanker==0.9.11',
        'deepdiff==5.2.3',
        'beautifulsoup4==4.9.3',
		'psycopg2==2.9.1'
    ],
    scripts=['bin/a4f', 'bin/aliens4friends'],
    license_files=['LICENSE',],
    zip_safe=False, # needed to make dotenv work
)
