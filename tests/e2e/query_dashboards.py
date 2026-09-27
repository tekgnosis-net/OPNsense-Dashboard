#!/usr/bin/env python3
"""Run every panel target and query variable of both dashboards through
Grafana's /api/ds/query with the template variables resolved (spec §6.4).

  query_dashboards.py full          every query returns data; plus host
                                    isolation (#33), traffic direction
                                    (8fa23f1), map countries, protocols,
                                    blocked flows per origin and Kind
  query_dashboards.py metrics-only  Flux queries return data; OpenSearch
                                    queries fail cleanly

Env: ROOT, GRAFANA_URL, GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD, InfluxDB
settings for seed_influx, and E2E_EXPECTED (send_syslog.py output) in full mode.
"""
import base64
import json
import os
import pathlib
import re
import statistics
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(os.environ["ROOT"])
sys.path.insert(0, str(ROOT / "tests/e2e"))
import seed_influx  # noqa: E402

DATASOURCES = {"${dataSource}": ("influxdb", "influxdb-opnsense"),
               "${ESdataSource}": ("grafana-opensearch-datasource", "opensearch-opnsense")}
SELECTED = {"Host": ["fw-a.example.lan"], "iface": ["igb0", "igb1"]}  # every other variable: All
REGEX_SPECIAL = re.compile(r"([\\^$*+?.()|\[\]{}/])")
LUCENE_SPECIAL = re.compile(r'([+\-=&|><!(){}\[\]^"~*?:\\/ ])')
MODE = sys.argv[1] if len(sys.argv) > 1 else "full"
failures = []


