#!/bin/bash
# FOSSology docker-entrypoint script
# Copyright Siemens AG 2016, fabio.huser@siemens.com
# Copyright TNG Technology Consulting GmbH 2016, maximilian.huber@tngtech.com
#
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty provided the copyright
# notice and this notice are preserved.  This file is offered as-is,
# without any warranty.
#
# Description: startup helper script for the FOSSology Docker container

set -o errexit -o nounset -o pipefail

db_host="${FOSSOLOGY_DB_HOST:-localhost}"
db_name="${FOSSOLOGY_DB_NAME:-fossology}"
db_user="${FOSSOLOGY_DB_USER:-fossy}"
db_password="${FOSSOLOGY_DB_PASSWORD:-fossy}"

# Write configuration
cat <<EOM > /usr/local/etc/fossology/Db.conf
dbname=$db_name;
host=$db_host;
user=$db_user;
password=$db_password;
EOM

sed -i 's/address = .*/address = '"${FOSSOLOGY_SCHEDULER_HOST:-localhost}"'/' \
    /usr/local/etc/fossology/fossology.conf

# Startup DB if needed or wait for external DB
if [[ $db_host == 'localhost' ]]; then
  echo '*****************************************************'
  echo 'WARNING: No database host was set and therefore the'
  echo 'internal database without persistency will be used.'
  echo 'THIS IS NOT RECOMENDED FOR PRODUCTIVE USE!'
  echo '*****************************************************'
  sleep 5
  /etc/init.d/postgresql start
else
  test_for_postgres() {
    PGPASSWORD=$db_password psql -h "$db_host" "$db_name" "$db_user" -c '\l' >/dev/null
    return $?
  }
  until test_for_postgres; do
    >&2 echo "Postgres is unavailable - sleeping"
    sleep 1
  done
fi

# This should solve issue https://github.com/fossology/fossology/issues/1841
is_first_run() {
	RES=$(PGPASSWORD=$db_password psql -h "$db_host" "$db_name" "$db_user" -tc "select count(*) from pg_catalog.pg_tables where tablename = 'license_candidate';")
	test "$(echo "$RES"|bc)" = 0
	return $?
}

