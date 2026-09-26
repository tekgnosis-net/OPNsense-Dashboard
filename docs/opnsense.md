# OPNsense (router) setup

Written for OPNsense 26.7.x, against the 26.7.4 source. Older releases are untested.

This page sets up the firewall side:
- Telegraf sends metrics to InfluxDB.
- The firewall log goes to Graylog over syslog.

Set up the monitoring host first ([stack.md](stack.md)). You will need its
address, the InfluxDB organization and bucket, a Telegraf write token, and
the syslog port.

## 1. Install the Telegraf plugin

System > Firmware > Plugins: install **os-telegraf**.

## 2. Configure Telegraf

Services > Telegraf.

**General**
- Enable Telegraf Agent: checked
- **Run as Root: checked.**
  - The collectors read pf statistics, dpinger gateway status and Suricata's
    `eve.json`, and only root can read those.
  - Without it, the `pf` input fails, the dashboard's Host list stays empty,
    and every panel is blank.
- Leave Hostname empty. The firewall panels match InfluxDB's `host` tag
  against the hostname in the syslog messages, and both must be the
  firewall's own hostname.

**Input**
- CPU, Disk, Memory, Processes, System: checked (they are on by default)
- Network: checked
- PF: checked
- Intrusion Detection Alerts: checked if you use Intrusion Detection and want
  the Suricata dashboard

**Output**
- Enable Influx v2 Output: checked
- Influx v2 URL: `http://<monitoring-host>:8086`, the host running the stack
  (not `localhost`)
- Influx v2 Token: the Telegraf write token (see stack.md, "Create the Telegraf
  token")
- Influx v2 Organization and Influx v2 Bucket: your `INFLUXDB_ORG` and
  `INFLUXDB_BUCKET`
- Leave "Enable Influx Output" (the v1 output) unchecked.

Click Save and Apply.

## 3. Install the collectors

The collectors are two scripts and one Telegraf drop-in file.

### With Ansible (recommended)

See [opnsense/ansible](../opnsense/ansible/README.md). The playbook copies
the files from your checkout and removes leftovers from earlier versions.

### By hand

As root on the firewall:

```sh
base=https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master
fetch -o /usr/local/bin/telegraf_pfifgw.php "$base/opnsense/bin/telegraf_pfifgw.php"
fetch -o /usr/local/bin/telegraf_temperature.sh "$base/opnsense/bin/telegraf_temperature.sh"
chmod 755 /usr/local/bin/telegraf_pfifgw.php /usr/local/bin/telegraf_temperature.sh
mkdir -p /usr/local/etc/telegraf.d
fetch -o /usr/local/etc/telegraf.d/custom.conf "$base/opnsense/telegraf.d/custom.conf"
configctl telegraf restart
```

`fetch` is FreeBSD's built-in downloader; `curl -o` works too.

### Upgrading from bsmithio/OPNsense-Dashboard

The old setup edited sudoers and installed Suricata files that are no longer
used. The Ansible playbook removes them. By hand:

- Remove `/usr/local/etc/telegraf.d/suricata.conf`,
  `/usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml` and
  `/tmp/eve.json`.
- Run `visudo` and delete these lines, in this order: `Defaults!PFIFGW …`,
  `Cmnd_Alias PFIFGW …`, and any `telegraf ALL=…` line.
  - Use `visudo` rather than `printf`/`tee`: the root shell (tcsh) expands `!`
    even inside quotes.

## 4. Temperature sensors

System > Settings > Miscellaneous > Thermal Sensors > Hardware:
- choose "Intel Core* CPU on-die thermal sensor (coretemp)" or
  "AMD K8, K10 and K11 CPU on-die thermal sensor (amdtemp)";
- then reboot.

ACPI thermal zones work without this setting. Systems without sensors just
report nothing.

## 5. Send the firewall log to Graylog

System > Settings > Logging > Remote, then add a destination:
- Enabled: checked
- Transport: UDP(4)
- Applications: filter (filterlog)
- Levels: include `info`; filterlog logs at that level
- Hostname: the monitoring host
- Port: `SYSLOG_PORT` from `.env` (default 1514)
- **RFC5424: checked.** This is required: the Graylog extractors only match
  RFC5424 messages.
- Description: Graylog

## 6. Suricata (optional)

1. Enable Intrusion Detection as usual: Services > Intrusion Detection >
   Administration.
2. Tick **Intrusion Detection Alerts** on the Telegraf Input tab. Telegraf
   then reads `/var/log/suricata/eve.json`.

No extra files are needed. OPNsense 26.1 removed the `custom.yaml` hook that
earlier versions of this project used.

## 7. Check that it works

Run these **as root**. Testing as the `telegraf` user hides the root-only
failures that "Run as Root" fixes.

```sh
/usr/local/bin/telegraf_pfifgw.php            # interface and gateways lines
sh /usr/local/bin/telegraf_temperature.sh     # temperature lines (empty without sensors)
telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d
pluginctl -r return_gateways_status           # dpinger's view of gateway delay and loss
```

## What the collectors send

| Measurement | Tags | Fields | Source |
|---|---|---|---|
| `interface` | `host`, `name` (device), `ip4_address`, `ip4_subnet`, `ip6_address`, `ip6_subnet`, `mac_address`, `friendlyname` (OPNsense description), `source` | `status`: 1 up, 0 down, 2 unknown | `telegraf_pfifgw.php` |
| `gateways` | `host`, `interface`, `gateway_name` | `monitor`, `source`, `gwdescr`, `status` ("1" online, "0" offline, "2" degraded, "Unavailable"); `delay` and `stddev` in ms and `loss` in %, left out until dpinger has data | `telegraf_pfifgw.php` |
| `temperature` | `host`, `sensor` (`cpu0`, `tz0`, `amdtemp0core0sensor0`, …) | `degrees` (°C) | `telegraf_temperature.sh` |
| `system`, `cpu`, `mem`, `disk`, `processes`, `pf`, `net` | Telegraf defaults | Telegraf defaults | os-telegraf inputs |
| `suricata` | `host`, `event_type`, `src_ip`, `src_port`, `dest_ip`, `dest_port` | `alert_signature`, `alert_category`, `alert_action`, `alert_signature_id`, `proto`, … | Intrusion Detection Alerts input |

Telegraf adds the `host` tag to every measurement.
