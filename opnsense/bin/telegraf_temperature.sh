#!/bin/sh
# Telegraf exec input for OPNsense-Dashboard: temperature sensors as InfluxDB
# line protocol, e.g. "temperature,sensor=cpu0 degrees=45.0". Telegraf adds
# the host tag. Sensors are found the way OPNsense core finds them: every
# Kelvin-typed sysctl (format IK), minus thresholds and ACPI trip points.

oids=$(sysctl -aF 2>/dev/null \
    | awk -F ': ' '$2 ~ /^IK/ { print $1 }' \
    | grep -v -e '\._' -e '\.ctt' -e '\.[pt][m012]' -e '\.tjmax' \
    | LC_ALL=C sort)
[ -n "$oids" ] || exit 0

# Splitting the OID list into separate arguments is intended.
# shellcheck disable=SC2086
sysctl -i $oids | awk -F ': ' '
    $2 ~ /^-?[0-9]+(\.[0-9]+)?C$/ {
        sensor = $1
        sub(/^hw\.acpi\.thermal\./, "", sensor)
        sub(/^dev\./, "", sensor)
        sub(/\.temperature$/, "", sensor)
        gsub(/\./, "", sensor)
        degrees = $2
        sub(/C$/, "", degrees)
        printf "temperature,sensor=%s degrees=%s\n", sensor, degrees
    }'
