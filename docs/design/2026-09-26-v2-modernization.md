# OPNsense-Dashboard v2 — modernization and de-fork

- **Date:** 2026-09-26
- **Status:** approved design, pending implementation
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

**`opnsense/bin/telegraf_pfifgw.php`** is a rewrite that keeps the output contract byte-compatible.

The `interface` measurement:
- Tags: `host`, `name`, `ip4_address`, `ip4_subnet`, `ip6_address`, `ip6_subnet`, `mac_address`, `friendlyname`, `source`.
- Integer field `status`: 1 = up, 0 = down, 2 = unknown.
- Status follows core's `OverviewController::parseIfInfo` rule: up if the `up` flag is set and the media status is `active` or `running`, or empty.
- Addresses come from `interfaces_primary_address[6]($ifname, $ifd)`, which takes the logical name and so handles track6 and `_stf`.

The `gateways` measurement:
- Tags: `host`, `interface`, `gateway_name`.
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
- Output is `temperature,sensor=<s>,host=<h> degrees=<float>`.

**`opnsense/telegraf.d/custom.conf`**
- Commands: `/usr/local/bin/telegraf_pfifgw.php` and `/bin/sh /usr/local/bin/telegraf_temperature.sh`, with no sudo.
- `timeout = "10s"`, because PR #54 hit the 5 s default on routers with many gateways.
- `data_format = "influx"`.
- Documented in the README settings table as a router-side setting, since it isn't an env var.

**Suricata:** no repo files. The user enables the os-telegraf **Intrusion Detection Alerts** input.

**`opnsense/ansible/`**
- `inventory.ini`, INI format.
- The playbook `copy`s files from the checkout (mode 0755 for the scripts, 0644 for the conf).
- Cleanup for upgraders:
  - remove the three legacy sudoers lines with `lineinfile state=absent`, validated by `visudo -cf`;
  - delete `/usr/local/etc/telegraf.d/suricata.conf`;
  - delete `/usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml`;
  - delete `/tmp/eve.json`.
- Restarts Telegraf.
- GUI toggles are not automated.

**Graylog content pack columns**
- Rename `tracker`→`rid` in all six extractors.
- Name the trailing TCP columns per filterlog: `…,tcp-flags,sequence,ack,window,urg,tcp-options`.
- Name the trailing UDP column `datalength`, and drop the extra columns.
- The exact per-protocol headers are fixed in the plan from filterlog's `description.txt`.
- No dashboard query uses the renamed columns.

**`docs/opnsense.md`** lists the 26.7 GUI steps in order:
1. Services → Telegraf → General: Enable, **Run as Root**.
2. Input: Network, PF, and Intrusion Detection Alerts (if IDS is used). Also CPU, Disk, Memory, System and Processes if they are not already on.
3. Output: Influx v2 URL, token, org and bucket.
4. System → Settings → Logging → Remote: UDP to the Graylog host on port 1514, **RFC5424 enabled**, application `filterlog`.
5. System → Settings → Miscellaneous: the Thermal Sensors hardware option.
6. Copy the files, by hand or with Ansible.
7. Verify with `telegraf --test`.

### 5.3 Monitoring stack

`docker-compose.yaml` has no `version:` key and one bridge network.

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
2. Finds the index set by prefix `opnsense_filterlog`, or creates it. Rotation period is `GRAYLOG_INDEX_ROTATION` (ISO-8601, default `P1D`). Max index count is `GRAYLOG_INDEX_MAX_COUNT`, clamped to 1–3650, default 30.
3. Uploads the content pack if its id/rev is absent, and installs it if not installed.
4. Assigns the `OPNsense / filterlog` stream to the index set with `remove_matches_from_default_stream=true`.
5. Makes sure the GeoIP pipeline is connected to the stream.
6. Sets the message-processor order so the Pipeline Processor runs after the Message Filter Chain, and enables both.
7. Prints what it did and never prints secrets.
8. Exits non-zero if any API call fails.

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
- `GRAYLOG_HEAP`, `OPENSEARCH_HEAP`
- `GRAYLOG_INDEX_ROTATION`, `GRAYLOG_INDEX_MAX_COUNT`
- MaxMind account ID, licence key, and update hours

