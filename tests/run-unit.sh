#!/bin/sh
# Runs the router-script unit tests (tests/php, tests/shell).
set -u
cd "$(dirname "$0")/.." || exit 1
status=0
for suite in php shell; do
    [ -f "tests/$suite/run.sh" ] || continue
    sh "tests/$suite/run.sh" || status=1
done
if [ "$status" -eq 0 ]; then
    echo "unit tests: all passed"
else
    echo "unit tests: FAILED" >&2
fi
exit "$status"
