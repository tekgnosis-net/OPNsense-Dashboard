#!/usr/bin/env python3
"""Send synthetic RFC5424 filterlog lines to Graylog over UDP (spec §6.4).
Timestamps carry a -05:00 offset, which differs from both UTC and the e2e
stack's TZ (Australia/Brisbane), so a mishandled offset moves messages out of
the query window (Review Focus 4). Source IPs are in MaxMind's
test database: 2.125.160.216 and 81.2.69.160 GB, 89.160.20.112 SE,
216.160.83.56 US, 2001:218::1 JP, 2001:220::1 KR.
Prints the expected counts as JSON. Env: ROOT, SYSLOG_PORT."""
import json
import os
import pathlib
import socket
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(os.environ["ROOT"]) / "tests/lib"))
import filterlog  # noqa: E402

PLAN = [  # host, ipver, proto, source, dport, action, count
    ("fw-a.example.lan", "4", "tcp", "2.125.160.216", 443, "block", 30),
    ("fw-a.example.lan", "4", "udp", "89.160.20.112", 53, "block", 10),
    ("fw-a.example.lan", "4", "icmp", "216.160.83.56", 0, "block", 5),
    ("fw-a.example.lan", "6", "tcp", "2001:218::1", 22, "block", 3),
    ("fw-a.example.lan", "6", "ipv6-icmp", "2001:220::1", 0, "block", 2),
    ("fw-a.example.lan", "4", "tcp", "81.2.69.160", 80, "pass", 10),
    ("fw-b.example.lan", "4", "tcp", "81.2.69.160", 3389, "block", 7),
]

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
port = int(os.environ["SYSLOG_PORT"])
tz = timezone(timedelta(hours=-5))
seq = 0
for host, ipver, proto, src, dport, action, count in PLAN:
    for i in range(count):
        seq += 1
        when = datetime.now(tz) - timedelta(seconds=count - i)
        line = filterlog.line(ipver, proto, host=host, when=when, seq=seq, src=src, dport=dport, action=action)
        sock.sendto(line.encode(), ("127.0.0.1", port))
        time.sleep(0.01)

print(json.dumps({
    "total": sum(p[6] for p in PLAN),
    "fw-a_block": sum(p[6] for p in PLAN if p[0].startswith("fw-a") and p[5] == "block"),
    "fw-b_block": sum(p[6] for p in PLAN if p[0].startswith("fw-b") and p[5] == "block"),
}))
