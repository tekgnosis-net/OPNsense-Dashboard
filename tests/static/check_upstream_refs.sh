#!/bin/sh
# Fails if any tracked file still points at the upstream authors' download
# URLs or image hosts. Credits may name the upstream projects (NOTICE, README,
# CHANGELOG) and the design records under docs/design/ quote them as evidence.
set -eu
cd "$(dirname "$0")/../.."
pattern='raw\.githubusercontent\.com/(bsmithio|Bsmith101)|github\.com/Bsmith101|bsmithio\.com|nuuls\.com'
if git grep -n -I -E "$pattern" -- . ':!docs/design/' ':!tests/static/check_upstream_refs.sh'; then
    echo "FAIL: upstream download URLs or image hosts found (listed above)" >&2
    exit 1
fi
echo "ok: no upstream download URLs or image hosts"
