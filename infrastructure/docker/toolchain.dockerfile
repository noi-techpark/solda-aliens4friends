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

RUN apt-get update && \
    apt-get -y install openjdk-11-jdk-headless bzip2

### SPDXTOOL INSTALLATION
#
ENV SPDXTOOL_RELEASE=2.2.5
COPY infrastructure/utils/spdxtool-wrapper /usr/local/bin/spdxtool
RUN wget -P /usr/local/lib \
    https://github.com/spdx/tools/releases/download/v${SPDXTOOL_RELEASE}/spdx-tools-${SPDXTOOL_RELEASE}-jar-with-dependencies.jar
RUN chmod +x /usr/local/bin/spdxtool

### SCANCODE INSTALLATION
#
ENV SCANCODE_RELEASE=3.2.3
ENV PATH=/scancode-toolkit:$PATH
RUN wget https://github.com/nexB/scancode-toolkit/releases/download/v${SCANCODE_RELEASE}/scancode-toolkit-${SCANCODE_RELEASE}.tar.bz2
RUN mkdir /scancode-toolkit && \
    tar xjvf scancode-toolkit-*.tar.bz2 -C scancode-toolkit --strip-components=1
RUN scancode --reindex-licenses

### Prepare Python development prerequisites
#
COPY setup.py README.md /code/
COPY bin/* /code/bin/
RUN cd /code && pip3 install .
RUN python -c "from flanker.addresslib import address" >/dev/null 2>&1

CMD [ "bash" ]
