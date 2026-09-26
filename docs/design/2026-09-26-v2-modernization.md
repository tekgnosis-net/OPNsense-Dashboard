# OPNsense-Dashboard v2 — modernization and de-fork

- **Date:** 2026-09-26
- **Status:** approved design, pending implementation. Amended 2026-09-27 after triaging all 68 upstream issues and PRs (§3.4, D10–D13).
- **Branch:** `v2-modernization`

## 1. Goal

Turn the unmaintained upstream fork into an independently maintained project that works on the current OPNsense release and a current monitoring stack. Upstream's last commit was 2023-10-10.

Success means all of the following hold:

1. A fresh install on OPNsense **26.7.x** fills both dashboards with no hand-patched scripts.
   - The latest release when this was written was 26.7.4, released 2026-09-15.
   - It is built on FreeBSD 15.1 with PHP 8.5, and ships os-telegraf 1.12.15 / telegraf 1.40.0.
2. The monitoring host runs a supported stack that takes **`.env` + two compose commands**, plus the OPNsense GUI steps.
3. No references to the upstream authors' URLs or hosted images remain. Upstream work is credited in `NOTICE` and the README.
4. Every change is covered by automated checks.
   - Unit tests cover the router scripts.
   - Static checks cover every file type.
   - A local end-to-end run with synthetic data covers the stack and every dashboard query.

## 2. Decisions

These were made by the maintainer during brainstorming.

