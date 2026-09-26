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
sh tests/run-static.sh    # runs every tests/static/check_* (currently: upstream refs, repo metadata)
```

`tests/run-unit.sh` and `tests/e2e/run.sh` arrive in later phases of v2. On the router (from `docs/troubleshooting.md`):

```sh
sudo /usr/local/bin/telegraf_pfifgw.php       # prints Influx line protocol
sh /usr/local/bin/telegraf_temperature.sh
sudo su -m telegraf -c 'telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d'
```

To run the monitoring stack, use `docker compose up -d`. It serves Grafana on :3000, InfluxDB on :8086, Graylog on :9000, and syslog on UDP :1514.

To provision the router, run `ansible-playbook -i inventory.ini -u root -k playbook.yml` from `opnsense/ansible/`.

## Architecture: three pipelines

### Metrics (Telegraf → InfluxDB v2 → Flux panels)

The OPNsense `os-telegraf` plugin runs with the Network and PF inputs enabled in its GUI. `opnsense/telegraf.d/custom.conf` adds an `inputs.exec` that runs both scripts in `opnsense/bin/` with `data_format = "influx"`. Grafana panels read the results through `${dataSource}`.

- `opnsense/bin/telegraf_pfifgw.php` emits the `interface` and `gateways` measurements. It calls OPNsense's internal PHP APIs (`config.inc`, `interfaces.inc`, `plugins.inc.d/dpinger.inc`, `\OPNsense\Routing\Gateways`), so OPNsense upgrades can break it.
- `telegraf_temperature.sh` emits `temperature` (tag `sensor`, field `degrees`) from `sysctl`.
- The dashboard's other measurements come from built-in Telegraf inputs: `system`, `cpu`, `mem`, `disk`, `processes`, `pf`, `net`.

### Firewall logs (syslog → Graylog → Elasticsearch → Lucene panels)

OPNsense sends syslog to Graylog's Syslog UDP input on port 1514. The content pack `graylog/OPNsense-pack.json` provides:

1. **Extractors.** Six REGEX extractors (IPv4/IPv6 × TCP/UDP/ICMP) match RFC5424 `filterlog` lines. Each has a CSV converter whose `column_header` defines the field names (`interface`, `action`, `src-ip`, `dst-port`, `protocol-name`, …).
2. **Stream.** Stream `OPNsense / filterlog` takes messages where `application_name` CONTAINS `filterlog`.
3. **GeoIP.** The `GeoIP` pipeline rule adds `src-ip-geo-country` using a MaxMind lookup table.
4. **Storage.** Messages go to an index set with prefix `opnsense_filterlog`.
5. **Panels.** The Firewall row and the map panel read it through `${ESdataSource}`.

### Suricata (optional, separate dashboard)

`config/suricata/` holds the pre-26.1 approach (a `custom.yaml` IDS template and a `suricata.conf` tail input) feeding the `suricata` measurement, which `grafana/dashboards/opnsense-suricata.json` displays.

## Cross-file contracts (change both sides together)

A mismatch on any of these produces empty panels, not errors:

- **Plugin output ↔ Flux queries.** Measurement, tag and field names printed by the plugins must match the dashboard's Flux filters (`_measurement == "gateways"`, tags `gateway_name`, `friendlyname`, `ip4_address`, `sensor`, …).
- **Graylog CSV headers ↔ Lucene queries.** The Graylog CSV `column_header` must match the field names in the dashboard's Lucene queries. These fields are hyphenated (`src-ip`, `dst-port`, `protocol-name`).
- **Datasource and bucket portability.** Panels reference `${dataSource}` or `${ESdataSource}`, and Flux queries use `v.defaultBucket`. Keep it that way when re-exporting from Grafana.
- **No upstream download URLs.** `tests/static/check_upstream_refs.sh` fails on any raw-download URL or hosted image belonging to the upstream authors. Downloads point at this repository.

## Editing dashboards

- Dashboards are edited in the Grafana UI and exported as JSON. For hand edits, patch the structure with `jq` or Python and re-validate; don't run regex replacements over the whole file.
- Template defaults reflect the original author's router (`WAN` = `igb0`); `docs/stack.md` tells users to adjust them.
