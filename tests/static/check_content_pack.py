#!/usr/bin/env python3
"""Graylog content pack invariants (spec §5.2): each synthetic filterlog line
is claimed by exactly one extractor and splits into exactly that extractor's
columns; headers match filterlog 0.9; the GeoIP rule sets only the country;
the pack points at this project."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/lib"))
import filterlog  # noqa: E402

pack = json.loads((ROOT / "graylog/OPNsense-pack.json").read_text())
errors = []


def val(node):
    return node["@value"] if isinstance(node, dict) and "@value" in node else node


def java_regex(pattern):
    # Java accepts inline flags after "^"; Python 3.11+ needs them first.
    return re.compile(pattern.replace("^(?i)", "(?i)^", 1))


def entity(kind):
    found = [e["data"] for e in pack["entities"] if e["type"]["name"] == kind]
    if len(found) != 1:
        errors.append(f"expected one {kind} entity, found {len(found)}")
    return found[0] if found else {}


if pack.get("vendor") != "tekgnosis-net" or not pack.get("url", "").endswith("tekgnosis-net/OPNsense-Dashboard"):
    errors.append("pack vendor/url must point at tekgnosis-net/OPNsense-Dashboard")

syslog_input = entity("input")
cfg = syslog_input.get("configuration", {})
if val(cfg.get("port")) != 1514 or val(cfg.get("store_full_message")) is not True:
    errors.append("syslog input must listen on 1514 and store full_message")

extractors = [{
    "title": val(x["title"]),
    "condition": java_regex(val(x["condition_value"])),
    "regex": java_regex(val(x["configuration"]["regex_value"])),
    "header": val(x["converters"][0]["configuration"]["column_header"]),
} for x in syslog_input.get("extractors", [])]
if len(extractors) != 6:
    errors.append(f"expected 6 extractors, found {len(extractors)}")

for (ipver, proto), header in filterlog.HEADERS.items():
    raw = filterlog.line(ipver, proto)
    matches = [x for x in extractors if x["condition"].search(raw)]
    if len(matches) != 1:
        errors.append(f"IPv{ipver} {proto}: {len(matches)} extractors match, want 1 "
                      f"({[m['title'] for m in matches]})")
        continue
    x = matches[0]
    if x["header"] != header:
        errors.append(f"{x['title']}: header\n    is   {x['header']}\n    want {header}")
    found = x["regex"].search(raw)
    columns = found.group(1).split(",") if found else []
    if len(columns) != len(x["header"].split(",")):
        errors.append(f"{x['title']}: filterlog sends {len(columns)} columns, header has "
                      f"{len(x['header'].split(','))}")

rule = val(entity("pipeline_rule").get("source", ""))
if 'set_field("src-ip-geo-country"' not in rule or "geo-location" in rule or "geo-city" in rule:
    errors.append("GeoIP rule must set only src-ip-geo-country (GeoLite2-Country has no location/city)")

adapter = entity("lookup_adapter").get("configuration", {})
if val(adapter.get("path")) != "/usr/share/graylog/geoip/GeoLite2-Country.mmdb" \
        or val(adapter.get("database_type")) != "MAXMIND_COUNTRY":
    errors.append("GeoIP adapter must read /usr/share/graylog/geoip/GeoLite2-Country.mmdb as MAXMIND_COUNTRY")

stream = entity("stream")
rules = [(val(r["field"]), val(r["type"]), val(r["value"])) for r in stream.get("stream_rules", [])]
if rules != [("application_name", "CONTAINS", "filterlog")]:
    errors.append(f"stream rule must be application_name CONTAINS filterlog, got {rules}")

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
if not errors:
    print("ok: content pack")
sys.exit(1 if errors else 0)
