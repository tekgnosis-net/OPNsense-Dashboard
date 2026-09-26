# Changelog

All notable changes to this project are documented here. The project uses
[Semantic Versioning](https://semver.org/). Issue numbers (#n) refer to the
upstream repository bsmithio/OPNsense-Dashboard, where they were reported.

## [2.0.1] - 2026-09-27

### Fixed
- MongoDB now defaults to 7.0 (`MONGO_IMAGE=mongo:7.0`). MongoDB 8.x refuses to
  start on kernels it reads as 6.19–7.0.13, which includes Ubuntu 26.04's
  `7.0.0-N` kernels (MongoDB SERVER-121912); Graylog 7.1 supports 7.x.
- Documented the minimum password lengths the services enforce at first start:
  InfluxDB admin password 8–72 characters, Graylog password secret at least 16.

## [2.0.0] - 2026-09-27

First release as an independent project; see [NOTICE](NOTICE) for its
history. The monitoring stack needs a fresh install: data from the 2023
stack (Graylog 5, Elasticsearch 7.10, Grafana 9) is not carried over.

### Router (OPNsense 26.7)
- `telegraf_pfifgw.php` rewritten for OPNsense 24.1 and later:
  - it uses `dpinger_status()`, the MVC `Gateways` model and a single
    `ifconfig` parse;
  - it fixes the fatal `get_interfaces_info()` (#57, #61, #78) and
    `convert_seconds_to_hms()` (#82) errors;
  - gateways no longer always show as "Unmonitored" (#39);
  - delay and loss are no longer reported as zero before dpinger has data;
  - tag values with spaces or commas no longer break the output.
  Degraded gateways report status 2.
- Telegraf runs as root ("Run as Root"), and sudoers is no longer edited
  (#1, #13, #63, #89).
- Suricata alerts now come from os-telegraf's Intrusion Detection Alerts
  input; OPNsense 26.1 removed the `custom.yaml` hook (#88).
- Temperature sensors are discovered the way OPNsense core does it: Intel,
  AMD, PCH and ACPI.
- The exec input has a 10 s timeout (#83), and Telegraf sets the `host` tag.
- The Ansible playbook installs from the checkout and removes the old sudoers
  lines and Suricata files.

### Firewall logs
- Graylog 7.1 with OpenSearch 2.19 replaces Graylog 5 with Elasticsearch 7.10.
- Extractor columns now follow filterlog 0.9, and ICMPv6 (`ipv6-icmp`) is
  parsed (#70).
- geoipupdate keeps the GeoLite2 database current (#58, #62, #71).
- `graylog-init` sets up the index set, content pack, stream and processing
  order (#27, #34, #52).

### Monitoring stack
- Grafana 13.2, InfluxDB 2.9 and MongoDB 8.0; every setting lives in `.env`.
- Datasources and dashboards are provisioned (#14, #15, #21).
- New metrics-only mode, without Graylog (#55).
- Grafana has a health check, so `docker compose up --wait` waits for it.

### Dashboards
- Migrated to current Grafana panels: time series and Geomap (#80).
- Host filtering is restored on every query (#33), and Host is built from
  `system` (#74, #89).
- WAN and LAN are detected from interface descriptions (#56, #81).
- Fixed the Interface Summary query. Gateway RTT and loss are averaged
  (#79), and Active Users shows 0 instead of N/A (#42).
- Traffic and throughput graphs no longer spike at their right edge.
- The Suricata signatures panel uses the configured bucket (#77, PR #44),
  and the alert log shows action and SID (#22).

### Project
- Maintained at tekgnosis-net/OPNsense-Dashboard; the MIT License covers
  changes from here on.
- Static checks, unit tests with OPNsense 26.7.4-shaped fixtures, an
  end-to-end suite, and CI.

### Planned (2.1)
- CARP/VIP state metrics (#69)
- dst-ip GeoIP enrichment
- A separate "Firewall Events" dashboard (#41, PR #54)
- Ping and speed-test panels (#79, PR #54)

## Before 2.0.0 (upstream)

| Date | Change |
|---|---|
| 2023-10 | RFC5424 extractors in the Graylog content pack (bsmithio/OPNsense-Dashboard) |
| 2023-01 | Ansible playbook; gateway packet-loss fix |
| 2022-02 | Suricata dashboard |
| 2021-11 | OPNsense port, Graylog content pack, Flux queries with `v.defaultBucket` |
| 2021-04 | Gateway status collected natively in PHP (VictorRobellini/pfSense-Dashboard) |
| 2020-04 | pfSense-Dashboard first published by Victor Robellini |
