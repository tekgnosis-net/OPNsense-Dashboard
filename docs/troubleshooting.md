# Troubleshooting

Work from the firewall towards Grafana: does Telegraf produce data, does it
reach InfluxDB, does the syslog reach Graylog, and does Grafana query it?

## The dashboard is empty, or the Host list has no entries

- **Run as Root is off.** Turn on Services > Telegraf > General > Run as
  Root, then Save and Apply.
  - The `pf` input and the collectors need root.
  - Typical errors when it's off: `pf` "Permission denied", `flock()`
    errors, gateway values all 0 (#1, #86, #89).
- Test **as root** on the firewall:
  ```sh
  telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d
  ```
  Testing as the `telegraf` user hides exactly these failures.
- **Telegraf logs `/write?db=telegraf` to localhost.** The InfluxDB v1
  output is enabled. Disable it, and set the Influx v2 URL to the monitoring
  host, not `localhost` (#25).
- **Check InfluxDB receives data.** In Grafana > Explore (InfluxDB), run:
  ```
  import "influxdata/influxdb/schema"
  schema.measurements(bucket: v.defaultBucket)
  ```
  You should see `system`, `cpu`, `net`, `pf`, `interface`, `gateways` and
  others.

## `exec: command timed out`

- Check that `timeout = "10s"` is in `/usr/local/etc/telegraf.d/custom.conf`.
- Time the collector: `time /usr/local/bin/telegraf_pfifgw.php` (#83).

## Gateway RTT or loss is empty

- Monitoring may be disabled for that gateway: System > Gateways >
  Configuration, "Disable Gateway Monitoring" is ticked.
- Or dpinger has no data yet. Check its view with:
  `pluginctl -r return_gateways_status` (#64, #39).
- The values are dpinger's rolling average to the monitor IP. If your ISP
  deprioritises ICMP, choose a different monitor IP (#79).

## The Firewall row or the map is empty

- **RFC5424 is off on the remote logging target**, or the port doesn't match
  `SYSLOG_PORT` (#47, #49, #57). The extractors only match RFC5424 messages.
- **Check Graylog receives the log.** In Graylog > Search, run
  `application_name:filterlog` over the last 5 minutes.
  - If nothing arrives, check the OPNsense remote target and any firewall in
    between.
  - If messages arrive without `src-ip`, `action` and so on, check that
    `graylog-init` ran (`docker compose run --rm graylog-init`) and that the
    target sends RFC5424.
- **Map empty, other panels fine.**
  - Check `docker compose logs geoipupdate` and your MaxMind account ID and
    licence key. New keys take a few minutes to activate (#48, #58, #62, #71).
  - Test a lookup: Graylog > System > Lookup Tables > GeoIP > "Test lookup"
    with a public IP.
  - geoipupdate keeps retrying (about once a minute) until the key works.
    Without MaxMind credentials it logs an error each time; run
    `docker compose stop geoipupdate` if you don't want the map.
- **"Bad Gateway" on a datasource.** Keep the provisioned service-name URLs
  (`http://opensearch:9200`); OpenSearch isn't published to the host (#51).
- **"Save & test" on the OpenSearch datasource says
  `Index not found: opnsense_filterlog_*`.** This is expected. The plugin's
  test can't resolve wildcard index patterns
  ([grafana/opensearch-datasource#888](https://github.com/grafana/opensearch-datasource/issues/888)),
  but queries and dashboards work. Don't change the index pattern.

## WAN panels empty after renaming or re-assigning interfaces

- WAN is every interface whose OPNsense description starts with "WAN" (#81,
  #56). Rename the interface, or edit the WAN variable (Dashboard settings >
  Variables > WAN) and save.

## Active Users shows 0

- Expected when nobody is logged in to a shell (SSH or console). Web GUI
  sessions aren't counted (#42).

## Suricata dashboard is empty

- Check that Intrusion Detection is enabled and **Intrusion Detection Alerts**
  is ticked on the Telegraf Input tab (OPNsense 26.1 and later; #88).
- Check that alerts exist: `tail /var/log/suricata/eve.json` on the firewall.
- To generate test alerts, [tmNIDS](https://github.com/3CORESec/testmynids.org)
  triggers common signatures. It needs `bash` (`pkg install bash`).

## Monitoring host

- **mongodb exits with code 132 or logs an AVX warning.** The CPU lacks AVX.
  On Proxmox, set the VM CPU type to `x86-64-v3` or `host`; otherwise use
  metrics-only mode (`COMPOSE_PROFILES=`) (#45, #37).
- **InfluxDB keeps restarting and logs `passwords must be between 8 and 72
  characters long`.** `INFLUXDB_ADMIN_PASSWORD` is too short or too long. Fix it
  in `.env` and run `docker compose up -d`; setup never completed, so nothing is
  lost.
- **Graylog won't start: `The minimum length for "password_secret" is 16
  characters`.** Set `GRAYLOG_PASSWORD_SECRET` to at least 16 characters
  (`openssl rand -hex 48`).
- **mongodb keeps restarting and logs `MongoDB cannot start: Linux kernel
  versions 6.19 and newer has a known incompatibility`.** MongoDB 8.x refuses
  kernels it reads as 6.19–7.0.13, which includes Ubuntu 26.04's `7.0.0-N`
  kernels (MongoDB SERVER-121912). Use the default `MONGO_IMAGE=mongo:7.0`,
  which Graylog 7.1 supports. Switching is safe while the MongoDB volume is
  still empty. MongoDB 7.0 cannot open a database that 8.0 created; in that
  case recreate the `mongodb_data` volume (this resets Graylog's configuration)
  and run `graylog-init` again.
- **Graylog won't start with a journal or disk preflight error.** Free disk
  space or lower `GRAYLOG_JOURNAL_MAX_SIZE` (#50).
- **Graylog won't start with a missing `graylog.conf`.** A host directory
  was bind-mounted over `/usr/share/graylog/data`. Use the named volume
  (#68).
- **OpenSearch indices became read-only.** The disk went past 95% full. Free
  space, then run:
  ```sh
  docker compose exec opensearch curl -XPUT 'localhost:9200/_all/_settings' -H 'Content-Type: application/json' -d '{"index.blocks.read_only_allow_delete": null}'
  ```
- **A password changed in `.env` had no effect.** "First start" settings
  only apply to an empty volume (#65).
  - Grafana: `docker compose exec grafana grafana cli admin reset-admin-password '<new>'`
  - InfluxDB: use its UI.
  - `GRAYLOG_ADMIN_PASSWORD` applies on the next `docker compose up -d graylog`.
- **Compose commands that name `--profile init` fail with "depends on
  undefined service graylog".** An explicit `--profile` replaces
  `COMPOSE_PROFILES`, so name both profiles: `--profile logs --profile init`.

## Upgrading from bsmithio/OPNsense-Dashboard

- Run the Ansible playbook, or follow "Upgrading" in [opnsense.md](opnsense.md).
- Remove old sudoers lines with `visudo`, not `printf`: the root shell
  (tcsh) expands `!` even inside quotes (#63).

## InfluxDB queries

```
from(bucket: v.defaultBucket)
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "gateways")
  |> limit(n: 10)
```

To delete one measurement, replace `opnsense` with your `INFLUXDB_BUCKET` and
`temperature` with the measurement. The `influx` CLI inside the container is
already configured with your organization and admin token:

```sh
docker compose exec influxdb influx delete --bucket opnsense \
  --start 1970-01-01T00:00:00Z --stop 2100-01-01T00:00:00Z \
  --predicate '_measurement="temperature"'
```
