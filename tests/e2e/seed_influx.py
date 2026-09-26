#!/usr/bin/env python3
"""Seed InfluxDB with synthetic metrics for two firewalls (spec §6.4).

  seed_influx.py history        30 min of points 10 s apart ending now, plus
                                48 h of hourly net counters (monthly panels)
  seed_influx.py live SECONDS   a fresh point every 5 s for SECONDS

The interface, gateways and temperature lines are the unit tests' expected
collector output, so the dashboards are tested against what the collectors
print; the host tag is added here, as Telegraf does. fw-a's WAN receives
100 000 B/s and sends 25 000 B/s; fw-b is five times that (host isolation).
Env: ROOT, INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_ADMIN_TOKEN.
"""
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(os.environ["ROOT"])
HOSTS = {"fw-a.example.lan": 1, "fw-b.example.lan": 5}
RECV_BPS, SENT_BPS = 100_000, 25_000
EPOCH = 1_700_000_000


def golden(path):
    return [line for line in (ROOT / path).read_text().splitlines() if line]


COLLECTED = golden("tests/php/cases/normal/expected.txt") + golden("tests/shell/cases/intel/expected.txt")


def with_host(line, host):
    measurement, rest = line.split(",", 1)
    return f"{measurement},host={host},{rest}"


def net_points(ts):
    out = []
    for host, k in HOSTS.items():
        elapsed = ts - EPOCH
        for iface, share in (("igb0", 1.0), ("igb1", 0.5), ("igb2", 0.1)):
            recv = int(RECV_BPS * k * share * elapsed)
            sent = int(SENT_BPS * k * share * elapsed)
            out.append(f"net,host={host},interface={iface} bytes_recv={recv}i,bytes_sent={sent}i,"
                       f"packets_recv={recv // 1000}i,packets_sent={sent // 1000}i {ts}")
    return out


def points(ts):
    out = net_points(ts)
    for host, k in HOSTS.items():
        h = f"host={host}"
        out += [f"{with_host(line, host)} {ts}" for line in COLLECTED]
        users = "" if ts % 300 == 0 else "n_users=2i,"  # some points lack n_users (#42)
        out.append(f"system,{h} {users}load1=0.{k}5,load5=0.{k}4,load15=0.{k}3,n_cpus=4i,"
                   f'uptime={ts - EPOCH}i,uptime_format="12 days,  3:04" {ts}')
        for cpu, idle in (("cpu-total", 90.0), ("cpu0", 88.0), ("cpu1", 92.0)):
            out.append(f"cpu,{h},cpu={cpu} usage_idle={idle - k},usage_user={5 + k},usage_system=3 {ts}")
        out.append(f"mem,{h} used_percent={40 + k}.5,total=8589934592i,used=3500000000i {ts}")
        out.append(f"disk,{h},device=ada0p2,path=/,fstype=ufs used_percent={20 + k}.0,free=100000000000i {ts}")
        out.append(f"processes,{h} running=1i,sleeping=80i,idle=10i,wait=0i,blocked=0i,zombies=0i,total=91i {ts}")
        out.append(f"pf,{h} match={1000 * k + ts % 1000}i,state-insert=500i,state-mismatch=0i,entries=120i {ts}")
        if ts % 60 == 0:
            out.append(f"suricata,{h},event_type=alert,src_ip=2.125.160.216,src_port=51234,dest_ip=203.0.113.45,"
                       f"dest_port=1433,path=/var/log/suricata/eve.json "
                       f'alert_signature="ET SCAN Suspicious inbound to MSSQL port 1433",'
                       f'alert_category="Potentially Bad Traffic",alert_action="allowed",'
                       f'alert_signature_id="2010935",proto="TCP" {ts}')
    return out


def write(lines):
    query = urllib.parse.urlencode({"org": os.environ["INFLUXDB_ORG"],
                                    "bucket": os.environ["INFLUXDB_BUCKET"], "precision": "s"})
    for start in range(0, len(lines), 5000):
        request = urllib.request.Request(
            f"{os.environ['INFLUXDB_URL']}/api/v2/write?{query}",
            data="\n".join(lines[start:start + 5000]).encode(), method="POST",
            headers={"Authorization": f"Token {os.environ['INFLUXDB_ADMIN_TOKEN']}",
                     "Content-Type": "text/plain; charset=utf-8"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 204:
                sys.exit(f"InfluxDB write failed: HTTP {response.status}")


def seed_history():
    now = int(time.time()) // 10 * 10
    lines = []
    for ts in range(now - 48 * 3600, now - 1800, 3600):
        lines += net_points(ts)
    for ts in range(now - 1800, now + 1, 10):
        lines += points(ts)
    write(lines)


def seed_now():
    # On the 10 s grid, like Telegraf with round_interval; off-grid points would
    # make the rate panels' last-per-window derivative jitter.
    write(points(int(time.time()) // 10 * 10))


if __name__ == "__main__":
    if sys.argv[1:2] == ["history"]:
        seed_history()
    elif sys.argv[1:2] == ["live"]:
        deadline = time.time() + int(sys.argv[2])
        while time.time() < deadline:
            seed_now()
            time.sleep(5)
    else:
        sys.exit("usage: seed_influx.py history | live SECONDS")
