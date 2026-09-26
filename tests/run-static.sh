#!/bin/sh
# Runs every static check under tests/static/. Exits non-zero if any fails.
set -u
cd "$(dirname "$0")/.." || exit 1
status=0
for check in tests/static/check_*; do
    case "$check" in
        *.py) runner=python3 ;;
        *.sh) runner=sh ;;
        *) continue ;;
    esac
    echo "== $check"
    "$runner" "$check" || status=1
done
if [ "$status" -eq 0 ]; then
    echo "static checks: all passed"
else
    echo "static checks: FAILED" >&2
fi
exit "$status"