Secrets have no working defaults: the placeholders in `.env.example` must be replaced. `docs/stack.md` shows how to generate each one.

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

The Suricata dashboard gets the schema migration only.

### 5.5 Cross-file contracts (unchanged, now tested)

| Producer | Consumer |
|---|---|
| Plugin measurement, tag and field names and **types** | Flux filters in the main dashboard |
| Extractor CSV headers and GeoIP rule field names | Lucene queries and variables |
| Datasource UIDs (provisioned) | Dashboards, which refer to datasources only through `${dataSource}` / `${ESdataSource}` |

## 6. Testing

1. **PHP unit tests** (`tests/php/`), written before the rewrite:
   - Stub `config.inc`, `util.inc`, `interfaces.inc`, `plugins.inc.d/dpinger.inc` and a stub `Gateways` class. The stubs return fixture data shaped like the 26.7.4 source.
   - Run the script with `php -d include_path=tests/php/stubs`.
   - Compare its output with golden files.
   - Cases: normal router; dpinger `~`; `monitor_disable='1'`; names with spaces, commas and `=`; interface without IPv6; interface missing from `ifconfig` details; degraded gateway states.
2. **Shell tests** (`tests/shell/`): a fake `sysctl` on `PATH` replays Intel coretemp, ACPI, AMD and "no sensors" fixtures. The output is compared with golden files.
3. **Static checks** (`tests/static.sh`):
   - `python3 -m json.tool` / `jq` on every JSON file
   - `php -l`
   - `shellcheck`
   - `docker compose config -q` with `.env.example`
   - `ansible-playbook --syntax-check` and `ansible-lint`
   - `yamllint` on provisioning and workflow files
   - a grep asserting that no `bsmithio`, `Bsmith101`, `bsmithio.com` or `nuuls` references remain
4. **End-to-end** (`tests/e2e/run.sh`):
   - Setup: compose project `opnsense-dash-test`; ports bound to `127.0.0.1` on non-default numbers; OpenSearch heap 512m, Graylog heap 512m–1g; MaxMind's public **test** database mounted in place of GeoLite2; then `graylog-init`.
   - Syslog: send synthetic RFC5424 filterlog lines over UDP (IPv4/IPv6 × TCP/UDP/ICMP, block/pass, source IPs from the test database). Assert that the parsed fields and `src-ip-geo-country` are present in OpenSearch.
   - Metrics: write golden plugin output and synthetic `system`/`cpu`/`mem`/`disk`/`processes`/`pf`/`net`/`temperature`/`suricata` points to InfluxDB.
   - Queries: run **every panel target and every query variable** of both dashboards through Grafana `/api/ds/query`, with variables resolved. Fail on any error frame or empty result.
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
| 5 | CI, `CHANGELOG.md`, final README, `docs/troubleshooting.md`, `CLAUDE.md`. |

Every commit carries the docs for its own change. Commits are gated on their checks passing. After commit 5 the branch is pushed and a PR opened. The maintainer merges, leaves the fork network, and enables Issues.

## 8. Out of scope

- An upgrade path from the 2023 stack (D4).
- Graylog Data Node. Self-managed OpenSearch is used because Grafana reads the index directly and Data Node client certificates expire after 30 days by default.
- InfluxDB 3 and SQL/InfluxQL rewrites.
- Replacing Graylog with a lighter pipeline.
- Automating OPNsense GUI settings through its API.
- New panels beyond the fixes listed.

## 9. Risks and open points (resolved during implementation)

| Risk | Mitigation |
|---|---|
| Content pack v1 import into Graylog 7.1 is untested. | The end-to-end run proves it. If it fails, re-export the pack from a 7.1 instance after creating the entities through the API. |
| Auto-migrated Geomap may not render the terms query as intended. | Scripted fix plus end-to-end query assertion plus screenshot review. |
| Graylog preflight or setup screen may appear even with `GRAYLOG_ELASTICSEARCH_HOSTS` set. | Verify on first boot. Document or disable per official env vars. |
| The PHP stubs could drift from real OPNsense. | Stubs mirror 26.7.4 signatures. The maintainer's on-device run is the final gate. |
| 5 GB of free RAM on the dev host for the end-to-end stack. | Small heaps, run one stack at a time, `down -v` afterwards. |
