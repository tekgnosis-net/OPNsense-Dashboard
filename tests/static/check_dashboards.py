#!/usr/bin/env python3
"""Dashboard invariants (spec §5.4, §5.5, §6.3). Each message names the
upstream issue or commit the rule protects."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DASH = ROOT / "grafana/dashboards"
DS_VARS = {"${dataSource}", "${ESdataSource}"}
BUILTIN_DS = {"-- Grafana --", "-- Mixed --", "-- Dashboard --", "grafana"}
HOST_FLUX = "r.host =~ /^${Host:regex}$/"
errors = []


def need(condition, message):
    if not condition:
        errors.append(message)


def walk(panels):
    for panel in panels:
        yield panel
        yield from walk(panel.get("panels", []))


def uid(ref):
    return ref.get("uid") if isinstance(ref, dict) else ref


def text(obj):
    query = obj.get("query")
    if isinstance(query, dict):
        query = query.get("query")
    return query if isinstance(query, str) else ""


def load(name, want_uid, want_title):
    dash = json.loads((DASH / name).read_text())
    need(dash.get("uid") == want_uid and dash.get("title") == want_title,
         f"{name}: uid/title must stay {want_uid!r}/{want_title!r}")
    return dash, {p["id"]: p for p in walk(dash["panels"])}, {v["name"]: v for v in dash["templating"]["list"]}


main, P, V = load("opnsense.json", "suTmk8c7k", "OPNsense")
suricata, SP, _ = load("opnsense-suricata.json", "94raP_-7z", "OPNsense Suricata")

# Both dashboards: migrated panel types, datasource variables (PR #16), v.defaultBucket (#77, PR #44).
for name, dash in (("opnsense.json", main), ("opnsense-suricata.json", suricata)):
    for p in walk(dash["panels"]):
        need(p["type"] not in ("graph", "grafana-worldmap-panel", "singlestat", "table-old"),
             f"{name} panel {p['id']}: legacy panel type {p['type']}")
        for ref in [p.get("datasource")] + [t.get("datasource") for t in p.get("targets") or []]:
            need(ref is None or uid(ref) in DS_VARS | BUILTIN_DS,
                 f"{name} panel {p['id']}: datasource {uid(ref)!r} is not a variable (PR #16)")
        for t in p.get("targets") or []:
            q = text(t)
            need(not re.search(r'from\(bucket:\s*"', q), f"{name} panel {p['id']}: literal bucket (#77, PR #44)")
            need("from(" not in q or "from(bucket: v.defaultBucket)" in q,
                 f"{name} panel {p['id']}: Flux must read from(bucket: v.defaultBucket)")
    for v in dash["templating"]["list"]:
        need(v["type"] != "query" or uid(v.get("datasource")) in DS_VARS,
             f"{name} variable {v['name']}: datasource is not a variable (PR #16)")

# Main dashboard: every query is filtered by Host (#33, 8fa23f1).
for p in walk(main["panels"]):
    for t in p.get("targets") or []:
        q = text(t)
        if uid(t.get("datasource") or p.get("datasource")) == "${ESdataSource}":
            need("source:$Host" in q, f"panel {p['id']}: Lucene query lacks source:$Host (#33)")
            need(not re.search(r"\s(and|or|not)\s", q), f"panel {p['id']}: lowercase Lucene operator: {q!r}")
        elif "from(" in q:
            need(HOST_FLUX in q, f"panel {p['id']}: Flux query lacks the Host filter (#33)")
for v in V.values():
    if v["type"] != "query" or v["name"] == "Host":
        continue
    q = text(v)
    if uid(v.get("datasource")) == "${ESdataSource}":
        need("source:$Host" in q, f"variable {v['name']}: terms query lacks source:$Host (#33)")
    else:
        need(HOST_FLUX in q, f"variable {v['name']}: Flux query lacks the Host filter (#33)")

# Variables (#89, D8, #80).
need(V["ESdataSource"].get("query") == "grafana-opensearch-datasource",
     "ESdataSource must select grafana-opensearch-datasource instances")
need('_measurement == "system"' in text(V["Host"]), "Host must be built from the system measurement (#89)")
for n in ("WAN", "LAN", "iface"):
    need(V[n]["type"] == "query" and "friendlyname" in text(V[n]) and "(?<text>" in (V[n].get("regex") or ""),
         f"{n} must list device names with the OPNsense description as display text (D8)")
need("=~ /^WAN/" in text(V["WAN"]), "WAN must be interfaces described as WAN* (D8)")
need("!~ /^WAN/" in text(V["LAN"]), "LAN must be every interface not described as WAN* (D8)")
need("${WAN:text}" in P[30]["title"] and "${LAN:text}" in P[48]["title"], "WAN/LAN rows must show the description (#80)")

# Panel fixes (§3.3).
for pid in (28, 52):
    need('"ip4_subnet", "mac_address"' in text(P[pid]["targets"][0]), f"panel {pid}: missing comma in keep()")
for pid in (26, 38):
    need("aggregateWindow(every: v.windowPeriod, fn: mean" in text(P[pid]["targets"][0]),
         f"panel {pid}: gateway RTT/loss must be averaged per v.windowPeriod (#79)")
defaults20 = P[20]["fieldConfig"]["defaults"]
need(defaults20.get("noValue") == "0" and "shell" in P[20].get("description", ""),
     "Active Users must show 0 when empty and say it counts shell sessions (#42, #32)")
need("DEGRADED" in json.dumps(P[46]["fieldConfig"]["defaults"].get("mappings", [])),
     "Gateway Summary must map status 2 to DEGRADED")
geo = P[59]
aggs = geo["targets"][0].get("bucketAggs", [])
need(geo["type"] == "geomap" and [a.get("type") for a in aggs] == ["terms"]
     and aggs[0].get("field") == "src-ip-geo-country",
     "firewall map must be a Geomap over a terms aggregation on src-ip-geo-country (#80)")
need('action:"block"' in text(geo["targets"][0]), "firewall map must count blocked events only (#80)")
# The worldmap migration adds a "reduce" transform, which drops the country
# column the Geomap lookup needs; the terms query already yields one row per country.
need(not any(tr.get("id") == "reduce" for tr in geo.get("transformations", [])),
     "firewall map must not reduce its frame (the country column is the lookup key)")
need("elastic" not in (V["ESdataSource"].get("label") or "").lower(),
     "ESdataSource is labelled Elasticsearch; the stack uses OpenSearch")

# Traffic direction and units (8fa23f1).
for pid in (34, 36, 40, 42, 49, 50, 51, 53):
    renames = {}
    for tr in P[pid].get("transformations", []):
        if tr.get("id") == "organize":
            renames.update(tr["options"].get("renameByName", {}))
    need(any(k.endswith("_recv") for k in renames) and any(k.endswith("_sent") for k in renames),
         f"panel {pid}: recv/sent renames missing (8fa23f1)")
    for key, label in renames.items():
        need(not key.endswith("_recv") or "Recv" in label, f"panel {pid}: {key} shown as {label!r} (8fa23f1)")
        need(not key.endswith("_sent") or "Sent" in label, f"panel {pid}: {key} shown as {label!r} (8fa23f1)")
for pid in (34, 36, 49, 51):
    need("* 8.0" in text(P[pid]["targets"][0]), f"panel {pid}: bits must be bytes * 8.0 (8fa23f1)")
for pid in (40, 50):
    need("difference(nonNegative: true)" in text(P[pid]["targets"][0]), f"panel {pid}: monthly total must use difference(nonNegative: true)")

# Rate graphs: aggregateWindow stamps windows with _stop by default, and the last
# window is truncated at "now", so a following derivative() divides a full
# window's increase by a few seconds and draws a false spike at the right edge.
for name, dash in (("opnsense.json", main), ("opnsense-suricata.json", suricata)):
    for p in walk(dash["panels"]):
        for t in p.get("targets") or []:
            q = text(t)
            for window in re.finditer(r"aggregateWindow\([^)]*\)", q):
                if "derivative(" in q[window.end():] and 'timeSrc: "_start"' not in window.group(0):
                    errors.append(f"{name} panel {p['id']}: aggregateWindow before derivative needs "
                                  f'timeSrc: "_start" (right-edge rate spike)')

# Per-interface summary tables need room for the header and one row (final review #8).
for pid in (28, 52):
    need(P[pid]["gridPos"]["h"] >= 4, f"panel {pid}: Interface Summary is clipped (gridPos.h < 4)")

# Light mode stays readable (#25).
for pid in (28, 32, 46, 52):
    steps = P[pid]["fieldConfig"]["defaults"].get("thresholds", {}).get("steps", [])
    need(bool(steps) and steps[0].get("color") == "text", f"panel {pid}: base threshold colour must be 'text' (#25)")

# Firewall row: a blocked source is shown with what it tried and which way it
# came. The old "Top IP Blocked" stat showed one address and nothing else, so a
# LAN host failing outbound looked like an attacker. filterlog's direction is
# relative to the interface (nearly every block is "in"), so origin comes from
# the interface: WAN interfaces = from the internet, the rest = your networks.
KIND = {  # from filterlog tcp-flags; the events table's value mappings mirror it
    "New connection": "tcp-flags:S* AND NOT tcp-flags:*A*",
    "Late packet": "_exists_:tcp-flags AND NOT (tcp-flags:S* AND NOT tcp-flags:*A*)",
    "Not TCP": "NOT _exists_:tcp-flags",
}
flows = {}
for p in walk(main["panels"]):
    for t in p.get("targets") or []:
        aggs = t.get("bucketAggs") or []
        terms = {a.get("field"): a for a in aggs if a.get("type") == "terms"}
        if "src-ip" not in terms:
            continue
        pid, q = p["id"], text(t)
        flows[pid] = q
        need(p["type"] == "table", f"panel {pid}: a blocked-source ranking must be a table with its context")
        for field in ("interface", "protocol-name", "dst-port", "rule-number"):
            need(field in terms, f"panel {pid}: blocked flows must also group by {field}")
        kinds = [a for a in aggs if a.get("type") == "filters"]
        need(bool(kinds) and {f.get("label"): f.get("query") for f in kinds[0]["settings"]["filters"]} == KIND,
             f"panel {pid}: Kind must be the filters aggregation {KIND}")
        # The plugin reads leaf buckets as an array; filters buckets are a map and vanish there.
        need(bool(aggs) and aggs[-1].get("type") == "terms", f"panel {pid}: the last bucket aggregation must be terms")
        need((terms.get("dst-port") or {}).get("settings", {}).get("missing") == "-",
             f"panel {pid}: dst-port needs missing \"-\" or ICMP blocks drop out of the counts")
        need("$dst_port" not in q, f"panel {pid}: $dst_port's All value (*) drops ICMP blocks")
        need("src-ip:$src_ip" in q, f"panel {pid}: must follow the $src_ip drill-down")
        links = json.dumps(p["fieldConfig"])
        need("var-src_ip=${__value.raw}" in links and "${Host:queryparam}" in links,
             f"panel {pid}: clicking a source must set $src_ip and keep the Host")
need(sorted("NOT interface:$WAN" in q for q in flows.values()) == [False, True]
     and all("interface:$WAN" in q for q in flows.values()),
     "Firewall row needs one flows table for interface:$WAN and one for NOT interface:$WAN")
events = [p for p in walk(main["panels"])
          if any((t.get("metrics") or [{}])[0].get("type") == "raw_data" for t in p.get("targets") or [])]
need(len(events) == 1 and events[0]["type"] == "table", "Firewall row needs one Recent Blocked Events table (raw data)")
if events:
    q = text(events[0]["targets"][0])
    need('action:"block"' in q and "src-ip:$src_ip" in q and "$dst_port" not in q,
         "Recent Blocked Events: blocked only, follow $src_ip, no $dst_port")
    mapped = json.dumps(events[0]["fieldConfig"])
    need(all(k in mapped for k in KIND) and "^(S[^A]*)$" in mapped,
         "Recent Blocked Events: tcp-flags must map to the same Kind names (new = S without A)")
# Their Interface column shows the OPNsense description (LAN, VLAN10Users), not the
# device (igc1): a Flux lookup of the interface measurement becomes value mappings
# ("Config from query results"), which must run before sortBy/limit/organize.
for p in [P[pid] for pid in flows] + events:
    lookups = [t for t in p.get("targets") or []
               if '_measurement == "interface"' in text(t) and "friendlyname" in text(t)]
    first = (p.get("transformations") or [{}])[0]
    opts = first.get("options", {})
    need(uid(p.get("datasource")) == "-- Mixed --" and len(lookups) == 1,
         f"panel {p['id']}: needs a Mixed datasource with one Flux lookup of interface descriptions")
    need(first.get("id") == "configFromData" and bool(lookups)
         and opts.get("configRefId") == lookups[0].get("refId")
         and opts.get("applyTo") == {"id": "byName", "options": "interface"}
         and {(m.get("fieldName"), m.get("handlerKey")) for m in opts.get("mappings", [])}
         == {("name", "mappings.value"), ("friendlyname", "mappings.text")},
         f"panel {p['id']}: first transformation must map interface via the lookup (Config from query results)")
need(not any(p["type"] == "stat" and "src-ip" in json.dumps(p.get("targets")) and "terms" in json.dumps(p.get("targets"))
             for p in walk(main["panels"])), "a stat panel ranking source IPs hides their context")

# Suricata alert log columns (#22).
q241 = text(SP[241]["targets"][0])
need("alert_action" in q241 and "alert_signature_id" in q241, "Suricata Alert Logs must include action and SID (#22)")

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
if not errors:
    print("ok: dashboards")
sys.exit(1 if errors else 0)
