#!/bin/sh
# Full end-to-end suite (spec §6.4). Needs docker, curl, jq, python3 and about
# 4 GB free RAM; uses project opnsense-dash-test on loopback ports only.
#   sh tests/e2e/run.sh                     full stack, then metrics-only
#   E2E_SCREENSHOTS=1 sh tests/e2e/run.sh   also refresh docs/images/*.png
set -eu
# shellcheck source=tests/e2e/lib.sh
. "$(dirname "$0")/lib.sh"
trap teardown EXIT
PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright/python:v1.63.0-noble
PLAYWRIGHT_VERSION=1.63.0

E2E_KEEP=1 sh "$E2E_DIR/stack_smoke.sh"

say "seeding InfluxDB and sending syslog"
python3 "$E2E_DIR/seed_influx.py" history
expected=$(python3 "$E2E_DIR/send_syslog.py")
total=$(echo "$expected" | jq .total)
os_query() {
    compose exec -T opensearch curl -fsS -H 'Content-Type: application/json' \
        "http://localhost:9200/opnsense_filterlog_*/_search" -d "$1"
}
hits() { os_query "$1" | jq .hits.total.value; }
indexed() { [ "$(hits '{"size":0,"track_total_hits":true}')" -ge "$total" ]; }
wait_for 180 "$total firewall messages in OpenSearch" indexed

say "firewall log fields"
aggs=$(os_query '{"size":0,"aggs":{"p":{"terms":{"field":"protocol-name"}},"c":{"terms":{"field":"src-ip-geo-country"}}}}')
[ "$(echo "$aggs" | jq -c '[.aggregations.p.buckets[].key] | sort')" = '["icmp","ipv6-icmp","tcp","udp"]' ] \
    || fail "protocol-name values: $(echo "$aggs" | jq -c .aggregations.p)"
[ "$(echo "$aggs" | jq -c '[.aggregations.c.buckets[].key] | sort')" = '["GB","JP","KR","SE","US"]' ] \
    || fail "src-ip-geo-country values: $(echo "$aggs" | jq -c .aggregations.c)"
for field in rid interface action src-ip dst-ip; do
    n=$(hits "{\"size\":0,\"track_total_hits\":true,\"query\":{\"bool\":{\"must_not\":{\"exists\":{\"field\":\"$field\"}}}}}")
    [ "$n" = 0 ] || fail "$n firewall messages lack $field"
done
n=$(hits '{"size":0,"track_total_hits":true,"query":{"bool":{"filter":{"terms":{"protocol-name":["tcp","udp"]}},"must_not":{"exists":{"field":"dst-port"}}}}}')
[ "$n" = 0 ] || fail "$n TCP/UDP messages lack dst-port"

say "every dashboard query (full stack)"
E2E_EXPECTED=$expected python3 "$E2E_DIR/query_dashboards.py" full

if [ "${E2E_SCREENSHOTS:-0}" = 1 ]; then
    say "screenshots into docs/images"
    mkdir -p "$ROOT/docs/images"
    python3 "$E2E_DIR/seed_influx.py" live 150 &
    seeder=$!
    # The image ships browsers but not the Python package; install the matching version.
    docker run --rm --network "${PROJECT}_default" --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$ROOT/docs/images:/out" -v "$E2E_DIR/screenshots.py:/screenshots.py:ro" "$PLAYWRIGHT_IMAGE" \
        sh -c 'python -m pip install -q --user --break-system-packages "playwright==$0" >/dev/null 2>&1 \
               && python /screenshots.py "$@"' \
        "$PLAYWRIGHT_VERSION" http://grafana:3000 "$GRAFANA_ADMIN_USER" "$GRAFANA_ADMIN_PASSWORD" /out
    wait "$seeder"
fi

say "metrics-only mode"
keep=${E2E_KEEP:-0}
E2E_KEEP=0
teardown
E2E_KEEP=$keep
sed 's/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=/' "$E2E_DIR/e2e.env" >"$WORK/metrics.env"
E2E_ENV_FILE="$WORK/metrics.env"
compose up -d --wait --wait-timeout 300 || fail "metrics-only stack did not start"
[ "$(compose ps --services | sort | tr '\n' ' ')" = "grafana influxdb " ] \
    || fail "metrics-only mode runs: $(compose ps --services | tr '\n' ' ')"
python3 "$E2E_DIR/seed_influx.py" history
python3 "$E2E_DIR/query_dashboards.py" metrics-only
say "end-to-end suite passed"
