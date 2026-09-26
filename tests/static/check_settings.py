#!/usr/bin/env python3
"""Every setting in .env.example has a row in the README settings table
("| `NAME` | default | ... |"), and the table lists nothing that does not exist."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
env = {m.group(1) for m in re.finditer(r"^([A-Z][A-Z0-9_]*)=", (ROOT / ".env.example").read_text(), re.M)}
readme = (ROOT / "README.md").read_text()
table = set(re.findall(r"^\| `([A-Z][A-Z0-9_]*)` \|", readme, re.M))
errors = [f"{name} is in .env.example but not in the README settings table" for name in sorted(env - table)]
errors += [f"{name} is in the README settings table but not in .env.example" for name in sorted(table - env)]
for error in errors:
    print(f"FAIL: {error}", file=sys.stderr)
if not errors:
    print(f"ok: {len(env)} settings documented")
sys.exit(1 if errors else 0)
