#!/usr/bin/env python3
"""Repository metadata required by the v2 de-fork (spec §5.1)."""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
errors = []


def need(path, *needles):
    p = ROOT / path
    if not p.is_file():
        errors.append(f"missing {path}")
        return
    text = p.read_text()
    for needle in needles:
        if needle not in text:
            errors.append(f"{path}: expected to mention {needle!r}")


need("LICENSE", "MIT License", "tekgnosis-net")
need("NOTICE", "VictorRobellini/pfSense-Dashboard", "bsmithio/OPNsense-Dashboard",
     "without a license", "48119ee")
need("README.md", "## Credits and history", "NOTICE", "LICENSE", "docs/opnsense.md", "docs/stack.md")
for name in ("bug_report.yml", "enhancement.yml", "config.yml"):
    need(f".github/ISSUE_TEMPLATE/{name}")
# Questions go to Discussions Q&A, where answers can be marked and searched,
# not to the issue tracker.
QA = "https://github.com/tekgnosis-net/OPNsense-Dashboard/discussions/categories/q-a"
need(".github/ISSUE_TEMPLATE/config.yml", "blank_issues_enabled: false", QA)
need("README.md", QA)
if (ROOT / ".github/ISSUE_TEMPLATE/question.yml").exists():
    errors.append("question.yml: questions go to Discussions Q&A (contact link in config.yml)")
need(".github/pull_request_template.md", "tests/run-static.sh", "tests/run-unit.sh")
need("CLAUDE.md", "tests/run-static.sh", "opnsense/bin/telegraf_pfifgw.php")

need("docs/opnsense.md", "Run as Root", "RFC5424", "Intrusion Detection Alerts",
     "telegraf --test", "opnsense/ansible", "Thermal Sensors")

need("CHANGELOG.md", "## [2.0.0]", "### Planned (2.1)", "CARP", "bsmithio/OPNsense-Dashboard")
# Each released version heading links to its GitHub release (tag vX.Y.Z).
changelog = (ROOT / "CHANGELOG.md").read_text()
for version in re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M):
    link = f"[{version}]: https://github.com/tekgnosis-net/OPNsense-Dashboard/releases/tag/v{version}"
    if link not in changelog:
        errors.append(f"CHANGELOG.md: missing link definition {link}")
need("docs/troubleshooting.md", "RFC5424", "Run as Root", "AVX", "GRAYLOG_JOURNAL_MAX_SIZE",
     "pluginctl -r return_gateways_status", "reset-admin-password", "visudo", "Index not found")
need("README.md", "## Supported versions", "## How it works", "```mermaid", "CHANGELOG.md",
     "docs/images/opnsense.png")
need(".github/workflows/ci.yml", "tests/run-static.sh", "tests/run-unit.sh", "tests/e2e/run.sh")

# Minimum lengths the services enforce at first start (InfluxDB onboarding;
# Graylog Configuration.validatePasswordSecret), documented where users set them.
need(".env.example", "8-72 characters", "at least 16 characters")
need("docs/troubleshooting.md", "passwords must be between 8 and 72", "password_secret",
     "MongoDB cannot start", "mongo:7.0")
# Hosts that already run another Grafana/InfluxDB/Graylog take the default ports;
# the fix is the *_PORT settings (and GRAYLOG_EXTERNAL_URI to match GRAYLOG_PORT).
need("docs/troubleshooting.md", "port is already allocated", "GRAFANA_PORT", "INFLUXDB_PORT",
     "GRAYLOG_EXTERNAL_URI")
# os-telegraf's IDS input stores all of eve.json; HTTP/TLS logging floods InfluxDB.
need("docs/opnsense.md", "HTTP", "TLS", "suricata-dashboard-is-slow-or-times-out")
need("docs/troubleshooting.md", "## Suricata dashboard is slow or times out", 'event_type="tls"')

def forbid(path, pattern, why):
    text = (ROOT / path).read_text()
    if re.search(pattern, text, re.M):
        errors.append(f"{path}: {why}")


# The router side has not run on a live OPNsense yet (final review #4, spec §6.6).
forbid("README.md", r"\(tested", "claims OPNsense testing that has not happened yet")
forbid("docs/opnsense.md", r"^Tested with", "claims OPNsense testing that has not happened yet")
# The influx CLI in the container is already configured; host variables would be empty
# and put the token in shell history (final review #12a).
forbid("docs/troubleshooting.md", r'--token "\$INFLUXDB_ADMIN_TOKEN"', "influx delete must not use host variables")
# No build artefacts in the repository (final review #6).
tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
for name in tracked:
    if "__pycache__/" in name or name.endswith(".pyc"):
        errors.append(f"tracked build artefact: {name}")

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
print("ok: repository metadata present" if not errors else "")
sys.exit(1 if errors else 0)
