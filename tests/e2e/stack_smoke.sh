#!/bin/sh
# End-to-end smoke test of the provisioned stack (spec §5.3; Review Focus 2, 3, 5).
# Needs docker, curl, jq and about 4 GB free RAM. E2E_KEEP=1 leaves it running.
set -eu
# shellcheck source=tests/e2e/lib.sh
. "$(dirname "$0")/lib.sh"
trap teardown EXIT

say "clean start of project $PROJECT"
keep=${E2E_KEEP:-0}
E2E_KEEP=0
teardown
E2E_KEEP=$keep
fetch_mmdb
compose up -d --wait --wait-timeout 600 || fail "stack did not become healthy"

say "graylog-init before the GeoIP database exists (must warn, not fail)"
out=$(compose run --rm -e GEOIP_WAIT_SECONDS=3 graylog-init) || fail "graylog-init failed on its first run"
echo "$out"
echo "$out" | grep -q "WARNING: .*GeoLite2-Country.mmdb not found" \
    || fail "graylog-init did not warn about the missing GeoIP database"

say "GeoIP lookups recover once the database appears, without a restart"
install_mmdb
geo_gb() {
    graylog_api "/system/lookup/tables/geoip/query?key=2.125.160.216" \
        | jq -e '[.. | .iso_code? // empty] | index("GB") != null'
}
wait_for 180 "GeoIP lookup of 2.125.160.216 to return GB" geo_gb

say "graylog-init again: nothing duplicated"
compose run --rm graylog-init >/dev/null || fail "graylog-init failed on its second run"
count() { graylog_api "$1" | jq -r "$2"; }
[ "$(count /system/inputs '[.inputs[] | select(.title == "Syslog UDP")] | length')" = 1 ] \
    || fail "expected exactly one Syslog UDP input"
[ "$(count /streams '[.streams[] | select(.title == "OPNsense / filterlog")] | length')" = 1 ] \
    || fail "expected exactly one OPNsense / filterlog stream"
[ "$(count /system/indices/index_sets '[.index_sets[] | select(.index_prefix == "opnsense_filterlog")] | length')" = 1 ] \
    || fail "expected exactly one opnsense_filterlog index set"
pack_id=$(jq -r .id "$ROOT/graylog/OPNsense-pack.json")
[ "$(count "/system/content_packs/$pack_id/installations" '.total')" = 1 ] \
    || fail "expected exactly one content pack installation"
[ "$(count /streams '[.streams[] | select(.title == "OPNsense / filterlog") | .disabled][0]')" = false ] \
    || fail "the filterlog stream is paused"
order=$(count /system/messageprocessors/config \
    '[.processor_order[].class_name | select(test("MessageFilterChain|StreamMatcher|PipelineInterpreter")) | split(".") | last] | join(",")')
[ "$order" = "MessageFilterChainProcessor,StreamMatcherFilterProcessor,PipelineInterpreter" ] \
    || fail "message processor order is $order"

say "second compose up on the existing volumes"
compose up -d --wait --wait-timeout 300 || fail "second compose up failed"

say "Grafana: \$ password, datasources, dashboards"
grafana_api /user >/dev/null || fail "Grafana rejected the single-quoted \$ admin password"
grafana_api /datasources/uid/influxdb-opnsense/health | jq -e '.status == "OK"' >/dev/null \
    || fail "datasource influxdb-opnsense is not healthy"
# The OpenSearch plugin's health check cannot resolve wildcard index patterns
# (grafana/opensearch-datasource#888), so prove the datasource with a query.
curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" -H 'Content-Type: application/json' \
    "$GRAFANA_URL/api/ds/query" -d '{"from":"now-1h","to":"now","queries":[{"refId":"A",
      "datasource":{"type":"grafana-opensearch-datasource","uid":"opensearch-opnsense"},
      "queryType":"lucene","luceneQueryType":"Metric","query":"*","metrics":[{"id":"1","type":"count"}],
      "bucketAggs":[{"id":"2","type":"date_histogram","field":"timestamp","settings":{"interval":"auto"}}]}]}' \
    | jq -e '.results.A.error == null' >/dev/null || fail "datasource opensearch-opnsense cannot query"
for uid in suTmk8c7k 94raP_-7z; do
    grafana_api "/dashboards/uid/$uid" >/dev/null || fail "dashboard $uid is not provisioned"
done
say "stack smoke test passed"