| # | Decision | Choice |
|---|---|---|
| D1 | Scope | Full modernization: router side, Docker stack, and both dashboards. |
| D2 | Telegraf privileges | **Run as Root** (os-telegraf GUI option). No sudoers edits. |
| D3 | Licensing | Credit upstream. Add **MIT** `LICENSE` for changes from the fork point on, and a `NOTICE` saying that earlier code was published upstream without a license. No action is taken on the upstream repos. |
| D4 | Data migration | Fresh install only. There is no upgrade path from the 2023 stack. |
| D5 | Delivery | Feature branch `v2-modernization`, five commits, then a PR on `tekgnosis-net/OPNsense-Dashboard`. |
| D6 | Setup approach | **Provisioned stack** (approach A). The rejected alternatives were fully manual (B) and provisioning Influx/Grafana only (C). |
| D7 | Layout | New layout (section 4) plus GitHub issue and PR templates. |
| D8 | WAN/LAN defaults | Detected from the OPNsense interface description. Users can still override them. |
| D9 | Local remote | `upstream` git remote removed. Done on 2026-09-26. |
| D10 | Metrics-only install (upstream #55) | The log services sit under a `logs` compose profile. `.env.example` sets `COMPOSE_PROFILES=logs`, so the full stack stays the default. Removing it gives InfluxDB and Grafana only. |
| D11 | CARP metrics (#69) | Backlog for v2.1. |
| D12 | Feature ideas: dst-ip GeoIP, "Firewall Events" dashboard, ping and speed-test panels (PR #54, #41, #79) | Backlog for v2.1. Implement fresh, since upstream code is unlicensed. |
| D13 | Upstream issue triage (§3.4) | All 14 gaps and all regression tests are adopted into this spec. |

The maintainer does these steps after merge. They are documented, not automated:
- Settings → Danger Zone → **Leave fork network**. This is irreversible. The repo qualifies: it is public, 19 MB, and has no child forks, stars or issues.
- Enable Issues on the repo.

## 3. What changed upstream since 2023

This section records research findings as evidence. "Verified" means checked against source at the tag or in official documentation.

### 3.1 OPNsense (verified against opnsense/core, plugins and ports at tag 26.7.4)

| Area | Finding | Consequence |
|---|---|---|
| `get_interfaces_info()` | Removed in 24.1 (core commit `4d495ea6c`, "Interfaces: Overview - remove legacy version", core#6832). | `telegraf_pfifgw.php` fatals on every run. The `interface` and `gateways` measurements have been missing since 24.1. |
| `\OPNsense\Routing\Gateways` | Moved to MVC in 24.1 (`1c890b8cc`). The constructor now takes no arguments. `gatewaysIndexedByName()` still exists. | Use `new Gateways()`. |
| `monitor_disable` | Now an MVC BooleanField, always present as `'0'` or `'1'`. | `isset()` is always true, so every gateway reads "Unmonitored". Use `!empty()`. |
| Gateway status | `return_gateways_status()` is marked deprecated. `dpinger_status()` is current and is what core's `scripts/routes/gateway_status.php` uses. Values are `"1.2 ms"` / `"0.0 %"`, or `"~"` when there is no data. Status is one of `none`, `down`, `force_down`, `delay`, `loss`, `delay+loss`. | Switch to `dpinger_status()`. Omit numeric fields when the value is `~`. Map the degraded states. |
| Address helpers | `get_real_interface`, `interfaces_primary_address[6]`, `get_interface_mac` and `legacy_interfaces_details` still exist. | Call `legacy_interfaces_details()` once and pass the result to every helper. |
| PHP binary | Core CLI scripts use `#!/usr/local/bin/php`. `php-cgi` remains only for lighttpd. | Change the shebang. |
| os-telegraf | Still supports Influx v2 output. The rc script passes `--config-directory /usr/local/etc/telegraf.d` and `setup.sh` creates that directory. The rc script now runs `telegraf config check` before start. There is no exec or temperature input in the GUI. The **Intrusion Detection Alerts** input tails `/var/log/suricata/eve.json` with `name_override="suricata"` and the same `tag_keys` and `json_string_fields` as this repo's `suricata.conf`. `[[inputs.pf]]` has no sudo option. | Keep `telegraf.d/custom.conf`. Remove the `mkdir` step. Replace the repo's Suricata files with the built-in input. `pf` needs root, which explains the empty dashboard in upstream issue #89. |
| sudo | Core owns only `sudoers.d/20-opnsense`. | Moot, since Telegraf runs as root (D2). Ansible removes the old sudoers lines. |
| Suricata | 26.1 removed `custom.yaml` from IDS `+TARGETS` and from `suricata.yaml`; the `conf.d/*.yaml` drop-ins replaced it in 25.7.10. Alerts already go to `/var/log/suricata/eve.json` (`root:wheel 640`, rotated). `/tmp` is wiped at boot. | Delete `config/suricata/*` and the `/tmp/eve.json` handling. |
| filterlog | The CSV layout is unchanged from 0.7 to 0.9. New action values: `match`, `noscrub`, `defer`. Rule label/UUID is the 4th field. The last TCP field is `options`. RFC5424 messages carry `[meta sequenceId="N"]`. | Extractors still match, but **only with RFC5424 enabled**. Rename column `tracker`→`rid`. Fix the trailing TCP/UDP columns. |
| Temperature | FreeBSD 15.1 still has `dev.cpu.N.temperature` and `hw.acpi.thermal.tzN.temperature`, plus `dev.amdtemp`/`dev.pchtherm`. Telegraf `inputs.temp` returns "not implemented" on FreeBSD. | Keep the script. Discover all Kelvin-type sysctls. |
| syslog-ng | Hostname and program handling are unchanged. | The stream rule on `application_name` still works. |

### 3.2 Monitoring stack (verified against Docker Hub, release notes and docs)

| Component | 2023 pin | Target | Notes |
|---|---|---|---|
| Grafana | 9.2.10 | **13.2.2** | Angular was removed in 12, so `grafana-worldmap-panel` fails to load. Built-in migrations convert worldmap→geomap and graph→timeseries. `GF_INSTALL_PLUGINS` is deprecated; use `GF_PLUGINS_PREINSTALL`. |
| Search backend | Elasticsearch OSS 7.10.2 | **OpenSearch 2.19.6** | Grafana's ES datasource needs ES ≥ 7.17. Graylog 7 deprecates ES (removal is planned for 8.0). OpenSearch 3.x is unsupported by Graylog 7.1. |
| Grafana plugin | — | `grafana-opensearch-datasource` 2.34.4 | Apache-2.0, needs Grafana ≥ 10.4. Plugin issue #1083 ("Get version and save" returns 404 on Grafana 13) is avoided by provisioning `flavor`/`version`. |
| Graylog | 5.0.2 | **7.1.9** | Extractors are "legacy" but supported. The v1 content-pack format, regex extractor, CSV converter and MaxMind adapter are all present in 7.1. An in-place upgrade would need six hops, hence D4. |
| MongoDB | 6.0.4 | **8.0** | Graylog 7.1 supports 7.x–8.2.x. `mongo:latest` (8.3) is outside the supported range. |
| InfluxDB | 2.6.1 | **2.9.1** | Stay on 2.x: InfluxDB 3 has no Flux, and all 35 dashboard queries are Flux. 2.9 hashes tokens. |
| compose `version:` | present | removed | Obsolete per the Docker compose spec. |

### 3.3 Existing dashboard defects found

- The WAN and LAN "Interface Summary" queries have a Flux syntax error: `keep(columns: [..., "ip4_subnet" "mac_address", ...])` is missing a comma.
- The `Host` variable is built from the `pf` measurement. When `pf` is missing (non-root Telegraf), `Host` is empty and every host-filtered panel is empty (#89).
- The `src_ip`, `dst_ip` and `dst_port` variables query underscored fields. The extractors emit `src-ip`, `dst-ip` and `dst-port`.
- Gateway Summary maps only `0`/`1`, so degraded dpinger states show as raw text.
- The `WAN` default is hard-coded to `igb0`. That fails on VMs using `vtnet` (#56).
- The Suricata dashboard's "Top Alert Signatures" query uses `from(bucket: "opnsense")` instead of `v.defaultBucket` (#77, PR #44).
- The multi-firewall host filtering from upstream commit `8fa23f1` (#33) has partly regressed:
  - Panel 111 ("Firewall Blocked Events") has no `source:$Host`.
  - The `LAN`, `iface`, `src_ip`, `dst_ip` and `dst_port` variables have no host filter.
  - "Top IP Blocked" uses a lowercase `and`, which Lucene treats as a search term, so its Host filter is effectively optional.
- The extractor CSV headers are inconsistent:
  - Some use `ipversion`, others `ip-version`.
  - IPv4 UDP uses `flags` where the others use `ip-flags`.
  - IPv6 TCP declares 27 columns where filterlog emits 26 (a likely cause of #70).
  - Several have a spurious trailing `opnsense-rid`.
- Gateway RTT and Loss panels plot raw points with no aggregation, which looks implausible over long ranges (#79).
- Active Users shows "N/A" when Telegraf omits `n_users` because `/var/run/utx.active` is missing (#42, #32).
- The Suricata "Alert Logs" table lacks the alert action and signature ID (#22).
- The GeoIP pipeline rule sets `src-ip-geo-location` and `src-ip-geo-city`. GeoLite2-Country has no coordinates or city, so those lookups are always empty.

### 3.4 Upstream issue triage (68 items, 2026-09-27)

Every open and closed issue and PR on bsmithio/OPNsense-Dashboard was read, including comments and PR diffs, and checked against this spec. The raw dumps are in the session scratchpad and not committed.

| Class | Items |
|---|---|
| Covered by this design | #89 #88 #82 #80 #78 #70 #64 #62 #61 #60 #59 #57 #56 #39 #34 #26 (map) and closed #1 #2 #4 #11 #13 #14 #15 #21 #23 #27 #47 #48 #51 #58 #71 #72 #74 #81 #83 #86 |
| Gaps adopted into this spec | #22 #32/#42 #33 #37/#45 #50 #52 #68 #77/PR44 #79, extractor header inconsistencies, hostname contract, Ansible sudoers variants (PR #28, #1), row titles (#80 comments), GeoIP DB activation delay (#34/#62) |
| Regression risks, now tests (§6) | PR #16 (datasource variables), PR #35 (packet loss), `8fa23f1` (LAN/WAN recv/sent direction, host filters), #25 (light-mode text colour), PR #36 (Ansible visudo validation) |
| Obsolete under this design | #63, #38, #3, #7, #29, #46, PR #73, PR #75 |
| Out of scope | #84 (Prometheus/API question), Zenarmor part of #26 |
| Backlog v2.1 (D11, D12) | #69 CARP, #41 and PR #54 Firewall Events / dst-ip GeoIP, #79 ping panels, PR #54 speed-test panels |
| Metrics-only mode (D10) | #55 |

## 4. Repository layout

```
README.md  CHANGELOG.md  LICENSE  NOTICE  CLAUDE.md  .env.example  docker-compose.yaml
.github/     ISSUE_TEMPLATE/{bug_report.yml, enhancement.yml, question.yml, config.yml}
             pull_request_template.md  workflows/ci.yml
docs/        opnsense.md  stack.md  troubleshooting.md  images/  design/
opnsense/    bin/telegraf_pfifgw.php  bin/telegraf_temperature.sh  telegraf.d/custom.conf
             ansible/{playbook.yml, inventory.ini, README.md}
graylog/     OPNsense-pack.json  init/graylog-init.sh
grafana/     dashboards/{opnsense.json, opnsense-suricata.json}
             provisioning/{datasources/datasources.yaml, dashboards/dashboards.yaml}
tests/       php/  shell/  e2e/
```

Removed: `configure.md` (split into `docs/`), `config/suricata/`, the top-level screenshots, `plugins/README.md` (merged into `docs/opnsense.md`), and the old `config/` and `plugins/` directories. Moves use `git mv` so history is kept. Dashboard titles and UIDs (`suTmk8c7k`, `94raP_-7z`) are unchanged.

## 5. Design

### 5.1 De-fork, credits, license, docs

- `LICENSE`: MIT, © 2026 tekgnosis-net. It covers changes from the fork point (commit `48119ee`) onwards.
- `NOTICE` covers:
  - where the project came from: VictorRobellini/pfSense-Dashboard (2020) → bsmithio/OPNsense-Dashboard (2021–2023) → this repository;
  - contributor names from `git log`;
  - the existing thanks to /u/trumee and to subract (IRQ10/Graylog-OPNsense_Extractors#11);
  - a statement that the upstream code carried no license.
- README sections, in order:
  - purpose
  - screenshots
  - a mermaid diagram of the three pipelines
  - supported versions: OPNsense 26.7.x is tested; older releases are untested
  - quick start
  - the `.env` settings table
  - repo layout
  - credits and history
  - license
- `CHANGELOG.md` starts at **2.0.0** ("first release as an independent project") and summarizes the upstream history.
- The content pack `vendor`/`url` fields point to tekgnosis-net. The pack `rev` is bumped.
- Issue forms:
  - Bug form fields: OPNsense version, os-telegraf version, stack image versions, `telegraf --test` output, and which dashboard or panel is affected.
  - Enhancement form.
  - Question form.
  - `config.yml` with blank issues disabled.
  - A PR template with a checklist: tests run, docs updated, `.env` table updated.
- `CLAUDE.md` is updated in the same commit as each behaviour change.

### 5.2 Router side

**`opnsense/bin/telegraf_pfifgw.php`** is a rewrite that keeps the measurement, tag and field names and types compatible, with one deliberate change:

- **No `host=` tag in the script's output** (the temperature script too).
  - Telegraf adds its agent `host` tag to every metric, but it never overrides a tag the plugin already set (verified in Telegraf `makemetric.go` v1.40.0).
  - With a script-supplied `gethostname()`, setting the os-telegraf Hostname option would make `interface`, `gateways` and `temperature` disagree with `system`, which the `Host` variable is built from.
  - Letting Telegraf add the tag keeps one source of truth.

The `interface` measurement:
- Tags: `host` (added by Telegraf), `name`, `ip4_address`, `ip4_subnet`, `ip6_address`, `ip6_subnet`, `mac_address`, `friendlyname`, `source`.
- Integer field `status`: 1 = up, 0 = down, 2 = unknown.
- Status follows core's `OverviewController::parseIfInfo` rule: up if the `up` flag is set and the media status is `active` or `running`, or empty.
- Addresses come from `interfaces_primary_address[6]($ifname, $ifd)`, which takes the logical name and so handles track6 and `_stf`.

The `gateways` measurement:
- Tags: `host` (added by Telegraf), `interface`, `gateway_name`.
- String fields: `monitor`, `source`, `gwdescr`, `status`.
- Float fields: `delay`, `stddev`, `loss`.
- Status mapping, which stays a **string** field so the type is unchanged:

  | dpinger `status` | Field value |
  |---|---|
  | `none` | `"1"` |
  | `down`, `force_down` | `"0"` |
  | `delay`, `loss`, `delay+loss` | `"2"` |
  | missing | `"Unavailable"` |

- `delay`, `stddev` and `loss` are omitted when dpinger reports `~`. If all three are absent, the line still carries its string fields.
- `monitor` is `"Unmonitored"` when `!empty($gw['monitor_disable'])`.

Other changes in the script:
- Line-protocol escaping: tag keys and values escape `,`, `=` and space. String field values escape `"` and `\`. Empty tag values become the existing placeholders (`Unassigned` / `Unavailable`), because Influx drops empty tags.
- Shebang `#!/usr/local/bin/php`. No undefined variables. Warnings don't reach stdout.
- `legacy_interfaces_details()` is called once per run.

**`opnsense/bin/telegraf_temperature.sh`**
- Valid shebang, `grep -F`, clean under `shellcheck`.
- It discovers sensors from Kelvin-type sysctls (`sysctl -a` restricted to `dev.cpu.*`, `hw.acpi.thermal.*`, `dev.amdtemp.*` and `dev.pchtherm.*` temperature leaves). The exact method is fixed in the implementation plan after checking FreeBSD `sysctl` output formats.
- Existing sensor tags keep their names: `cpuN` and `tzN`. New sensors get deterministic names (for example `amdtemp0core0`).
- Output is `temperature,sensor=<s> degrees=<float>`. Telegraf adds `host`.

**`opnsense/telegraf.d/custom.conf`**
- Commands: `/usr/local/bin/telegraf_pfifgw.php` and `/bin/sh /usr/local/bin/telegraf_temperature.sh`, with no sudo.
- `timeout = "10s"`, because PR #54 hit the 5 s default on routers with many gateways.
- `data_format = "influx"`.
- Documented in the README settings table as a router-side setting, since it isn't an env var.

**Suricata:** no repo files. The user enables the os-telegraf **Intrusion Detection Alerts** input.

**`opnsense/ansible/`**
- `inventory.ini`, INI format.
- The playbook `copy`s files from the checkout (mode 0755 for the scripts, 0644 for the conf).
- Creates `/usr/local/etc/telegraf.d` if it is missing, as `telegraf:telegraf 0750`. os-telegraf's `setup.sh` only creates it when the service starts.
- Cleanup for upgraders:
  - remove every historical sudoers variant with `lineinfile state=absent`, each validated by `visudo -cf`. Variants include the 2021 `/sbin/pfctl -s info` line, `Cmnd_Alias PFIFGW`, `Defaults!PFIFGW` and its escaped `Defaults\!PFIFGW` form, and duplicates;
  - remove them in dependency order — `Defaults` first, then `Cmnd_Alias`, then the `telegraf ALL=` rule — so no intermediate file references an undefined alias;
  - delete `/usr/local/etc/telegraf.d/suricata.conf`;
  - delete `/usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml`;
  - delete `/tmp/eve.json`.
- Restarts Telegraf.
- GUI toggles are not automated.

**Graylog content pack columns and GeoIP rule**
- Normalize all six extractors' CSV headers to one naming scheme with the correct column count per protocol:
  - IPv4 and IPv6 common fields;
  - TCP `…,datalength,tcp-flags,sequence,ack,window,urg,tcp-options`;
  - UDP `…,src-port,dst-port,datalength`;
  - ICMP per type as filterlog emits it.
- Specific fixes: rename `tracker`→`rid`; `ipversion`→`ip-version`; `flags`→`ip-flags`; drop the spurious `opnsense-rid`; correct IPv6 TCP to 26 columns.
- The exact headers are fixed in the plan from filterlog's `description.txt` at 26.7.4.
- Fields the dashboards query must keep their names: `interface`, `action`, `src-ip`, `dst-ip`, `dst-port`, `protocol-name`.
- The GeoIP rule sets only `src-ip-geo-country`, because GeoLite2-Country has no coordinates or city.
- The content pack is fixed at the source. The docs never tell users to hand-edit extractors, because the 7.1.6 extractor-edit UI is known to error (upstream #70 comments).

**`docs/opnsense.md`** lists the 26.7 GUI steps in order:
1. Services → Telegraf → General: Enable, **Run as Root**.
2. Input: Network, PF, and Intrusion Detection Alerts (if IDS is used). Also CPU, Disk, Memory, System and Processes if they are not already on.
3. Output: Influx v2 URL, token, org and bucket.
4. System → Settings → Logging → Remote: UDP to the Graylog host on port 1514, **RFC5424 enabled**, application `filterlog`.
5. System → Settings → Miscellaneous: the Thermal Sensors hardware option.
6. Copy the files, by hand or with Ansible.
7. Verify **as root** with `telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d`. Testing as the `telegraf` user hides root-only failures, including the `pf` failure in #89 and the flock errors in #86.
   - `pluginctl -r return_gateways_status` is still valid for checking dpinger values; it maps to `dpinger_status()` at 26.7.4.

### 5.3 Monitoring stack

`docker-compose.yaml` has no `version:` key and one bridge network.

**Profiles (D10).**
- `influxdb` and `grafana` always run.
- `mongodb`, `opensearch`, `graylog` and `geoipupdate` carry `profiles: [logs]`. `graylog-init` carries `profiles: [init]`.
- `.env.example` sets `COMPOSE_PROFILES=logs`, so the full stack is the default.
- In metrics-only mode the OpenSearch datasource is still provisioned but unreachable. The Firewall row shows "No data" and nothing else is affected. The README states this.

**Storage.**
- Every stateful service uses a named volume: mongodb data and config, `opensearch_data`, `graylog_data` at `/usr/share/graylog/data` (as in Graylog's official compose), `geoip_data`, `influxdb_data` (plus config), and `grafana_data`.
- Graylog's volume must not be bind-mounted over an empty host directory. That hides the image's `graylog.conf` (upstream #68). The docs say so.
- `GRAYLOG_JOURNAL_MAX_SIZE` (default `2gb`, documented range `512mb`–`20gb`) is passed as `GRAYLOG_MESSAGE_JOURNAL_MAX_SIZE`. Graylog's preflight check refuses to start without that much free disk (#50).
- `docs/stack.md` gives disk sizing, including OpenSearch's 95% flood-stage watermark, above which indices become read-only.

**Host requirements** (README and `docs/stack.md`):
- x86-64 with **AVX**, or arm64 **ARMv8.2-A** or later. Every MongoDB version Graylog 7.1 supports requires this, verified against MongoDB's production notes.
- On Proxmox the default CPU type (`x86-64-v2-AES`) lacks AVX. Use `x86-64-v3`, which keeps live migration, or `host` (#45, #37).
- The docs give an `grep -qw avx /proc/cpuinfo` pre-check. Metrics-only mode has no AVX requirement.
- `vm.max_map_count ≥ 262144` for OpenSearch.
- About 4 GB of RAM for the full stack at default heaps.

| Service | Key settings |
|---|---|
| `mongodb` | `${MONGO_IMAGE:-mongo:8.0}`. Volumes for `/data/db` and `/data/configdb`. Healthcheck with `mongosh --eval 'db.runCommand({ping:1})'`. |
| `opensearch` | `${OPENSEARCH_IMAGE:-opensearchproject/opensearch:2.19.6}`. `discovery.type=single-node`, `plugins.security.disabled=true`, `action.auto_create_index=false`, `DISABLE_INSTALL_DEMO_CONFIG=true`, `OPENSEARCH_JAVA_OPTS=-Xms${OPENSEARCH_HEAP}-Xmx${OPENSEARCH_HEAP}`. memlock and nofile ulimits. Not published to the host. Healthcheck on `_cluster/health`. |
| `graylog` | `${GRAYLOG_IMAGE:-graylog/graylog:7.1.9}`. Env: `GRAYLOG_PASSWORD_SECRET`, `GRAYLOG_ROOT_PASSWORD_SHA2`, `GRAYLOG_HTTP_EXTERNAL_URI`, `GRAYLOG_HTTP_BIND_ADDRESS=0.0.0.0:9000`, `GRAYLOG_ELASTICSEARCH_HOSTS=http://opensearch:9200`, `GRAYLOG_MONGODB_URI`, `GRAYLOG_ROOT_TIMEZONE=${TZ}`, `TZ`, `GRAYLOG_SERVER_JAVA_OPTS` heap. Publishes `${BIND_ADDRESS}:${GRAYLOG_PORT}:9000` and `${BIND_ADDRESS}:${SYSLOG_PORT}:1514/udp`. Mounts the GeoIP volume read-only. Depends on healthy mongodb and opensearch. |
| `geoipupdate` | `${GEOIPUPDATE_IMAGE}` (MaxMind official). `GEOIPUPDATE_ACCOUNT_ID`, `GEOIPUPDATE_LICENSE_KEY`, `GEOIPUPDATE_EDITION_IDS=GeoLite2-Country`, `GEOIPUPDATE_FREQUENCY=${GEOIP_UPDATE_HOURS}`. Writes to the shared GeoIP volume. |
| `influxdb` | `${INFLUXDB_IMAGE:-influxdb:2.9.1}`. `DOCKER_INFLUXDB_INIT_MODE=setup` plus `USERNAME`, `PASSWORD`, `ORG`, `BUCKET`, `RETENTION` and `ADMIN_TOKEN` from `.env`. Publishes `${BIND_ADDRESS}:${INFLUXDB_PORT}:8086` so the router can write. |
| `grafana` | `${GRAFANA_IMAGE:-grafana/grafana:13.2.2}`. `GF_PLUGINS_PREINSTALL=grafana-opensearch-datasource@${OPENSEARCH_PLUGIN_VERSION}`. Admin user and password from `.env`, `TZ`. Mounts `grafana/provisioning` and `grafana/dashboards` read-only. |
| `graylog-init` | Profile `init`. Pinned alpine image; installs curl and jq. Runs `graylog/init/graylog-init.sh`. Idempotent; details below. |

`graylog-init.sh`:
1. Waits for `/api/system/lbstatus` to report ALIVE, with a bounded timeout.
2. Waits for the GeoIP database file to appear in the shared volume, with a bounded timeout (`GEOIP_WAIT_SECONDS`, default 600, clamped 0–3600).
   - New MaxMind keys can take minutes to activate (#34, #62).
   - On timeout it warns and continues. The lookup adapter picks the file up once it appears.
3. Finds the index set by prefix `opnsense_filterlog`, or creates it. Rotation period is `GRAYLOG_INDEX_ROTATION` (ISO-8601, default `P1D`). Max index count is `GRAYLOG_INDEX_MAX_COUNT`, clamped to 1–3650, default 30.
4. Uploads the content pack if its id/rev is absent, and installs it if not installed.
5. Assigns the `OPNsense / filterlog` stream to the index set with `remove_matches_from_default_stream=true`.
6. Makes sure the GeoIP pipeline is connected to the stream.
7. Sets the message-processor order to **Message Filter Chain → Stream Rule Processor → Pipeline Processor**, all enabled (#52, #34, #26).
   - Graylog 5 and later split stream matching into its own processor (migration `V20220818112023`).
   - The GeoIP pipeline is attached to a stream, so extractors must run first, then stream routing, then pipelines.
8. Prints what it did and never prints secrets.
9. Exits non-zero if any API call fails.

The GeoIP lookup adapter path in the content pack changes to the mounted volume. The mount point is fixed in the plan after checking Graylog's `allowed_auxiliary_paths` default.

Grafana provisioning:
- **InfluxDB datasource:** uid `influxdb-opnsense`, Flux, `http://influxdb:8086`. Organization `$INFLUXDB_ORG`, `defaultBucket` `$INFLUXDB_BUCKET`, token `$INFLUXDB_GRAFANA_TOKEN`, which defaults to the admin token.
- **OpenSearch datasource:** uid `opensearch-opnsense`, `http://opensearch:9200`, index `opnsense_filterlog_*`, time field `timestamp`, `flavor: opensearch`, `version: 2.19.x`, PPL off.
- **Dashboards provider:** `/var/lib/grafana/dashboards`, `allowUiUpdates: true`, in a folder named "OPNsense".

`.env.example` holds every setting with a comment and default. The README table lists each one with its default and allowed range:
- `TZ`
- image tags and plugin version
- `BIND_ADDRESS`, `GRAFANA_PORT`, `INFLUXDB_PORT`, `GRAYLOG_PORT`, `SYSLOG_PORT`
- Grafana admin user and password
- InfluxDB user, password, org, bucket, retention, admin token, and Grafana token
- `GRAYLOG_PASSWORD_SECRET`, `GRAYLOG_ROOT_PASSWORD_SHA2`, `GRAYLOG_EXTERNAL_URI`
- `GRAYLOG_HEAP`, `OPENSEARCH_HEAP`, `GRAYLOG_JOURNAL_MAX_SIZE`
- `GRAYLOG_INDEX_ROTATION`, `GRAYLOG_INDEX_MAX_COUNT`
- MaxMind account ID, licence key, update hours, and `GEOIP_WAIT_SECONDS`
- `COMPOSE_PROFILES`

Secrets have no working defaults: the placeholders in `.env.example` must be replaced. `docs/stack.md` shows how to generate each one.

Settings read by this repo's own scripts (`graylog-init.sh`, the e2e scripts) are clamped in code. Settings passed straight to an upstream image (heaps, journal size, ports) cannot be clamped by compose. For those, the README table documents the supported range and says the values are passed through unvalidated.

The Telegraf **write token** is the one manual step in the stack. The user creates it in the InfluxDB UI and pastes it into OPNsense. The reason is that InfluxDB 2.9 stores tokens hashed and does not accept caller-chosen token values, and the init process must not print secrets to logs.

### 5.4 Dashboards

Migration procedure:
1. Import the current JSON into the local Grafana 13.
2. Let the schema migration run.
3. Save, then export with `GET /api/dashboards/uid/<uid>`.
4. Strip `id` and `version`.
5. Apply the scripted fixes below.
6. Commit the result to `grafana/dashboards/`.

The migration script lives in the scratchpad, not the repo. The committed JSON is the artifact.

Main dashboard fixes:
- `ESdataSource`, plus the 5 firewall panels and 3 variables that use it, change to type `grafana-opensearch-datasource`. The Lucene queries are unchanged.
- The Geomap panel uses a terms aggregation on `src-ip-geo-country` with the query `action:block AND interface:$iface …`, no date histogram, and lookup by country code.
- `Host` is built from the `system` measurement.
- Add the missing comma in the two Interface Summary queries.
- The `src_ip`, `dst_ip` and `dst_port` variables use `src-ip`, `dst-ip` and `dst-port`.
- Gateway Summary mappings are `"0"` OFFLINE (red), `"1"` ONLINE (green), `"2"` DEGRADED (orange).
- `WAN` becomes a query variable: interface `name` where `friendlyname` starts with `WAN`. `LAN` becomes interfaces not in `$WAN`. Both remain editable. `docs/stack.md` explains overrides.
- `WAN` and `LAN` return **text = `friendlyname`, value = `name`**, so repeated rows are titled `${WAN:text}` / `${LAN:text}` (for example "WAN", "LAN", "IOT"), while queries filter on the device name (#80 comments).
- Host filtering is complete (#33):
  - add `AND source:$Host` to panel 111;
  - add `r.host =~ /^${Host:regex}$/` to the `LAN`, `iface` and `WAN` variables;
  - add `source:$Host` to the `src_ip`, `dst_ip` and `dst_port` term queries;
  - uppercase the `and` in "Top IP Blocked".
- Gateway RTT and Loss use `aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)` and one legend entry per `gateway_name` (#79). The panel description says the value is dpinger's rolling average to the monitor IP.
- Active Users sets `noValue: 0`. Its description says it counts shell sessions, not GUI logins (#42, #32).
- Upstream fixes that must survive the migration:
  - LAN/WAN recv/sent naming and direction on panels 34/36/40/49/50/51 (bits) and 42/53 (packets), including `*8.0` on bits and `difference(nonNegative: true)` on monthly totals (`8fa23f1`);
  - summary-table base threshold colour stays `"text"`, which keeps light mode readable (#25).

Suricata dashboard:
- Schema migration.
- The "Top Alert Signatures" query uses `v.defaultBucket` instead of `"opnsense"` (#77, PR #44).
- "Alert Logs" gains `alert_action` and `alert_signature_id` columns (#22). The built-in input flattens eve JSON exactly as the old config did.

### 5.5 Cross-file contracts (all enforced by tests)

| Producer | Consumer |
|---|---|
| Plugin measurement, tag and field names and **types** | Flux filters in the main dashboard |
| Extractor CSV headers and GeoIP rule field names | Lucene queries and variables |
| Datasource UIDs (provisioned) | Dashboards, which refer to datasources only through `${dataSource}` / `${ESdataSource}` |
| Telegraf `host` tag on every measurement | `Host` variable (from `system`) and all Flux host filters |
| Influx `host` tag (router FQDN) | Graylog `source` field (syslog HOSTNAME; OPNsense syslog-ng uses `use_fqdn(yes)`), matched by `source:$Host` in Lucene. Overriding the os-telegraf Hostname option breaks this match; the docs say so. |
| Influx `interface.name` (device name) | filterlog `interface` field, because `$iface` is read from Influx and used in Lucene |
| Bucket from the datasource's `defaultBucket` | Every Flux `from(bucket: v.defaultBucket)`; no literal bucket names anywhere |

### 5.6 Troubleshooting content (`docs/troubleshooting.md`)

Each entry comes from a recurring upstream issue:

| Symptom | Cause and fix |
|---|---|
| Graylog receives UDP but the stream and Firewall row stay empty | RFC5424 not enabled on the remote target, or the port doesn't match `SYSLOG_PORT` (#47, #49, #57). |
| Telegraf log shows `/write?db=telegraf` to localhost | InfluxDB v1 output enabled by mistake. Disable it, and point the v2 URL at the Docker host (#25). |
| `pf` "Permission denied", `flock()` errors, gateway values all 0, or a blank dashboard after an upgrade | Run as Root is off. Test as root (#1, #86, #89). |
| `exec: command timed out` | Check `timeout` in `custom.conf`, then run `time /usr/local/bin/telegraf_pfifgw.php` (#83). |
| Changed a password in `.env` but it had no effect | Init values only apply on first start. Reset procedures for Grafana, InfluxDB and Graylog (#65). |
| Datasource "Bad Gateway" | Don't replace the service-name URLs with host IPs; OpenSearch is not published to the host (#51). |
| Map empty | Check `geoipupdate` logs and MaxMind credentials (new keys take minutes to activate), then use the lookup-table "Test lookup" in Graylog (#48, #58, #71, #62). |
| WAN panels empty after renaming interfaces | WAN is detected by a description starting with "WAN". Rename the interface or override the variable (#81, #56). |
| mongodb container exits with code 132 or an AVX warning | The host CPU lacks AVX. Change the VM CPU type or use metrics-only mode (#45, #37). |
| Graylog won't start: journal or preflight disk error, or missing `graylog.conf` | Free disk or lower `GRAYLOG_JOURNAL_MAX_SIZE`. Don't bind-mount over `/usr/share/graylog/data` (#50, #68). |
| Gateway RTT/Loss empty | Monitoring is disabled for that gateway, or dpinger has no data yet. Check with `pluginctl -r return_gateways_status` (#64, #39). |
| Active Users shows 0 | Expected when nobody is logged in to a shell. GUI sessions are not counted (#42). |
| Manually removing old sudoers lines on tcsh | `!` expands even inside quotes on tcsh. Use `visudo`, or run under `sh` (#63). |

## 6. Testing

1. **PHP unit tests** (`tests/php/`), written before the rewrite:
   - Stub `config.inc`, `util.inc`, `interfaces.inc`, `plugins.inc.d/dpinger.inc` and a stub `Gateways` class. The stubs return fixture data shaped like the 26.7.4 source.
   - Run the script with `php -d include_path=tests/php/stubs`.
   - Compare its output with golden files.
   - Cases:
     - normal router
     - names with spaces, commas and `=`
     - interface without IPv6
     - interface missing from `ifconfig` details
     - no `host=` tag in any output line
   - Gateway cases:
     - dpinger `~` with status `down`, as at dpinger startup: numeric fields omitted, `status="0"`
     - down gateway with `"0.0 ms"` / `"100.0 %"`: `loss=100`, `status="0"`
     - partial loss `"12.5 %"`: `loss=12.5` (PR #35 regression)
     - `"1.2 ms"`: `delay=1.2` (#79)
     - `monitor_disable='1'` with status `none`: `status="1"` and `monitor="Unmonitored"`
     - degraded states `delay`, `loss` and `delay+loss`: `status="2"`
     - a config-side `loss` key in the `Gateways` stub is ignored
2. **Shell tests** (`tests/shell/`): a fake `sysctl` on `PATH` replays Intel coretemp, ACPI, AMD and "no sensors" fixtures. The output is compared with golden files.
3. **Static checks** (`tests/static.sh`):
   - Syntax and lint:
     - `python3 -m json.tool` / `jq` on every JSON file
     - `php -l`
     - `shellcheck`
     - `docker compose config -q` with `.env.example`, both with `COMPOSE_PROFILES=logs` and with it empty
     - `ansible-playbook --syntax-check` and `ansible-lint`
     - `yamllint` on provisioning and workflow files
   - Project-specific checks:
     - A grep asserting that no `bsmithio`, `Bsmith101`, `bsmithio.com` or `nuuls` references remain.
     - **Datasource references** (PR #16): a jq walk asserting every panel, target and variable datasource uid is `${dataSource}` or `${ESdataSource}` (annotation built-ins excepted).
     - **No literal buckets** (#77): fail on `from(bucket: "`. Every Flux query uses `v.defaultBucket`.
     - **Host filters** (#33): every Flux target and query variable contains `r.host =~ /^${Host:regex}$/`, except the `Host` variable itself. Every Lucene target and terms variable contains `source:$Host`. No lowercase ` and ` / ` or ` operators appear in Lucene queries.
     - **Removed APIs**: the plugin contains none of `get_interfaces_info`, `find_interface_network`, `return_gateways_status` or `convert_seconds_to_hms`.
     - **`custom.conf`** (#4, #83): the commands are exactly `/usr/local/bin/telegraf_pfifgw.php` and `/bin/sh /usr/local/bin/telegraf_temperature.sh`, there is no `sudo`, and `timeout = "10s"`.
     - **Ansible** (PR #36): every task touching sudoers has `validate: /usr/local/sbin/visudo -cf %s`.
     - **Light mode** (#25): summary-table base threshold colour is `"text"`.
     - **LAN/WAN direction** (`8fa23f1`): the recv/sent display-name overrides on the named panels map `bytes_recv`→"…Recv…" and `bytes_sent`→"…Sent…". Bits queries multiply by `8.0`.
4. **End-to-end** (`tests/e2e/run.sh`):
   - Setup: compose project `opnsense-dash-test`; ports bound to `127.0.0.1` on non-default numbers; OpenSearch heap 512m, Graylog heap 512m–1g; MaxMind's public **test** database mounted in place of GeoLite2; then `graylog-init`.
   - The InfluxDB bucket is deliberately **not** named `opnsense`, so literal-bucket bugs fail.
   - Syslog:
     - Send synthetic RFC5424 filterlog lines over UDP (IPv4/IPv6 × TCP/UDP/ICMP, block/pass/match, source IPs from the test database).
     - They come from **two hosts**, `fw-a.example.lan` and `fw-b.example.lan`, whose FQDNs also appear as Influx `host` tags.
     - Assert that every normalized field and `src-ip-geo-country` is present in OpenSearch.
   - Metrics:
     - Write golden plugin output and synthetic `system`/`cpu`/`mem`/`disk`/`processes`/`pf`/`net`/`temperature`/`suricata` points for both hosts.
     - Include one `system` point without `n_users`.
     - Include `net` counters with different recv and sent rates.
     - Include `suricata` alerts carrying `alert_action` and `alert_signature_id`.
   - Queries: run **every panel target and every query variable** of both dashboards through Grafana `/api/ds/query`, with variables resolved. Fail on any error frame or empty result. Additionally:
     - **Host isolation** (#33): with `Host=fw-a`, no `fw-b` values appear in any result.
     - **Direction** (`8fa23f1`): the "Bits Recv" series equals the synthetic recv rate × 8.
   - Metrics-only mode (D10):
     - Bring the stack up with `COMPOSE_PROFILES=` (empty).
     - Assert that Grafana and InfluxDB start and every Flux panel returns data.
     - Assert that OpenSearch panels fail cleanly, with no Grafana crash.
   - Screenshots: capture both dashboards with Playwright into `docs/images/`.
   - Teardown: `docker compose -p opnsense-dash-test down -v`. The maintainer's other containers on the host are never touched.
5. **CI** (`.github/workflows/ci.yml`): static checks and unit tests on pushes and PRs. End-to-end on `workflow_dispatch`.
6. **Router-side on real hardware:** the maintainer runs the playbook and `telegraf --test` on a real OPNsense 26.7 router. This is reported as unverified until done.

## 7. Delivery

Branch `v2-modernization`:

| Commit | Contents |
|---|---|
| 0 | This spec. |
| 1 | Layout moves (`git mv`), de-fork references, `LICENSE`/`NOTICE`, README credits, issue and PR templates, `CLAUDE.md`. |
| 2 | Router side: plugin rewrite and PHP tests, temperature script and shell tests, `custom.conf`, Suricata removal, Ansible, extractor columns, `docs/opnsense.md`. |
| 3 | Stack: compose, `.env.example`, provisioning, `graylog-init`, geoipupdate, `docs/stack.md`. |
| 4 | Dashboards: migrated JSON and fixes, end-to-end suite, screenshots. |
| 5 | CI, `CHANGELOG.md` (including "Planned" for v2.1), final README, `docs/troubleshooting.md` (§5.6), `CLAUDE.md`. |

Every commit carries the docs for its own change. Commits are gated on their checks passing. After commit 5 the branch is pushed and a PR opened. The maintainer merges, leaves the fork network, and enables Issues.

## 8. Out of scope

- An upgrade path from the 2023 stack (D4).
- Graylog Data Node. Self-managed OpenSearch is used because Grafana reads the index directly and Data Node client certificates expire after 30 days by default.
- InfluxDB 3 and SQL/InfluxQL rewrites.
- Replacing Graylog with a lighter pipeline.
- Automating OPNsense GUI settings through its API.
- New panels beyond the fixes listed.

Planned for v2.1 (D11, D12). Recorded in `CHANGELOG.md` under "Planned", and as issues once Issues are enabled:
- CARP/VIP state metrics (#69).
- dst-ip GeoIP enrichment.
- A separate "Firewall Events" dashboard (PR #54, #41).
- Ping and speed-test panels (#79, PR #54).

These will be implemented fresh, because upstream code is unlicensed.

## 9. Risks and open points (resolved during implementation)

| Risk | Mitigation |
|---|---|
| Content pack v1 import into Graylog 7.1 is untested. | The end-to-end run proves it. If it fails, re-export the pack from a 7.1 instance after creating the entities through the API. |
| Auto-migrated Geomap may not render the terms query as intended. | Scripted fix plus end-to-end query assertion plus screenshot review. |
| Graylog preflight or setup screen may appear even with `GRAYLOG_ELASTICSEARCH_HOSTS` set. | Verify on first boot. Document or disable per official env vars. |
| The PHP stubs could drift from real OPNsense. | Stubs mirror 26.7.4 signatures. The maintainer's on-device run is the final gate. |
| 5 GB of free RAM on the dev host for the end-to-end stack. | Small heaps, run one stack at a time, `down -v` afterwards. |
