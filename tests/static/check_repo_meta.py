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
for name in ("bug_report.yml", "enhancement.yml", "question.yml", "config.yml"):
    need(f".github/ISSUE_TEMPLATE/{name}")
need(".github/ISSUE_TEMPLATE/config.yml", "blank_issues_enabled: false")
need(".github/pull_request_template.md", "tests/run-static.sh", "tests/run-unit.sh")
need("CLAUDE.md", "tests/run-static.sh", "opnsense/bin/telegraf_pfifgw.php")

need("docs/opnsense.md", "Run as Root", "RFC5424", "Intrusion Detection Alerts",
     "telegraf --test", "opnsense/ansible", "Thermal Sensors")

need("CHANGELOG.md", "## [2.0.0]", "### Planned (2.1)", "CARP", "bsmithio/OPNsense-Dashboard")
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
