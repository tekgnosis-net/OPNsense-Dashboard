#!/bin/sh
# Runs opnsense/bin/telegraf_temperature.sh against each fixture in
# tests/shell/cases/ with a fake sysctl on PATH and diffs the output.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
script="$root/opnsense/bin/telegraf_temperature.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
status=0
for case_dir in "$root"/tests/shell/cases/*/; do
    name=$(basename "$case_dir")
    PATH="$root/tests/shell/bin:$PATH" SYSCTL_CASE="$case_dir" \
        sh "$script" >"$tmp/$name.out" 2>"$tmp/$name.err"
    rc=$?
    if [ "$rc" -eq 0 ] && [ ! -s "$tmp/$name.err" ] \
        && diff -u "${case_dir}expected.txt" "$tmp/$name.out" >"$tmp/$name.diff"; then
        echo "ok   shell/$name"
    else
        echo "FAIL shell/$name (exit $rc)"
        cat "$tmp/$name.err" "$tmp/$name.diff"
        status=1
    fi
done
exit "$status"
