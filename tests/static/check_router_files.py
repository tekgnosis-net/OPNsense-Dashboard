#!/usr/bin/env python3
"""Router-side invariants from upstream issues (spec §6.3)."""
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
errors = []

# OPNsense removed or deprecated these; the old script broke on each (#57, #61, #78, #82).
plugin = (ROOT / "opnsense/bin/telegraf_pfifgw.php").read_text()
for api in ("get_interfaces_info", "find_interface_network", "return_gateways_status",
            "convert_seconds_to_hms", "php-cgi"):
    if api in plugin:
        errors.append(f"telegraf_pfifgw.php uses removed API or binary: {api}")
if not plugin.startswith("#!/usr/local/bin/php\n"):
    errors.append("telegraf_pfifgw.php must start with #!/usr/local/bin/php")

temperature = (ROOT / "opnsense/bin/telegraf_temperature.sh").read_text()
if not temperature.startswith("#!/bin/sh\n"):  # #4: a blank first line broke the shebang
    errors.append("telegraf_temperature.sh must start with #!/bin/sh")

# Exactly our two scripts, run directly as root (no sudo), with a timeout long
# enough for routers with many gateways (#4, #83, PR #54).
conf = tomllib.loads((ROOT / "opnsense/telegraf.d/custom.conf").read_text())
execs = conf.get("inputs", {}).get("exec", [])
want = ["/usr/local/bin/telegraf_pfifgw.php", "/bin/sh /usr/local/bin/telegraf_temperature.sh"]
if len(execs) != 1:
    errors.append("custom.conf must define exactly one [[inputs.exec]]")
elif execs[0].get("commands") != want or execs[0].get("timeout") != "10s" \
        or execs[0].get("data_format") != "influx":
    errors.append(f"custom.conf must run {want} with timeout \"10s\" and data_format \"influx\"")

# Every task that edits sudoers validates it with visudo (PR #36); files come
# from the checkout, never downloaded.
playbook = (ROOT / "opnsense/ansible/playbook.yml").read_text()
for task in re.split(r"\n(?=\s*- name: )", playbook):
    if "lineinfile" in task and "sudoers" in task \
            and not re.search(r"validate:\s*['\"]?/usr/local/sbin/visudo -cf %s", task):
        errors.append(f"sudoers task without visudo validation: {task.strip().splitlines()[0]}")
if "get_url" in playbook or "raw.githubusercontent.com" in playbook:
    errors.append("playbook must copy files from the checkout, not download them")

for legacy in ("config/suricata/custom.yaml", "config/suricata/suricata.conf"):
    if (ROOT / legacy).exists():
        errors.append(f"{legacy} is obsolete since OPNsense 26.1; use the Intrusion Detection Alerts input")

for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
if not errors:
    print("ok: router files")
sys.exit(1 if errors else 0)
