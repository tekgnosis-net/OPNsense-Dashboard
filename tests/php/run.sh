#!/bin/sh
# Runs opnsense/bin/telegraf_pfifgw.php against each fixture in tests/php/cases/
# with stub OPNsense includes, and diffs stdout against expected.txt. Any PHP
# notice, warning or error (sent to stderr) also fails the case.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
script="$root/opnsense/bin/telegraf_pfifgw.php"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
status=0
for case_dir in "$root"/tests/php/cases/*/; do
    name=$(basename "$case_dir")
    php -n -d error_reporting=E_ALL -d display_errors=stderr \
        -d include_path="$root/tests/php/stubs" \
        -d auto_prepend_file="${case_dir}fixture.php" \
        "$script" >"$tmp/$name.out" 2>"$tmp/$name.err"
    rc=$?
    if [ "$rc" -eq 0 ] && [ ! -s "$tmp/$name.err" ] \
        && diff -u "${case_dir}expected.txt" "$tmp/$name.out" >"$tmp/$name.diff"; then
        echo "ok   php/$name"
    else
        echo "FAIL php/$name (exit $rc)"
        cat "$tmp/$name.err" "$tmp/$name.diff"
        status=1
    fi
done
exit "$status"
