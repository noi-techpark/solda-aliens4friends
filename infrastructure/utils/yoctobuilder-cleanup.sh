#!/bin/bash

set -euo pipefail

BASEPATH=/build/oniro
OLDER_THAN_DAYS=5
DRYRUN=1

((DRYRUN)) && CMD="echo DRYRUN: rm -rf " || CMD="rm -rf"

CANDIDATES=$(
        find "$BASEPATH" \
                -maxdepth 1 \
                -type d \
                -mtime +$OLDER_THAN_DAYS \
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


