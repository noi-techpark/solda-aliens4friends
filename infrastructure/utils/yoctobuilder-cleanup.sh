#!/bin/bash

if [ $# -ne 3 ]; then
	echo "Usage: yoctobuilder-cleanup.sh BASEPATH OLDER_THAN_DAYS [dryrun|delete]"
	exit 1
fi

if [ "$3" = "dryrun" ]; then
	CMD="echo DRYRUN: rm -rf "
else
	CMD="rm -rf"
fi

set -euo pipefail

BASEPATH=$1
OLDER_THAN_DAYS=$2

CANDIDATES=$(
	find "$BASEPATH" \
		-maxdepth 1 \
		-type d \
		-mtime +"$OLDER_THAN_DAYS" \
		-regextype posix-extended \
		-regex '.*-.*-[0-9]+-[a-z0-9]{8}'
)

for C in $CANDIDATES; do
	# ignore double-quote warning
	# shellcheck disable=SC2086
	find "$C" \
		-maxdepth 1 \
		-type d \
		-name 'build-*-*' \
		-exec $CMD "{}" \;
done

echo "READY."
exit 0
