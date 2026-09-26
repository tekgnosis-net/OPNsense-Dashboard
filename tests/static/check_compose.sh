#!/bin/sh
# Compose invariants (spec §5.3, D10; Review Focus 2): renders in both profile
# modes with .env.example, every service sets TZ, every ${VAR} used by the
# compose file is defined in .env.example, and .env.example explains quoting.
set -eu
cd "$(dirname "$0")/../.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

[ -f .env.example ] || fail ".env.example is missing"
sed 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=/' .env.example >"$tmp/metrics.env"

docker compose --env-file .env.example config -q
docker compose --env-file .env.example config --services | sort >"$tmp/full"
docker compose --env-file "$tmp/metrics.env" config --services | sort >"$tmp/metrics"
printf '%s\n' geoipupdate grafana graylog influxdb mongodb opensearch | diff -u - "$tmp/full" \
    || fail "full mode must run exactly the six services above"
printf '%s\n' grafana influxdb | diff -u - "$tmp/metrics" \
    || fail "metrics-only mode must run only grafana and influxdb"

docker compose --env-file .env.example --profile logs --profile init config --format json >"$tmp/all.json"
missing_tz=$(jq -r '[.services | to_entries[] | select(.value.environment.TZ == null) | .key] | join(" ")' "$tmp/all.json")
[ -z "$missing_tz" ] || fail "every service must set TZ (missing: $missing_tz)"

grep -o '[$]{[A-Z_]*' docker-compose.yaml | cut -c3- | sort -u | while read -r var; do
    grep -q "^$var=" .env.example || fail "\${$var} is used in docker-compose.yaml but missing from .env.example"
done
grep -q "single quotes" .env.example || fail ".env.example must explain quoting values that contain \$"
echo "ok: compose"