# Setup environment
if [[ $# -eq 0 || ($# -eq 1 && "$1" == "scheduler") ]]; then
  if is_first_run; then
  	/usr/local/lib/fossology/fo-postinstall --common --database --licenseref
  fi
fi

### Addition (c) 2021 by Alberto Pianon <pianon@array.eu>

#***************************************************
#*    PATCHING EASYRDF TO IMPORT BIG SPDX FILES    *
#*    (bugfix backport from v1.1.1 to v.0.9.0)     *
#***************************************************
# FIXME We should move this to fossology.dockerfile, since it is a one-time action
cd /usr/local/share/fossology/vendor/easyrdf/easyrdf/lib/EasyRdf/Parser
(patch -p1 << EOT
--- a/RdfXml.php
+++ b/RdfXml.php
@@ -795,14 +795,22 @@
         /* xml parser */
         \$this->initXMLParser();

-        /* parse */
-        if (!xml_parse(\$this->xmlParser, \$data, false)) {
-            \$message = xml_error_string(xml_get_error_code(\$this->xmlParser));
-            throw new EasyRdf_Parser_Exception(
-                'XML error: "' . \$message . '"',
-                xml_get_current_line_number(\$this->xmlParser),
-                xml_get_current_column_number(\$this->xmlParser)
-            );
+        /* split into 1MB chunks, so XML parser can cope */
+        \$chunkSize = 1000000;
+        \$length = strlen(\$data);
+        for (\$pos=0; \$pos < \$length; \$pos += \$chunkSize) {
+            \$chunk = substr(\$data, \$pos, \$chunkSize);
+            \$isLast = (\$pos + \$chunkSize > \$length);
+
+            /* Parse the chunk */
+            if (!xml_parse(\$this->xmlParser, \$chunk, \$isLast)) {
+                \$message = xml_error_string(xml_get_error_code(\$this->xmlParser));
+                throw new Exception(
+                    'XML error: "' . \$message . '"',
+                    xml_get_current_line_number(\$this->xmlParser),
+                    xml_get_current_column_number(\$this->xmlParser)
+                );
+            }
         }

         xml_parser_free(\$this->xmlParser);
EOT
) || true
cd -

echo ""
echo ""
echo "***************************************************"
echo "*    PATCHING REST API to correctly report        *"
echo "*    job status                                   *"
echo "***************************************************"

# the bug is this one:
# https://github.com/fossology/fossology/issues/1800#issuecomment-712919785
# It will be solved by a complete refactoring of job rest API in this PR:
# https://github.com/fossology/fossology/pull/1955
# In the meantime, we need to patch it while keeping the "old" rest API logic

cd /usr/local/share/fossology/www/ui/api/Controllers/
(patch -p1 << EOT
--- a/JobController.php
+++ b/JobController.php
@@ -228,24 +228,25 @@
     \$status = "";
     \$jobqueue = [];

+    \$sql = "SELECT jq_pk from jobqueue WHERE jq_job_fk = \$1;";
+    \$statement = __METHOD__ . ".getJqpk";
+    \$rows = \$this->dbHelper->getDbManager()->getRows(\$sql, [\$job->getId()],
+      \$statement);
     /* Check if the job has no upload like Maintenance job */
     if (empty(\$job->getUploadId())) {
-      \$sql = "SELECT jq_pk, jq_end_bits from jobqueue WHERE jq_job_fk = \$1;";
-      \$statement = __METHOD__ . ".getJqpk";
-      \$rows = \$this->dbHelper->getDbManager()->getRows(\$sql, [\$job->getId()],
-        \$statement);
       if (count(\$rows) > 0) {
-        \$jobqueue[\$rows[0]['jq_pk']] = \$rows[0]['jq_end_bits'];
-      }
-    } else {
-      \$jobqueue = \$jobDao->getAllJobStatus(\$job->getUploadId(),
-        \$job->getUserId(), \$job->getGroupId());
+        \$jobqueue[] = \$rows[0]['jq_pk'];
+      }
+    } else {
+      foreach(\$rows as \$row) {
+        \$jobqueue[] = \$row['jq_pk'];
+      }
     }

     \$job->setEta(\$this->getUploadEtaInSeconds(\$job->getId(),
       \$job->getUploadId()));

-    \$job->setStatus(\$this->getJobStatus(array_keys(\$jobqueue)));
+    \$job->setStatus(\$this->getJobStatus(\$jobqueue));
   }

   /**
EOT
) || true
cd -

if [[ $db_host == 'localhost' ]]; then
	#https://github.com/fossology/fossology/wiki/Configuration-and-Tuning#preparing-postgresql
	mem=$(free --giga | grep Mem | awk '{print $2}')
	su - postgres -c psql <<EOT
	ALTER SYSTEM set shared_buffers = '$(( mem / 4 ))GB';
	ALTER SYSTEM set effective_cache_size = '$(( mem / 2 ))GB';
	ALTER SYSTEM set maintenance_work_mem = '$(( mem * 50 ))MB';
	ALTER SYSTEM set work_mem = '128MB';
	ALTER SYSTEM set fsync = 'on';
	ALTER SYSTEM set full_page_writes = 'off';
	ALTER SYSTEM set log_line_prefix = '%t %h %c';
	ALTER SYSTEM set standard_conforming_strings = 'on';
	ALTER SYSTEM set autovacuum = 'on';
EOT

	/etc/init.d/postgresql stop
	sleep 5
	/etc/init.d/postgresql start
fi

### End addition (c) 2021 by Alberto Pianon <pianon@array.eu>

# Start Fossology
echo
echo 'Fossology initialisation complete; Starting up...'
echo
if [[ $# -eq 0 ]]; then
  /usr/local/share/fossology/scheduler/agent/fo_scheduler \
    --log /dev/stdout \
    --verbose=3 \
    --reset &
  /usr/sbin/apache2ctl -D FOREGROUND
elif [[ $# -eq 1 && "$1" == "scheduler" ]]; then
  exec /usr/local/share/fossology/scheduler/agent/fo_scheduler \
    --log /dev/stdout \
    --verbose=3 \
    --reset
elif [[ $# -eq 1 && "$1" == "web" ]]; then
  exec /usr/sbin/apache2ctl -e info -D FOREGROUND
else
  exec "$@"
fi
