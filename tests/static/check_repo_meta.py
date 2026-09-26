#!/usr/bin/env python3
"""Repository metadata required by the v2 de-fork (spec §5.1)."""
import pathlib
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

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
print("ok: repository metadata present" if not errors else "")
sys.exit(1 if errors else 0)
