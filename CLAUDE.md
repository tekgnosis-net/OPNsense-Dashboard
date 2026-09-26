# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A configuration bundle, not an application: two importable Grafana dashboards plus the pieces that feed them from an OPNsense firewall. Maintained here (tekgnosis-net/OPNsense-Dashboard); the v2 design spec is `docs/design/2026-09-26-v2-modernization.md`.

| Path | Contents |
|---|---|
| `opnsense/bin/` | Telegraf exec scripts that run **on the router** |
| `opnsense/telegraf.d/custom.conf` | The Telegraf exec input that runs them |
| `opnsense/ansible/` | Playbook that provisions the router |
| `graylog/OPNsense-pack.json` | Graylog content pack |
| `grafana/dashboards/` | Dashboard JSON |
| `docker-compose.yaml` | Monitoring host stack |
| `docs/` | Setup guides (`opnsense.md`, `stack.md`), `troubleshooting.md`, design records |
| `tests/` | Checks and tests |

There is no build step. `README.md` lists the monitored panels; `docs/` holds the setup steps.

## Validating changes

```sh
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements-dev.txt   # once, for check_lint.sh
sh tests/run-static.sh    # every tests/static/check_*: lint, upstream refs, repo metadata, router files, content pack
sh tests/run-unit.sh      # PHP plugin vs stubs of OPNsense 26.7.4 functions; temperature script vs a fake sysctl
```

`tests/e2e/run.sh` arrives in a later phase of v2. On the router, **as root** (testing as the `telegraf` user hides root-only failures):

```sh
/usr/local/bin/telegraf_pfifgw.php            # prints Influx line protocol
sh /usr/local/bin/telegraf_temperature.sh
telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d
```

To run the monitoring stack, use `docker compose up -d`. It serves Grafana on :3000, InfluxDB on :8086, Graylog on :9000, and syslog on UDP :1514.

To provision the router, run `ansible-playbook -i inventory.ini -k playbook.yml` from `opnsense/ansible/`. It copies files from the checkout and removes the old sudoers lines and Suricata files.

## Architecture: three pipelines

### Metrics (Telegraf → InfluxDB v2 → Flux panels)

The OPNsense `os-telegraf` plugin runs **as root** ("Run as Root"; no sudo anywhere) with the Network and PF inputs enabled in its GUI. `opnsense/telegraf.d/custom.conf` adds an `inputs.exec` (timeout 10s) that runs both scripts in `opnsense/bin/` with `data_format = "influx"`. Telegraf adds the `host` tag; the scripts must not print one. Grafana panels read the results through `${dataSource}`.

- `opnsense/bin/telegraf_pfifgw.php` emits the `interface` and `gateways` measurements. It uses only `get_configured_interface_with_descr`, `get_real_interface`, `legacy_interfaces_details` (called once), `interfaces_primary_address[6]`, `dpinger_status` and `\OPNsense\Routing\Gateways::gatewaysIndexedByName` (OPNsense core 26.7.4). `tests/php/stubs/` mirrors those signatures; update them from core source when targeting a new release.
- `telegraf_temperature.sh` emits `temperature` (tag `sensor`, field `degrees`), discovering Kelvin-typed sysctls the way OPNsense core does.
- The dashboard's other measurements come from built-in Telegraf inputs: `system`, `cpu`, `mem`, `disk`, `processes`, `pf`, `net`.

### Firewall logs (syslog → Graylog → Elasticsearch → Lucene panels)

OPNsense sends syslog to Graylog's Syslog UDP input on port 1514. The content pack `graylog/OPNsense-pack.json` provides:

1. **Extractors.** Six REGEX extractors (IPv4/IPv6 × TCP/UDP/ICMP) match RFC5424 `filterlog` lines. Each has a CSV converter whose `column_header` defines the field names (`interface`, `action`, `src-ip`, `dst-port`, `protocol-name`, …). The headers follow filterlog 0.9 exactly; `tests/lib/filterlog.py` is the reference layout and `check_content_pack.py` enforces it. ICMPv6 is logged as `ipv6-icmp` (FreeBSD protocol name).
2. **Stream.** Stream `OPNsense / filterlog` takes messages where `application_name` CONTAINS `filterlog`.
3. **GeoIP.** The `GeoIP` pipeline rule adds `src-ip-geo-country` using a MaxMind lookup table.
4. **Storage.** Messages go to an index set with prefix `opnsense_filterlog`.
5. **Panels.** The Firewall row and the map panel read it through `${ESdataSource}`.

### Suricata (optional, separate dashboard)

os-telegraf's built-in "Intrusion Detection Alerts" input tails `/var/log/suricata/eve.json` into the `suricata` measurement (needs Run as Root), which `grafana/dashboards/opnsense-suricata.json` displays. OPNsense 26.1 removed the `custom.yaml` hook older versions used.

## Cross-file contracts (change both sides together)

A mismatch on any of these produces empty panels, not errors:

- **Plugin output ↔ Flux queries.** Measurement, tag and field names **and types** printed by the plugins must match the dashboard's Flux filters (`_measurement == "gateways"`, tags `gateway_name`, `friendlyname`, `ip4_address`, `sensor`, …; gateway `status` is a string). Update `tests/php/cases/*/expected.txt` in the same commit as any output change.
- **Graylog CSV headers ↔ Lucene queries.** The Graylog CSV `column_header` must match the field names in the dashboard's Lucene queries. These fields are hyphenated (`src-ip`, `dst-port`, `protocol-name`).
- **Datasource and bucket portability.** Panels reference `${dataSource}` or `${ESdataSource}`, and Flux queries use `v.defaultBucket`. Keep it that way when re-exporting from Grafana.
- **No upstream download URLs.** `tests/static/check_upstream_refs.sh` fails on any raw-download URL or hosted image belonging to the upstream authors. Downloads point at this repository.

## Editing dashboards

- Dashboards are edited in the Grafana UI and exported as JSON. For hand edits, patch the structure with `jq` or Python and re-validate; don't run regex replacements over the whole file.
- Template defaults reflect the original author's router (`WAN` = `igb0`); `docs/stack.md` tells users to adjust them.
