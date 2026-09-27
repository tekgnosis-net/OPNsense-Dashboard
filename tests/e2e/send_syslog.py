#!/usr/bin/env python3
"""Send synthetic RFC5424 filterlog lines to Graylog over UDP (spec §6.4).
Timestamps carry a -05:00 offset, which differs from both UTC and the e2e
stack's TZ (Australia/Brisbane), so a mishandled offset moves messages out of
the query window (Review Focus 4). Source IPs are in MaxMind's
test database: 2.125.160.216 and 81.2.69.160 GB, 89.160.20.112 SE,
216.160.83.56 US, 2001:218::1 JP, 2001:220::1 KR. igb0 is fw-a's WAN; the
igb1 (LAN) lines are hosts inside the network, one opening new connections
(SYN) and one sending late packets of closed connections (FIN-ACK).
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

PLAN = [  # host, ipver, proto, source, dport, action, count, interface, tcp flags
    ("fw-a.example.lan", "4", "tcp", "2.125.160.216", 443, "block", 30, "igb0", "S"),
    ("fw-a.example.lan", "4", "udp", "89.160.20.112", 53, "block", 10, "igb0", ""),
    ("fw-a.example.lan", "4", "icmp", "216.160.83.56", 0, "block", 5, "igb0", ""),
    ("fw-a.example.lan", "6", "tcp", "2001:218::1", 22, "block", 3, "igb0", "S"),
    ("fw-a.example.lan", "6", "ipv6-icmp", "2001:220::1", 0, "block", 2, "igb0", ""),
    ("fw-a.example.lan", "4", "tcp", "81.2.69.160", 80, "pass", 10, "igb0", "S"),
    ("fw-a.example.lan", "6", "tcp", "2001:db8:1:10::200e", 443, "block", 12, "igb1", "S"),
    ("fw-a.example.lan", "4", "tcp", "192.168.1.50", 443, "block", 6, "igb1", "FA"),
    ("fw-b.example.lan", "4", "tcp", "81.2.69.160", 3389, "block", 7, "igb0", "S"),
]
WAN = {"igb0"}


def kind(proto, flags):
    """The dashboard's Kind column: new = SYN without ACK."""
    if proto != "tcp":
        return "Not TCP"
    return "New connection" if flags.startswith("S") and "A" not in flags else "Late packet"


sock =socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
port = int(os.environ["SYSLOG_PORT"])
tz = timezone(timedelta(hours=-5))
seq = 0
for host, ipver, proto, src, dport, action, count, iface, flags in PLAN:
    for i in range(count):
        seq += 1
        when = datetime.now(tz) - timedelta(seconds=count - i)
        line = filterlog.line(ipver, proto, host=host, when=when, seq=seq, src=src, dport=dport, action=action,
                              iface=iface, tcp_flags=flags)
        sock.sendto(line.encode(), ("127.0.0.1", port))
        time.sleep(0.01)

print(json.dumps({
    "total": sum(p[6] for p in PLAN),
    "fw-a_block": sum(p[6] for p in PLAN if p[0].startswith("fw-a") and p[5] == "block"),
    "fw-b_block": sum(p[6] for p in PLAN if p[0].startswith("fw-b") and p[5] == "block"),
    # fw-a's blocked flows per origin: {source: [kind, port or "-", interface, count]}
    "flows": {origin: {p[3]: [kind(p[2], p[8]), str(p[4]) if p[2] in ("tcp", "udp") else "-", p[7], p[6]]
                       for p in PLAN if p[0].startswith("fw-a") and p[5] == "block" and (p[7] in WAN) == wan}
              for origin, wan in (("internet", True), ("networks", False))},
}))