def api(path, body=None):
    token = base64.b64encode(
        f"{os.environ['GRAFANA_ADMIN_USER']}:{os.environ['GRAFANA_ADMIN_PASSWORD']}".encode()).decode()
    request = urllib.request.Request(
        os.environ["GRAFANA_URL"] + path, method="POST" if body is not None else "GET",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def walk(panels):
    for panel in panels:
        yield panel
        yield from walk(panel.get("panels", []))


def fmt(state, how):
    values, all_value = state["values"], state.get("all_value")
    if state["is_all"] and all_value is not None:
        return all_value
    if how == "regex":
        escaped = [REGEX_SPECIAL.sub(r"\\\1", v) for v in values]
        return escaped[0] if len(escaped) == 1 else "(" + "|".join(escaped) + ")"
    if how == "lucene":
        if len(values) == 1:
            return LUCENE_SPECIAL.sub(r"\\\1", values[0])
        return "(" + " OR ".join(f'"{v}"' for v in values) + ")"
    if how == "text":
        return ", ".join(state["texts"])
    return values[0] if len(values) == 1 else "{" + ",".join(values) + "}"


def interpolate(query, variables, default):
    def replace(match):
        name = match.group(1) or match.group(3)
        if name not in variables:
            return match.group(0)
        return fmt(variables[name], match.group(2) or default)
    return re.sub(r"\$\{(\w+)(?::(\w+))?\}|\$(\w+)", replace, query)


def datasource(ref):
    uid = ref.get("uid") if isinstance(ref, dict) else ref
    kind, real_uid = DATASOURCES[uid]
    return {"type": kind, "uid": real_uid}


def query(target):
    status, body = api("/api/ds/query", {"from": "now-30m", "to": "now", "queries": [target]})
    result = (body.get("results") or {}).get(target["refId"], {})
    return status, result.get("error"), result.get("frames") or []


def rows(frames):
    return sum(len(f["data"]["values"][0]) for f in frames if f.get("data", {}).get("values"))


def strings(frames):
    out = []
    for f in frames:
        for field, values in zip(f["schema"]["fields"], f["data"].get("values", [])):
            if field.get("type") == "string":
                out += [v for v in values if v is not None]
    return out


def records(frames):
    """Rows of table frames as dicts keyed by field name."""
    out = []
    for f in frames:
        names = [x["name"] for x in f["schema"]["fields"]]
        out += [dict(zip(names, row)) for row in zip(*f["data"].get("values", []))]
    return out


def label_values(frames, key):
    """Values of one field label, e.g. the terms key of a terms + date_histogram query."""
    out = set()
    for f in frames:
        for field in f["schema"]["fields"]:
            value = (field.get("labels") or {}).get(key)
            if value is not None:
                out.add(value)
    return out


def numbers_by_field(frames):
    out = {}
    for f in frames:
        names = [x["name"] for x in f["schema"]["fields"]]
        values = f["data"].get("values", [])
        if "_field" in names and "_value" in names:
            for key, value in zip(values[names.index("_field")], values[names.index("_value")]):
                out.setdefault(key, []).append(value)
            continue
        for field, column in zip(f["schema"]["fields"], values):
            if field.get("type") == "number":
                key = (field.get("labels") or {}).get("_field") or field["name"]
                out.setdefault(key, []).extend(v for v in column if v is not None)
    return out


def resolve_variables(dash):
    variables = {}
    for var in dash["templating"]["list"]:
        if var["type"] == "datasource":
            continue
        if var["type"] == "custom":
            values = [v.strip() for v in var["query"].split(",") if v.strip()]
            variables[var["name"]] = {"values": values, "texts": values, "is_all": False, "all_value": None}
            continue
        ds = datasource(var["datasource"])
        raw = var["query"]["query"] if isinstance(var["query"], dict) else var["query"]
        if ds["type"] == "influxdb":
            target = {"refId": "V", "datasource": ds, "rawQuery": True,
                      "query": interpolate(raw, variables, "glob")}
        else:
            if MODE == "metrics-only":
                continue
            find = json.loads(raw)
            target = {"refId": "V", "datasource": ds, "queryType": "lucene", "luceneQueryType": "Metric",
                      "query": interpolate(find.get("query", "*"), variables, "lucene"),
                      "metrics": [{"id": "1", "type": "count"}],
                      "bucketAggs": [{"id": "2", "type": "terms", "field": find["field"],
                                      "settings": {"size": "500", "order": "desc", "orderBy": "_count",
                                                   "min_doc_count": "1"}}]}
        status, error, frames = query(target)
        options = list(dict.fromkeys(strings(frames)))
        if ds["type"] != "influxdb":
            options = options or [str(int(v)) for v in sum(numbers_by_field(frames).values(), []) if v]
        pairs = [(o, o) for o in options]
        if var.get("regex"):
            pattern = re.compile(var["regex"].strip("/").replace("(?<", "(?P<"))
            matches = [pattern.match(o) for o in options]
            pairs = [(m.group("value"), m.group("text")) if "value" in pattern.groupindex else (o, o)
                     for o, m in zip(options, matches) if m]
        if status != 200 or error or not pairs:
            failures.append(f"variable {var['name']}: HTTP {status}, error={error!r}, {len(pairs)} values")
            continue
        values = [v for v, _ in pairs]
        chosen = SELECTED.get(var["name"])
        if chosen and not set(chosen) <= set(values):
            failures.append(f"variable {var['name']}: {chosen} not among {values}")
        variables[var["name"]] = {
            "values": chosen or values, "texts": [t for v, t in pairs if v in (chosen or values)],
            "is_all": chosen is None, "all_value": var.get("allValue")}
    return variables


def run(dash, name):
    variables = resolve_variables(dash)
    results = {}
    for panel in walk(dash["panels"]):
        for target in panel.get("targets") or []:
            ref = target.get("datasource") or panel.get("datasource")
            ds = datasource(ref)
            lucene = ds["type"] != "influxdb"
            q = dict(target, datasource=ds, intervalMs=10000, maxDataPoints=500)
            q["refId"] = target.get("refId") or "A"
            q["query"] = interpolate(target.get("query", ""), variables, "lucene" if lucene else "glob")
            if not lucene and re.search(r"range\(start: -\d+[sm]\)", q["query"]):
                seed_influx.seed_now()  # panels that only look at the last seconds
            status, error, frames = query(q)
            label = f"{name} panel {panel['id']} ({panel.get('title', '')})"
            if lucene and MODE == "metrics-only":
                if status == 200 and not error:
                    failures.append(f"{label}: expected an error without OpenSearch")
                continue
            if status != 200 or error or rows(frames) == 0:
                failures.append(f"{label}: HTTP {status}, error={error!r}, rows={rows(frames)}")
            results.setdefault(panel["id"], frames)  # the panel's first target
            results[(panel["id"], q["refId"])] = frames
    return results


main = json.loads((ROOT / "grafana/dashboards/opnsense.json").read_text())
suricata = json.loads((ROOT / "grafana/dashboards/opnsense-suricata.json").read_text())
found = run(main, "OPNsense")
run(suricata, "Suricata")

if MODE == "full" and not failures:
    expected = json.loads(os.environ["E2E_EXPECTED"])
    bits = numbers_by_field(found[34])  # WAN Traffic - Bits/sec for Host=fw-a
    recv, sent = statistics.median(bits.get("bytes_recv", [0])), statistics.median(bits.get("bytes_sent", [0]))
    if not (720_000 <= recv <= 880_000 and 180_000 <= sent <= 220_000):
        failures.append(f"direction/units (8fa23f1): recv {recv:.0f} bit/s, sent {sent:.0f} bit/s; "
                        "want ~800000 and ~200000 for fw-a")
    if len(found[34]) != 2:
        failures.append(f"host isolation (#33): {len(found[34])} series for Host=fw-a, want 2 (recv, sent)")
    peak = max(bits.get("bytes_recv", [0]))
    if peak > 880_000:
        failures.append(f"rate spike: WAN recv peaks at {peak:.0f} bit/s for a steady 800000 "
                        "(aggregateWindow before derivative needs timeSrc: \"_start\")")
    blocked = sum(sum(v) for v in numbers_by_field(found[111]).values())
    if blocked != expected["fw-a_block"]:
        failures.append(f"host isolation (#33): {blocked} blocked events for fw-a, want {expected['fw-a_block']}")
    countries = set(strings(found[59]))
    if not {"GB", "SE", "US", "JP", "KR"} <= countries:
        failures.append(f"map (#80): countries {sorted(countries)}")
    protocols = label_values(found[65], "protocol-name")
    if not {"tcp", "udp", "icmp", "ipv6-icmp"} <= protocols:
        failures.append(f"protocols: {sorted(protocols)}")
    # Blocked flows (112 from the internet, 113 from your networks): one row per
    # source here, so the rows must equal what send_syslog.py sent. This also
    # proves ICMP keeps its rows (dst-port missing "-") and Kind is a partition.
    for pid, origin in ((112, "internet"), (113, "networks")):
        got = {r.get("src-ip"): [r.get("filter"), r.get("dst-port"), r.get("interface"), int(r.get("Count") or 0)]
               for r in records(found[pid])}
        want = expected["flows"][origin]
        if len(records(found[pid])) != len(got) or got != want:
            failures.append(f"panel {pid} ({origin} flows): {records(found[pid])}, want {want}")
        if any(r.get("rule-number") != "96" for r in records(found[pid])):
            failures.append(f"panel {pid}: rule-number column missing or wrong")
    countries = {r.get("src-ip"): r.get("src-ip-geo-country") for r in records(found[112])}
    if countries != {"2.125.160.216": "GB", "89.160.20.112": "SE", "216.160.83.56": "US",
                     "2001:218::1": "JP", "2001:220::1": "KR"}:
        failures.append(f"panel 112: countries {countries}")
    for pid in (112, 113, 114):  # the Interface column's lookup (device -> OPNsense description)
        lookup = {r.get("name"): r.get("friendlyname") for r in records(found.get((pid, "B"), []))}
        if lookup.get("igb0") != "WAN" or lookup.get("igb1") != "LAN":
            failures.append(f"panel {pid}: interface lookup {lookup}, want igb0 -> WAN, igb1 -> LAN")
    events = records(found[114])
    sources = set(expected["flows"]["internet"]) | set(expected["flows"]["networks"])
    stamps = [e.get("timestamp") for e in events]
    if not 1 <= len(events) <= 50 or {e.get("src-ip") for e in events} - sources or stamps != sorted(stamps, reverse=True):
        failures.append(f"panel 114 (recent blocked events): {len(events)} rows, sources "
                        f"{sorted({e.get('src-ip') for e in events})}, want newest first and only {sorted(sources)}")

if MODE == "metrics-only":
    status, _ = api("/api/health")
    if status != 200:
        failures.append(f"Grafana unhealthy after OpenSearch queries: HTTP {status}")

for failure in failures:
    print(f"FAIL: {failure}", file=sys.stderr)
print(f"dashboard queries ({MODE}): {'FAILED' if failures else 'all passed'}")
sys.exit(1 if failures else 0)
