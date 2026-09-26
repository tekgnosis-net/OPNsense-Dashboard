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

# Light mode stays readable (#25).
for pid in (28, 32, 46, 52):
    steps = P[pid]["fieldConfig"]["defaults"].get("thresholds", {}).get("steps", [])
    need(bool(steps) and steps[0].get("color") == "text", f"panel {pid}: base threshold colour must be 'text' (#25)")

# Suricata alert log columns (#22).
q241 = text(SP[241]["targets"][0])
need("alert_action" in q241 and "alert_signature_id" in q241, "Suricata Alert Logs must include action and SID (#22)")

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
if not errors:
    print("ok: dashboards")
sys.exit(1 if errors else 0)
