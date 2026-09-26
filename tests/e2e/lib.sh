# Shared helpers for tests/e2e/*.sh (POSIX sh; source, do not run). Scripts in
# tests/e2e source it directly; from elsewhere set E2E_DIR first.
# shellcheck shell=sh
E2E_DIR=${E2E_DIR:-$(cd "$(dirname "$0")" && pwd)}
ROOT=$(cd "$E2E_DIR/../.." && pwd)
WORK="$E2E_DIR/.work"
PROJECT=${E2E_PROJECT:-opnsense-dash-test}
E2E_ENV_FILE=${E2E_ENV_FILE:-$E2E_DIR/e2e.env}
# MaxMind's public GeoLite2-Country test database, pinned by commit and checksum.
MMDB_URL=https://raw.githubusercontent.com/maxmind/MaxMind-DB/000a8df991543651637fd9c16b7a7f8480370514/test-data/GeoLite2-Country-Test.mmdb
MMDB_SHA256=6996ce679243c7f719b901ebe3b490048af2fb5965163f083857533841154fd8
mkdir -p "$WORK"

# shellcheck disable=SC1090
. "$E2E_ENV_FILE"
# Required from the env file; fail early with a clear message.
GRAFANA_PORT=${GRAFANA_PORT:?set GRAFANA_PORT in $E2E_ENV_FILE}
INFLUXDB_PORT=${INFLUXDB_PORT:?set INFLUXDB_PORT in $E2E_ENV_FILE}
GRAYLOG_PORT=${GRAYLOG_PORT:?set GRAYLOG_PORT in $E2E_ENV_FILE}
GRAFANA_URL="http://127.0.0.1:$GRAFANA_PORT"
GRAYLOG_URL="http://127.0.0.1:$GRAYLOG_PORT"
INFLUXDB_URL="http://127.0.0.1:$INFLUXDB_PORT"
export GRAFANA_URL GRAYLOG_URL INFLUXDB_URL GRAFANA_ADMIN_USER GRAFANA_ADMIN_PASSWORD \
    INFLUXDB_ORG INFLUXDB_BUCKET INFLUXDB_ADMIN_TOKEN GRAYLOG_ADMIN_PASSWORD SYSLOG_PORT ROOT

fail() { echo "E2E FAIL: $*" >&2; exit 1; }
say() { echo "== $*"; }

compose() {
    if [ -n "${E2E_EXTRA_COMPOSE:-}" ]; then
        set -- -f "$E2E_EXTRA_COMPOSE" "$@"
    fi
    docker compose -p "$PROJECT" --project-directory "$ROOT" --env-file "$E2E_ENV_FILE" \
        -f "$ROOT/docker-compose.yaml" -f "$E2E_DIR/compose.e2e.yaml" "$@"
}

wait_for() { # SECONDS DESCRIPTION COMMAND...
    limit=$1 what=$2
    shift 2
    waited=0
    until "$@" >/dev/null 2>&1; do
        [ "$waited" -lt "$limit" ] || fail "timed out after ${limit}s waiting for $what"
        sleep 3
        waited=$((waited + 3))
    done
}

fetch_mmdb() {
    [ -s "$WORK/GeoLite2-Country.mmdb" ] || curl -fsSL -o "$WORK/GeoLite2-Country.mmdb" "$MMDB_URL"
    echo "$MMDB_SHA256  $WORK/GeoLite2-Country.mmdb" | sha256sum -c - >/dev/null \
        || fail "MaxMind test database checksum mismatch"
}

install_mmdb() {
    docker run --rm -v "${PROJECT}_geoip_data:/geoip" -v "$WORK:/src:ro" "$INIT_IMAGE" \
        cp /src/GeoLite2-Country.mmdb /geoip/GeoLite2-Country.mmdb
}

graylog_api() { # PATH -> JSON
    curl -fsS -u "admin:$GRAYLOG_ADMIN_PASSWORD" -H 'X-Requested-By: e2e' "$GRAYLOG_URL/api$1"
}

grafana_api() { # PATH -> JSON
    curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" "$GRAFANA_URL/api$1"
}

teardown() {
    if [ "${E2E_KEEP:-0}" = 1 ]; then
        say "E2E_KEEP=1: leaving project $PROJECT running"
        return 0
    fi
    # Name both profiles: an explicit --profile replaces COMPOSE_PROFILES.
    compose --profile logs --profile init down -v --remove-orphans >/dev/null 2>&1 || true
}
