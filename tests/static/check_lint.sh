#!/bin/sh
# Syntax and lint for every tracked JSON, PHP, shell and YAML file.
# Needs jq, php, shellcheck and, from tests/requirements-dev.txt,
# ansible-playbook, ansible-lint and yamllint (a .venv/ in the repo root is
# picked up automatically).
set -u
cd "$(dirname "$0")/../.." || exit 1
[ -d .venv/bin ] && PATH="$PWD/.venv/bin:$PATH"
status=0
fail() { echo "FAIL: $*" >&2; status=1; }

for f in $(git ls-files '*.json'); do
    jq empty "$f" 2>/dev/null || fail "invalid JSON: $f"
done
for f in $(git ls-files '*.php' '*.inc'); do
    php -n -l "$f" >/dev/null || fail "php -l: $f"
done
# shellcheck disable=SC2046
shellcheck -s sh $(git ls-files '*.sh') tests/shell/bin/sysctl || fail shellcheck
# shellcheck disable=SC2046
yamllint -s $(git ls-files '*.yml' '*.yaml' '.yamllint') || fail yamllint
(cd opnsense/ansible && ansible-playbook -i inventory.ini --syntax-check playbook.yml >/dev/null) \
    || fail "ansible-playbook --syntax-check"
(cd opnsense/ansible && ansible-lint --offline playbook.yml) || fail ansible-lint

[ "$status" -eq 0 ] && echo "ok: lint"
exit "$status"
