# OPNsense-Dashboard

Grafana dashboards for OPNsense firewalls: system health, interfaces,
gateways, firewall blocks with GeoIP, and Suricata alerts, fed by Telegraf,
Graylog and InfluxDB.

This project is maintained here. It began as a fork of
[bsmithio/OPNsense-Dashboard](https://github.com/bsmithio/OPNsense-Dashboard),
itself based on
[VictorRobellini/pfSense-Dashboard](https://github.com/VictorRobellini/pfSense-Dashboard);
see [Credits and history](#credits-and-history).

## What's monitored

- Active users, uptime, CPU load, per-core CPU, load average, RAM, disk
- CPU and ACPI temperature sensors
- Gateway round-trip time and loss (dpinger)
- Interfaces with IPv4/IPv6 addresses, subnet, MAC, status and OPNsense description
- WAN and LAN traffic and throughput
- Firewall blocks: events, ports, protocols, top source IP and a GeoIP map
- Suricata alerts (separate dashboard)

## Documentation

- [docs/opnsense.md](docs/opnsense.md): router setup (Telegraf, collectors, remote syslog)
- [docs/stack.md](docs/stack.md): monitoring host setup (Docker stack, Graylog, Grafana)
- [docs/troubleshooting.md](docs/troubleshooting.md)

## Repository layout

| Path | Contents |
|---|---|
| `opnsense/` | Files installed on the firewall: Telegraf exec scripts (`bin/`), Telegraf config (`telegraf.d/`), Ansible playbook (`ansible/`) |
| `graylog/` | Graylog content pack |
| `grafana/dashboards/` | Dashboard JSON |
| `docker-compose.yaml` | Monitoring host stack |
| `tests/` | Static checks, unit tests and the end-to-end suite |
| `docs/` | Setup guides, troubleshooting and design records |

## Credits and history

This repository continues the work of:

- **VictorRobellini/pfSense-Dashboard** (2020): the original pfSense dashboard,
  Telegraf plugins and Graylog setup.
- **bsmithio/OPNsense-Dashboard** (2021–2023): the OPNsense port, Flux
  queries, firewall panels, Suricata dashboard and RFC5424 extractors.

Thanks also to [/u/trumee](https://www.reddit.com/r/PFSENSE/comments/fsss8r/additional_grafana_dashboard/fmal0t6/)
for the interface summary approach and to
[subract](https://github.com/IRQ10/Graylog-OPNsense_Extractors/pull/11) for the
RFC5424 extractors. Contributors are listed in [NOTICE](NOTICE).

## License

Changes made in this repository are released under the [MIT License](LICENSE).
The upstream projects were published without a license; see [NOTICE](NOTICE).
