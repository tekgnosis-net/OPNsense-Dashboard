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

# Secrets ship empty so an unedited .env refuses to start instead of
# exposing known credentials (final review #1).
SECRETS="GRAFANA_ADMIN_PASSWORD INFLUXDB_ADMIN_PASSWORD INFLUXDB_ADMIN_TOKEN GRAYLOG_ADMIN_PASSWORD GRAYLOG_PASSWORD_SECRET"
for var in $SECRETS; do
    grep -qx "$var=" .env.example || fail "$var must be empty in .env.example (no working default secret)"
done
if docker compose --env-file .env.example config -q 2>"$tmp/err"; then
    fail "an unedited .env.example must not render (secrets are required)"
fi
grep -q "in .env" "$tmp/err" || fail "compose must name the missing secret: $(cat "$tmp/err")"

# Render checks use .env.example with dummy secrets filled in.
cp .env.example "$tmp/full.env"
for var in $SECRETS; do
    sed -i "s/^$var=\$/$var=dummy-$var/" "$tmp/full.env"
done
sed 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=/' "$tmp/full.env" >"$tmp/metrics.env"

docker compose --env-file "$tmp/full.env" config -q
docker compose --env-file "$tmp/full.env" config --services | sort >"$tmp/full"
docker compose --env-file "$tmp/metrics.env" config --services | sort >"$tmp/metrics"
printf '%s\n' geoipupdate grafana graylog influxdb mongodb opensearch | diff -u - "$tmp/full" \
    || fail "full mode must run exactly the six services above"
printf '%s\n' grafana influxdb | diff -u - "$tmp/metrics" \
    || fail "metrics-only mode must run only grafana and influxdb"

docker compose --env-file "$tmp/full.env" --profile logs --profile init config --format json >"$tmp/all.json"
missing_tz=$(jq -r '[.services | to_entries[] | select(.value.environment.TZ == null) | .key] | join(" ")' "$tmp/all.json")
[ -z "$missing_tz" ] || fail "every service must set TZ (missing: $missing_tz)"

grep -o '[$]{[A-Z_]*' docker-compose.yaml | cut -c3- | sort -u | while read -r var; do
    grep -q "^$var=" .env.example || fail "\${$var} is used in docker-compose.yaml but missing from .env.example"
done
# MongoDB 8.x refuses to start on kernels it reads as 6.19-7.0.13, which includes
# Ubuntu 26.04's "7.0.0-N" kernels even when the upstream base is 7.0.14; 7.0 is
# unaffected and supported by Graylog 7.1.
grep -qx 'MONGO_IMAGE=mongo:7.0' .env.example || fail "MONGO_IMAGE in .env.example must default to mongo:7.0"
grep -q 'image: [$]{MONGO_IMAGE:-mongo:7.0}' docker-compose.yaml || fail "docker-compose.yaml must default MONGO_IMAGE to mongo:7.0"
[ "$(jq -r '.services.mongodb.image' "$tmp/all.json")" = "mongo:7.0" ] || fail "mongodb must render as mongo:7.0"
# geoipupdate must keep retrying until a new MaxMind key activates (final review #2).
[ "$(jq -r '.services.geoipupdate.restart' "$tmp/all.json")" = "unless-stopped" ] \
    || fail "geoipupdate must use restart: unless-stopped"
# graylog-init's readiness wait is a setting, not a constant (final review #11).
grep -q 'GRAYLOG_INIT_TIMEOUT_SECONDS' graylog/init/graylog-init.sh \
    || fail "graylog-init.sh must read GRAYLOG_INIT_TIMEOUT_SECONDS"
grep -q "single quotes" .env.example || fail ".env.example must explain quoting values that contain \$"
echo "ok: compose"
