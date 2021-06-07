# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 NOI Techpark <p.bertolla@noi.bz.it>
# SPDX-FileCopyrightText: 2021 NOI Techpark <p.moser@noi.bz.it>
#
# This script is to run scancode on a host machine, without having to
# install all dependencies there.
#
# Build the image:
#     docker build -t scancode .
#
# Test it:
#     docker run -it scancode --help   (or any other scancode parameter)
#
# Full example which uses the current directory as working directory of Scancode:
#     docker run -it -v $PWD:/userland scancode -n4 -cli --json /userland/scanresult.json /userland
#

FROM python:3.6

ARG USER_ID=1000
ARG GROUP_ID=1000

ENV SCANCODE_RELEASE=3.2.3

RUN apt-get update && apt-get install -y bzip2

RUN wget https://github.com/nexB/scancode-toolkit/releases/download/v${SCANCODE_RELEASE}/scancode-toolkit-${SCANCODE_RELEASE}.tar.bz2
RUN mkdir scancode-toolkit && \
    tar xjvf scancode-toolkit-*.tar.bz2 -C scancode-toolkit --strip-components=1

RUN groupadd -g ${GROUP_ID} scancode-user && \
    useradd -l -u ${USER_ID} -g scancode-user scancode-user && \
    install -d -m 0755 -o scancode-user -g scancode-user /home/scancode-user && \
    chown --changes --silent --no-dereference --recursive ${USER_ID}:${GROUP_ID} /scancode-toolkit

WORKDIR /scancode-toolkit
ENV PATH=$HOME/scancode-toolkit:$PATH
RUN scancode --reindex-licenses

USER scancode-user

ENTRYPOINT [ "scancode" ]
