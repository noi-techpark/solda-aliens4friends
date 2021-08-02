# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2021 NOI Techpark <p.moser@noi.bz.it>

#FROM noitechpark/fossology-on-steroids:latest
FROM fossology/fossology:3.9.0

# Path where to open the Fossology webapp...
ARG FOSSOLOGY_REPO_PATH=/repo

COPY ./infrastructure/docker/fossology-entrypoint.sh /fossology/docker-entrypoint.sh

RUN chmod +x /fossology/docker-entrypoint.sh

RUN a2enmod ssl \
  && a2ensite default-ssl \
  && PHP_PATH=$(php --ini | awk '/\/etc\/php.*\/cli$/{print $5}'); \
  phpIni="${PHP_PATH}/../apache2/php.ini"; \
  sed \
    -i.bak \
    -e "s/upload_max_filesize = 700M/upload_max_filesize = 1000M/" \
    -e "s/post_max_size = 701M/post_max_size = 1004M/" \
    -e "s/memory_limit = 702M/memory_limit = 3030M/" \
    $phpIni \
  && cp $phpIni /fossology/php.ini

# Use the root path for the fossology repo endpoint
RUN REPOPATH=$(realpath -sm "${FOSSOLOGY_REPO_PATH}") && \
	REPOPATH_API=$(realpath -sm "${FOSSOLOGY_REPO_PATH}/api") && \
	sed \
	-i.bak \
	-e "s#Alias /repo /usr/local/share/fossology/www/ui#Alias $REPOPATH /usr/local/share/fossology/www/ui/#" \
	-e "s#/repo/api#$REPOPATH_API#g" \
    /etc/apache2/sites-enabled/fossology.conf

ENTRYPOINT ["/fossology/docker-entrypoint.sh"]
