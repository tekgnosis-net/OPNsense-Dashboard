# Monitoring host setup

The monitoring host runs InfluxDB and Grafana, plus Graylog, MongoDB,
OpenSearch and geoipupdate for the firewall log (the full stack). Everything
is configured from `.env`.

## 1. Prepare the host

- Docker Engine with the Compose v2 plugin (`docker compose version`).
- **Full stack only:**
  - **CPU with AVX.** Check with `grep -qw avx /proc/cpuinfo && echo ok`.
    MongoDB needs it; on Proxmox set the VM CPU type to `x86-64-v3` or `host`.
    Without AVX, use the metrics-only mode.
  - **OpenSearch memory maps.** Run:
    ```sh
    echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf
    sudo sysctl --system
    ```
- **Full stack only, for the map:** create a free MaxMind account at
  <https://www.maxmind.com/en/geolite2/signup>, then generate a licence key
  (Account > Manage License Keys). A new key can take a few minutes to become
  active.

## 2. Configure

```sh
git clone https://github.com/tekgnosis-net/OPNsense-Dashboard.git
cd OPNsense-Dashboard
cp .env.example .env
openssl rand -hex 32    # paste as INFLUXDB_ADMIN_TOKEN
openssl rand -hex 48    # paste as GRAYLOG_PASSWORD_SECRET
```

Edit `.env`:
- set `TZ`;
- set every password (`GRAFANA_ADMIN_PASSWORD`, `INFLUXDB_ADMIN_PASSWORD`,
  `GRAYLOG_ADMIN_PASSWORD`);
- paste the two generated values;
- add your MaxMind account ID and licence key.

Wrap any value that contains `$` in single quotes. Every setting is listed in
the README's Settings table.

**Metrics only.** Set `COMPOSE_PROFILES=` (empty). You get InfluxDB and
Grafana; the Firewall row of the dashboard shows "No data".

## 3. Start

```sh
docker compose up -d
docker compose ps                          # all services "healthy" or "running"
docker compose run --rm graylog-init       # full stack only, once
```

`graylog-init` configures Graylog through its API:
- the `opnsense_filterlog` index set;
- the content pack (syslog input on UDP 1514, filterlog extractors, stream,
  GeoIP lookup);
- the stream's index set, and resuming the stream;
- the processing order.

It is safe to run again. If the GeoIP database has not downloaded yet, it
waits up to `GEOIP_WAIT_SECONDS`, then continues with a warning. The map
starts working as soon as the file arrives.

## 4. Create the Telegraf token

Telegraf on the firewall needs a token that can write to your bucket:

1. Open InfluxDB at `http://<host>:8086` and log in with
   `INFLUXDB_ADMIN_USER` / `INFLUXDB_ADMIN_PASSWORD`.
2. Go to Load Data > API Tokens > Generate API Token > Custom API Token.
3. Under Buckets, tick **Write** for your bucket, then save.
4. Copy the token now. InfluxDB 2.9 stores tokens hashed, so it can't be
   shown again.

Use it as the "Influx v2 Token" in OPNsense ([opnsense.md](opnsense.md)).

## 5. Open the dashboards

Grafana: `http://<host>:3000`, logging in with `GRAFANA_ADMIN_USER` /
`GRAFANA_ADMIN_PASSWORD`. The **OPNsense** folder holds both dashboards; the
datasources are already configured.

On the OpenSearch datasource's settings page, "Save & test" reports
`Index not found: opnsense_filterlog_*`. That is a known problem in the
plugin's test with wildcard index patterns
([grafana/opensearch-datasource#888](https://github.com/grafana/opensearch-datasource/issues/888));
queries and dashboards work. Don't change the index pattern.

Dashboard variables (at the top):
- **Host.** Firewalls that report the `system` measurement. Pick one when
  you have several.
- **WAN / LAN.** Interfaces whose OPNsense description starts with "WAN" are
  WAN; all others are LAN. Rows show the description and filter on the
  device (`igb0`, `vtnet0`, …). If your WAN has a different description,
  either rename it in OPNsense, or edit the variable (Dashboard settings >
  Variables > WAN) and save.
- **iface.** The interfaces the Firewall row counts blocks for.
- **src_ip, dst_port.** Filters for the Firewall row. Clicking a source in
  the flow or event tables sets src_ip.
- **Gateway, Disk, Sensor.** Filters for their panels.

Reading the Firewall row:
- **Blocked from the Internet** counts blocks on WAN interfaces.
  **Blocked from Your Networks** counts blocks on every other interface, which
  means traffic from your own devices. The firewall log records both as
  direction "in", because the packet entered the firewall on that interface.
- **Kind** says what was blocked:
  - *New connection*: a refused connection attempt (TCP SYN).
  - *Late packet*: part of a connection the firewall had already closed (FIN,
    RST or ACK). This is usually harmless.
  - *Not TCP*: UDP or ICMP.
- Your own device near the top of "Blocked from Your Networks" is covered in
  [troubleshooting](troubleshooting.md#one-of-my-own-devices-is-the-top-blocked-source).

Dashboards are provisioned from `grafana/dashboards/`. You can edit and save
them in the UI. A change to the file (for example after a `git pull`)
replaces your UI edits; use "Save as" to keep a personal copy.

## Storage

| Data | Volume | Grows with | Kept for |
|---|---|---|---|
| Metrics | `influxdb_data` | number of interfaces, gateways and sensors | `INFLUXDB_RETENTION` |
| Firewall log | `opensearch_data` | firewall log volume | `GRAYLOG_INDEX_ROTATION` × `GRAYLOG_INDEX_MAX_COUNT` |
| Graylog journal | `graylog_data` | bursts OpenSearch can't absorb yet | up to `GRAYLOG_JOURNAL_MAX_SIZE` |

- **Journal.** Graylog refuses to start unless the free disk plus its current
  journal is at least `GRAYLOG_JOURNAL_MAX_SIZE`.
- **OpenSearch.** It stops accepting writes (indices become read-only) when
  the disk passes 95% full.
- **Don't bind-mount an empty directory over `/usr/share/graylog/data`.**
  That hides the image's `graylog.conf` and Graylog won't start. Use the
  named volume.

## Changing settings later

- **Most settings:** edit `.env`, then run `docker compose up -d`.
- **"First start" settings** (Grafana/InfluxDB admin logins, InfluxDB
  org/bucket/retention/token) only apply to an empty volume. To change them:
  - Grafana admin password:
    `docker compose exec grafana grafana cli admin reset-admin-password '<new>'`
  - InfluxDB: use the InfluxDB UI (Settings, Buckets, API Tokens).
- **`GRAYLOG_ADMIN_PASSWORD`** is read at every start: edit it, then run
  `docker compose up -d graylog`.
- **Index rotation and retention** are set when `graylog-init` creates the
  index set. Change them later in Graylog: System > Indices > OPNsense /
  filterlog > Edit.

## Upgrading images

Image versions are pinned in `.env.example`. After changing a pin, run the
end-to-end suite (`sh tests/e2e/run.sh`) before using it.

This release only supports a fresh install: moving data over from the 2023
stack (Graylog 5 / Elasticsearch 7 / Grafana 9) is not supported. Start with
empty volumes.

## Backup

Back up the named volumes; the project name is `opnsense-dashboard`. For
example:

```sh
docker run --rm -v opnsense-dashboard_influxdb_data:/v -v "$PWD":/b alpine tar czf /b/influxdb.tgz -C /v .
```

`grafana_data` holds only UI edits and users, because dashboards and
datasources are provisioned from this repository.
