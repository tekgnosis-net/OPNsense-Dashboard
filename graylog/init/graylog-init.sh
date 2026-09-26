#!/bin/sh
# One-shot Graylog setup for OPNsense-Dashboard (spec §5.3). Safe to re-run:
# every step checks the current state first. Never prints secrets.
#   docker compose run --rm graylog-init
# Env (set by docker-compose.yaml): GRAYLOG_URL, GRAYLOG_ADMIN_USER,
# GRAYLOG_ADMIN_PASSWORD, CONTENT_PACK, GEOIP_FILE, GEOIP_WAIT_SECONDS (0-3600),
# GRAYLOG_INDEX_ROTATION (ISO-8601 period), GRAYLOG_INDEX_MAX_COUNT (1-3650).
set -eu
# shellcheck disable=SC3040  # busybox ash (alpine) supports pipefail
set -o pipefail

: "${GRAYLOG_URL:=http://graylog:9000}"
: "${GRAYLOG_ADMIN_USER:=admin}"
: "${GRAYLOG_ADMIN_PASSWORD:?GRAYLOG_ADMIN_PASSWORD is required}"
: "${CONTENT_PACK:=/init/OPNsense-pack.json}"
: "${GEOIP_FILE:=/geoip/GeoLite2-Country.mmdb}"
INDEX_PREFIX=opnsense_filterlog
STREAM_TITLE="OPNsense / filterlog"

log() { echo "graylog-init: $*"; }

clamp() { # VALUE MIN MAX DEFAULT
    case "$1" in '' | *[!0-9]*) echo "$4"; return ;; esac
    if [ "$1" -lt "$2" ]; then echo "$2"; elif [ "$1" -gt "$3" ]; then echo "$3"; else echo "$1"; fi
}
GEOIP_WAIT=$(clamp "${GEOIP_WAIT_SECONDS:-600}" 0 3600 600)
MAX_INDICES=$(clamp "${GRAYLOG_INDEX_MAX_COUNT:-30}" 1 3650 30)
ROTATION=${GRAYLOG_INDEX_ROTATION:-P1D}
case "$ROTATION" in
    P*) ;;
    *) log "GRAYLOG_INDEX_ROTATION must be an ISO-8601 period such as P1D; using P1D"; ROTATION=P1D ;;
esac

api() { # METHOD PATH [BODY | @FILE] -> response body; fails on HTTP errors
    method=$1 path=$2 body=${3-}
    if [ -n "$body" ]; then
        curl -fsS -u "$GRAYLOG_ADMIN_USER:$GRAYLOG_ADMIN_PASSWORD" -X "$method" \
            -H 'X-Requested-By: graylog-init' -H 'Content-Type: application/json' \
            --data-binary "$body" "$GRAYLOG_URL/api$path"
    else
        curl -fsS -u "$GRAYLOG_ADMIN_USER:$GRAYLOG_ADMIN_PASSWORD" -X "$method" \
            -H 'X-Requested-By: graylog-init' "$GRAYLOG_URL/api$path"
    fi
}

log "waiting for Graylog at $GRAYLOG_URL"
tries=0
until [ "$(curl -fsS "$GRAYLOG_URL/api/system/lbstatus" 2>/dev/null)" = ALIVE ]; do
    tries=$((tries + 1))
    [ "$tries" -le 100 ] || { log "Graylog did not become ready within 300s"; exit 1; }
    sleep 3
done
api GET /system >/dev/null || { log "cannot log in as $GRAYLOG_ADMIN_USER: check GRAYLOG_ADMIN_PASSWORD"; exit 1; }

# 1. GeoIP database (new MaxMind keys can take minutes to activate).
waited=0
while [ ! -s "$GEOIP_FILE" ] && [ "$waited" -lt "$GEOIP_WAIT" ]; do
    sleep 5
    waited=$((waited + 5))
done
if [ -s "$GEOIP_FILE" ]; then
    log "GeoIP database present"
else
    log "WARNING: $GEOIP_FILE not found after ${GEOIP_WAIT}s; the map stays empty until geoipupdate downloads it (no restart needed)"
fi

# 2. Index set for the firewall log.
index_set_id=$(api GET /system/indices/index_sets \
    | jq -r --arg p "$INDEX_PREFIX" '[.index_sets[] | select(.index_prefix == $p) | .id][0] // empty')
