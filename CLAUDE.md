# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A configuration bundle for monitoring OPNsense firewalls with Grafana, not an application. Maintained here (tekgnosis-net/OPNsense-Dashboard); design records live in `docs/design/` (the v2 spec is `docs/design/2026-09-26-v2-modernization.md`).

| Path | Contents |
|---|---|
| `opnsense/bin/` | Telegraf exec collectors that run **on the firewall** (PHP 8.5, POSIX sh) |
| `opnsense/telegraf.d/custom.conf` | The exec input that runs them |
| `opnsense/ansible/` | Playbook that installs them from the checkout |
| `graylog/OPNsense-pack.json` | Graylog content pack: syslog input, filterlog extractors, stream, GeoIP |
| `graylog/init/graylog-init.sh` | One-shot Graylog setup through the REST API |
| `grafana/dashboards/`, `grafana/provisioning/` | Dashboards and provisioned datasources |
| `docker-compose.yaml`, `.env.example` | Monitoring stack; every setting is an `.env` variable |
| `tests/` | Static checks, unit tests, end-to-end suite |

## Validating changes

```sh
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements-dev.txt   # once
sh tests/run-static.sh    # lint + invariant checks (upstream regressions, contracts, settings)
sh tests/run-unit.sh      # router scripts against OPNsense 26.7.4-shaped stubs / fake sysctl
sh tests/e2e/run.sh       # full stack in Docker with synthetic data; every dashboard query
```

- **End-to-end suite:** compose project `opnsense-dash-test`, loopback ports 13000 (Grafana), 18086 (InfluxDB), 19000 (Graylog), 11514/udp (syslog), about 4 GB RAM, cleans up with `down -v`. `E2E_KEEP=1` leaves the stack running; `E2E_SCREENSHOTS=1` refreshes `docs/images/` and checks in the browser what the firewall tables render, including an IPv6 `$src_ip` drill-down. Never touch other compose projects on the host. `tests/e2e/stack_smoke.sh` is the provisioning-only subset.
- **Router side on real hardware:** run the Ansible playbook and `telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d` on an OPNsense 26.7 router **as root**; unit tests only prove the scripts against stubs.
- **After visual dashboard changes,** look at the `E2E_SCREENSHOTS=1` images: a query can return data while a panel renders nothing.

## Architecture: three pipelines

- **Metrics.** os-telegraf runs as root (Network, PF and default inputs). `custom.conf` runs `opnsense/bin/telegraf_pfifgw.php` (`interface`, `gateways`) and `telegraf_temperature.sh` (`temperature`); data goes to InfluxDB 2.9; dashboards read it with Flux. Telegraf adds the `host` tag; the scripts must not print one.
- **Firewall log.** OPNsense remote syslog (RFC5424, required) → Graylog 7.1 UDP 1514 → six regex extractors whose CSV headers match filterlog 0.9 (`tests/lib/filterlog.py` is the reference layout; ICMPv6 is logged as `ipv6-icmp`) → stream `OPNsense / filterlog` (`application_name` CONTAINS `filterlog`) → GeoIP pipeline (`src-ip-geo-country` only) → OpenSearch 2.19 index set `opnsense_filterlog` → Lucene queries through the OpenSearch plugin.
- **Suricata.** os-telegraf's Intrusion Detection Alerts input → `suricata` measurement → Suricata dashboard.

The plugin uses only these OPNsense internals (core 26.7.4): `get_configured_interface_with_descr`, `get_real_interface`, `legacy_interfaces_details`, `interfaces_primary_address[6]`, `dpinger_status`, `\OPNsense\Routing\Gateways::gatewaysIndexedByName`. When they change, update `tests/php/stubs/` from core source for the target release.

## Contracts (change both sides together; tests enforce them)

