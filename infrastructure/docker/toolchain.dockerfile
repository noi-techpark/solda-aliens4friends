# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 NOI Techpark <p.moser@noi.bz.it>
#
# This script is to run spdx-tools and aliens4friends on the host machine,
# without having to install all dependencies there.
#
# Build the image (from the root directory):
#     docker build -t toolchain -f infrastructure/docker/toolchain.dockerfile .
#
# Test it:
#     docker run -it toolchain a4f help
#     docker run -it toolchain spdxtool
#     docker run -it toolchain scancode --help
#
FROM python:3.8

# TODOS
# - Use slim or alpine versions if possible
# - use a multi-stage build and copy only necessary files from spdxtool and scancode
# - cleanup apt-get caches
# - combine layers that should be together with a single RUN command

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk-headless bzip2 sudo lzip && \
	apt-get autoremove --purge -y && apt-get clean && rm -rf /var/lib/apt/lists/*

### SPDXTOOL INSTALLATION
# Do not use ENV SPDXTOOL_RELEASE=2.2.5, to leverage the docker build cache
COPY infrastructure/utils/spdxtool-wrapper /usr/local/bin/spdxtool
RUN wget -P /usr/local/lib \
    https://github.com/spdx/tools/releases/download/v2.2.5/spdx-tools-2.2.5-jar-with-dependencies.jar && \
	chmod +x /usr/local/bin/spdxtool

### SCANCODE INSTALLATION
COPY infrastructure/docker/scancode.patch /tmp
RUN pip3 install setuptools wheel click==6.7 bitarray==0.8.1 \
      pygments==2.4.2 commoncode==20.10.20 pluggy==0.13.1 \
	  extractcode==20.10 plugincode==20.9 typecode==20.10.20 \
	  dparse2==0.5.0.4  scancode-toolkit[full]==3.2.3 && \
	cd /usr/local/lib/python3.8/site-packages/scancode && \
    patch -p1 < /tmp/scancode.patch && \
	cd - && \
    rm /tmp/scancode.patch && \
	scancode --reindex-licenses

### Prepare Python development prerequisites
#
ENV PATH=/code/bin:$PATH
COPY setup.py README.md /code/
COPY bin/* /code/bin/
COPY aliens4friends /code/aliens4friends/
RUN cd /code && \
	pip3 install --upgrade pip && \
	pip3 install python-dotenv && \
	pip3 install anybadge && \
	pip3 install . && \
	python -c "from flanker.addresslib import address" >/dev/null 2>&1

RUN useradd --create-home --uid 1000 --shell /bin/bash a4fuser && \
	usermod -aG sudo a4fuser && \
	echo "a4fuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER a4fuser
CMD [ "bash" ]
