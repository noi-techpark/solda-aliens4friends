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
FROM python:3.6

# TODOS
# - Use slim or alpine versions if possible
# - use a multi-stage build and copy only necessary files from spdxtool and scancode
# - cleanup apt-get caches
# - combine layers that should be together with a single RUN command

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk-headless bzip2 && \
	apt-get autoremove --purge -y

### SPDXTOOL INSTALLATION
# (we no longer use ENV here for the version, since that would invalidate this layer every time)
COPY infrastructure/utils/spdxtool-wrapper /usr/local/bin/spdxtool
RUN wget -P /usr/local/lib \
    https://github.com/spdx/tools/releases/download/v2.2.5/spdx-tools-2.2.5-jar-with-dependencies.jar && \
	chmod +x /usr/local/bin/spdxtool

### SCANCODE INSTALLATION
# (we no longer use ENV here for the version, since that would invalidate this layer every time)
ENV PATH=/scancode-toolkit:$PATH
RUN wget https://github.com/nexB/scancode-toolkit/releases/download/v3.2.3/scancode-toolkit-3.2.3.tar.bz2 && \
	mkdir /scancode-toolkit && \
    tar xjvf scancode-toolkit-*.tar.bz2 -C scancode-toolkit --strip-components=1 && \
	rm -f scancode-toolkit-*.tar.bz2 && \
	scancode --reindex-licenses

### CERTIFICATE INSTALLATION
# This is needed for the fossology-wrapper to access a protected fossology instance
ARG FOSSY_IP_ADDRESS=127.0.0.1
ARG FOSSY_HOSTNAME=localhost
ARG FOSSY_SSL_CERT
RUN echo "$FOSSY_IP_ADDRESS  $FOSSY_HOSTNAME" >> /etc/hosts && \
    echo "$FOSSY_SSL_CERT" > /usr/local/share/ca-certificates/fossology.crt  && \
    update-ca-certificates --fresh > /dev/null  && \
    cp /etc/ssl/certs/ca-certificates.crt /usr/local/lib/python3.6/site-packages/certifi/cacert.pem

### Prepare Python development prerequisites
#
ENV PATH=/code/bin:$PATH
COPY setup.py README.md /code/
COPY bin/* /code/bin/
COPY aliens4friends /code/aliens4friends/
RUN cd /code && pip3 install python-dotenv && pip3 install . && \
	python -c "from flanker.addresslib import address" >/dev/null 2>&1

RUN apt-get install -y sudo && \
	useradd --create-home --uid 1000 --shell /bin/bash a4fuser

USER a4fuser
CMD [ "bash" ]