- **Plugin output ↔ dashboards.** Measurement, tag and field names **and types** (gateway `status` is a string) must match what the dashboards query. Update `tests/php/cases/*/expected.txt` in the same commit.
- **Extractor CSV headers ↔ Lucene fields.** The dashboards query `interface`, `action`, `src-ip`, `dst-ip`, `dst-port`, `protocol-name`, `src-ip-geo-country`.
- **Datasource and bucket.** Dashboards reference datasources only via `${dataSource}` / `${ESdataSource}` and buckets only via `v.defaultBucket`. Every main-dashboard query filters by Host (`r.host =~ /^${Host:regex}$/` or `source:$Host`).
- **Host identity.** Influx `host` tag = Graylog `source` = the firewall's FQDN; the os-telegraf Hostname option must stay empty.
- **Settings.** Every setting is in `.env.example`, `docker-compose.yaml` and the README Settings table (`check_compose.sh`, `check_settings.py`). Scripts in this repo clamp numeric settings they read.
- **No upstream download URLs.** `check_upstream_refs.sh` fails on any raw-download URL or hosted image of the upstream authors.

## Editing dashboards

- Edit in Grafana 13, export JSON, keep the datasource variables and `v.defaultBucket`, normalize `\r\n` to `\n`. For hand edits, patch the structure with `jq`/Python; don't regex over the whole file.
- `WAN`, `LAN`, `iface` return `device|description`; the variable regex `/^(?<value>[^|]+)\|(?<text>.*)$/` splits them. WAN = description starting with "WAN".
- Rate graphs use `aggregateWindow(..., timeSrc: "_start")` before `derivative()`; the default `_stop` stamps the truncated last window at "now" and draws a false spike at the right edge.
- The Geomap needs the country column: no `reduce` transform on panel 59.
- Firewall flow tables (112 internet = `interface:$WAN`, 113 networks = `NOT interface:$WAN`) nest terms `src-ip` → filters "Kind" → … → terms `dst-port` (`missing: "-"`). Keep a terms aggregation last: the plugin reads leaf buckets as an array and silently drops filters buckets there. Don't filter them on `$dst_port`: its All value `*` drops ICMP. Kind definitions live in `check_dashboards.py` (`KIND`); the events table (114) mirrors them as value mappings on `tcp-flags`.
- `tests/static/check_dashboards.py` holds the invariants (each names the upstream issue it protects).

## Stack

| Service | Version |
|---|---|
| Grafana | 13.2.2 (+ grafana-opensearch-datasource 2.34.4, `GF_PLUGINS_PREINSTALL_SYNC`) |
| InfluxDB | 2.9.1 (2.x only: InfluxDB 3 has no Flux) |
| Graylog | 7.1.9 |
| OpenSearch | 2.19.6 (Graylog 7.1 supports ≤ 2.19) |
| MongoDB | 7.0 (needs AVX; 8.x exits on kernels it reads as 6.19–7.0.13, e.g. Ubuntu 26.04's `7.0.0-N`) |
| geoipupdate | v8.0.0 |

- **Profiles:** `logs` = the Graylog side (default via `COMPOSE_PROFILES`), `init` = `graylog-init`. An explicit `--profile` replaces `COMPOSE_PROFILES`, so pass `--profile logs --profile init` together when you need both.
- **Datasources:** `influxdb-opnsense`, `opensearch-opnsense`. The OpenSearch plugin's health check ("Save & test") fails on wildcard index patterns (grafana/opensearch-datasource#888); prove it with a query, not `/health`.
- **Graylog admin password:** plaintext `GRAYLOG_ADMIN_PASSWORD` in `.env`; the graylog entrypoint derives the SHA-256 (and passes `server` explicitly, since overriding the entrypoint clears the image CMD); `graylog-init` logs in with it.
- **Secrets** ship empty in `.env.example`, so an unedited copy refuses to start (`check_compose.sh` renders with dummy values).
- **`graylog-init`** configures Graylog first and waits for the GeoIP database last (announced; `GEOIP_WAIT_SECONDS`), with the API readiness wait set by `GRAYLOG_INIT_TIMEOUT_SECONDS`. geoipupdate uses `restart: unless-stopped` so it keeps retrying until a new MaxMind key activates.
- **`graylog-init`** handles Graylog 7.1 API quirks: content-pack streams start paused; a second pack install duplicates inputs/streams (check installations first); `PUT /streams/{id}` clears the description if omitted; index-set POSTs reject unknown fields.
- **Playwright** (dashboard capture, screenshots): `mcr.microsoft.com/playwright/python:v1.63.0-noble` has the browsers but not the Python package — install `playwright==1.63.0` at container start. The Grafana UI needs a session from `POST /login`; basic auth only covers the API.
