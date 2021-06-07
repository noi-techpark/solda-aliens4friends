# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 NOI Techpark <p.moser@noi.bz.it>

FROM openjdk:11-jre-slim

RUN apt-get update && apt-get -y install openjdk-11-jre-headless

RUN wget -P /usr/local/lib \
    https://github.com/spdx/tools/releases/download/v2.2.5/spdx-tools-2.2.5-jar-with-dependencies.jar

CMD [ "java",  "-jar", "/usr/local/lib/spdx-tools-2.2.5-jar-with-dependencies.jar" ]