if [ -z "$index_set_id" ]; then
    body=$(jq -n --arg p "$INDEX_PREFIX" --arg rot "$ROTATION" --argjson max "$MAX_INDICES" '{
        title: "OPNsense / filterlog", description: "OPNsense firewall log (filterlog)",
        index_prefix: $p, shards: 1, replicas: 0, index_analyzer: "standard",
        index_optimization_max_num_segments: 1, index_optimization_disabled: false,
        field_type_refresh_interval: 5000, writable: true, use_legacy_rotation: true,
        rotation_strategy_class: "org.graylog2.indexer.rotation.strategies.TimeBasedRotationStrategy",
        rotation_strategy: {
            type: "org.graylog2.indexer.rotation.strategies.TimeBasedRotationStrategyConfig",
            rotation_period: $rot, rotate_empty_index_set: false},
        retention_strategy_class: "org.graylog2.indexer.retention.strategies.DeletionRetentionStrategy",
        retention_strategy: {
            type: "org.graylog2.indexer.retention.strategies.DeletionRetentionStrategyConfig",
            max_number_of_indices: $max}}')
    index_set_id=$(api POST /system/indices/index_sets "$body" | jq -r .id)
    log "created index set $INDEX_PREFIX (rotate $ROTATION, keep $MAX_INDICES)"
else
    log "index set $INDEX_PREFIX already exists"
fi

# 3. Content pack: upload once, install once (a second install duplicates inputs).
pack_id=$(jq -r .id "$CONTENT_PACK")
pack_rev=$(jq -r .rev "$CONTENT_PACK")
uploaded=$(api GET /system/content_packs \
    | jq --arg id "$pack_id" --argjson rev "$pack_rev" '[.content_packs[] | select(.id == $id and .rev == $rev)] | length')
if [ "$uploaded" -eq 0 ]; then
    api POST /system/content_packs "@$CONTENT_PACK" >/dev/null
    log "uploaded content pack rev $pack_rev"
fi
installs=$(api GET "/system/content_packs/$pack_id/installations" | jq .total)
if [ "$installs" -eq 0 ]; then
    api POST "/system/content_packs/$pack_id/$pack_rev/installations" \
        '{"entity":{"parameters":{},"comment":"graylog-init"}}' >/dev/null
    log "installed content pack rev $pack_rev"
else
    log "content pack already installed"
fi

# 4. Stream: write to our index set, not the default one, and run it
#    (streams from content packs start paused).
stream_id=$(api GET /streams \
    | jq -r --arg t "$STREAM_TITLE" '[.streams[] | select(.title == $t) | .id][0] // empty')
[ -n "$stream_id" ] || { log "stream '$STREAM_TITLE' not found after installing the content pack"; exit 1; }
stream=$(api GET "/streams/$stream_id")
if [ "$(echo "$stream" | jq -r .index_set_id)" != "$index_set_id" ]; then
    api PUT "/streams/$stream_id" "$(jq -n --arg id "$index_set_id" \
        '{description: "OPNsense filter logs", index_set_id: $id, remove_matches_from_default_stream: true}')" >/dev/null
    log "stream now writes to $INDEX_PREFIX"
fi
if [ "$(echo "$stream" | jq -r .disabled)" = true ]; then
    api POST "/streams/$stream_id/resume" >/dev/null
    log "stream resumed"
fi

# 5. GeoIP pipeline connected to the stream (the pack normally does this).
pipeline_id=$(api GET /system/pipelines/pipeline \
    | jq -r '[.[] | select(.title == "GeoIP") | .id][0] // empty')
[ -n "$pipeline_id" ] || { log "GeoIP pipeline not found"; exit 1; }
connections=$(api GET /system/pipelines/connections)
if ! echo "$connections" | jq -e --arg s "$stream_id" --arg p "$pipeline_id" \
        'any(.[]; .stream_id == $s and (.pipeline_ids | index($p)))' >/dev/null; then
    ids=$(echo "$connections" | jq -c --arg s "$stream_id" --arg p "$pipeline_id" \
        '[.[] | select(.stream_id == $s) | .pipeline_ids[]] + [$p] | unique')
    api POST /system/pipelines/connections/to_stream \
        "$(jq -n --arg s "$stream_id" --argjson ids "$ids" '{stream_id: $s, pipeline_ids: $ids}')" >/dev/null
    log "connected the GeoIP pipeline to the stream"
fi

# 6. Processing order: extractors (filter chain), then stream rules, then
#    pipelines (the GeoIP pipeline hangs off the stream).
want='["org.graylog2.messageprocessors.MessageFilterChainProcessor","org.graylog2.messageprocessors.StreamMatcherFilterProcessor","org.graylog.plugins.pipelineprocessor.processors.PipelineInterpreter"]'
config=$(api GET /system/messageprocessors/config)
if echo "$config" | jq -e --argjson want "$want" '
        ([.processor_order[].class_name | select(. as $c | $want | index($c))] == $want)
        and ([.disabled_processors[] | select(. as $c | $want | index($c))] | length == 0)' >/dev/null; then
    log "message processor order already correct"
else
    body=$(echo "$config" | jq --argjson want "$want" '
        .processor_order as $all
        | {processor_order: ([$all[] | select(.class_name as $c | $want | index($c) | not)]
                             + [$want[] as $c | $all[] | select(.class_name == $c)]),
           disabled_processors: [.disabled_processors[] | select(. as $c | $want | index($c) | not)]}')
    api PUT /system/messageprocessors/config "$body" >/dev/null
    log "message processors set to: filter chain, stream rules, pipelines"
fi

log "done"
