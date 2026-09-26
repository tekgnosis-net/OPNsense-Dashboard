"""Synthetic OPNsense filterlog syslog lines (filterlog 0.9, OPNsense 26.7.4).

Field layout from opnsense/ports opnsense/filterlog/files (description.txt,
print-ip.c, print-ip6.c, print-tcp.c):
  common: rulenr, subrulenr, anchor, label (rule id), interface, reason,
          action, dir, ipversion
  IPv4:   tos, ecn, ttl, id, offset, flags, protonum, protoname, length, src, dst
  IPv6:   class, flow, hoplimit, protoname, protonum, length, src, dst
  TCP:    srcport, dstport, datalen, flags, seq, ack, window, urg, options
  UDP:    srcport, dstport, datalen
  other:  one field, "datalength=<n>"
Protocol names come from FreeBSD /etc/protocols: 58 is "ipv6-icmp".
"""
from datetime import datetime

COMMON = "rule-number,sub-rule-number,anchor,rid,interface,reason,action,direction,ip-version"
IPV4 = "tos,ecn,ttl,id,offset,ip-flags,protocol-id,protocol-name,length,src-ip,dst-ip"
IPV6 = "class,flow-label,hop-limit,protocol-name,protocol-id,length,src-ip,dst-ip"
TCP = "src-port,dst-port,datalength,tcp-flags,sequence,ack,window,urg,tcp-options"
UDP = "src-port,dst-port,datalength"
OTHER = "datalength"

HEADERS = {
    ("4", "tcp"): f"{COMMON},{IPV4},{TCP}",
    ("4", "udp"): f"{COMMON},{IPV4},{UDP}",
    ("4", "icmp"): f"{COMMON},{IPV4},{OTHER}",
    ("6", "tcp"): f"{COMMON},{IPV6},{TCP}",
    ("6", "udp"): f"{COMMON},{IPV6},{UDP}",
    ("6", "ipv6-icmp"): f"{COMMON},{IPV6},{OTHER}",
}
PROTOCOLS = list(HEADERS)
PROTO_NUMBER = {"tcp": 6, "udp": 17, "icmp": 1, "ipv6-icmp": 58}
RULE_ID = "fae559338f65e11c53669fc3642c93c2"


def fields(ipver, proto, *, iface="igb0", action="block", direction="in",
           src=None, dst=None, sport=51234, dport=443):
    src = src or ("2.125.160.216" if ipver == "4" else "2001:218::1")
    dst = dst or ("203.0.113.45" if ipver == "4" else "2001:db8:0:1::1a2b")
    head = ["96", "", "", RULE_ID, iface, "match", action, direction, ipver]
    if ipver == "4":
        ip = ["0x0", "", "64", "12345", "0", "DF", str(PROTO_NUMBER[proto]), proto, "60", src, dst]
    else:
        ip = ["0x00", "0x00000", "64", proto, str(PROTO_NUMBER[proto]), "40", src, dst]
    if proto == "tcp":
        tail = [str(sport), str(dport), "0", "S", "1234567890", "", "64240", "", "mss;sackOK;TS;nop;wscale"]
    elif proto == "udp":
        tail = [str(sport), str(dport), "40"]
    else:
        tail = ["datalength=64"]
    return head + ip + tail


def line(ipver, proto, *, host="fw-a.example.lan", when=None, seq=1, **kw):
    """One RFC5424 line as OPNsense's syslog-ng sends it (RFC5424 enabled)."""
    when = when or datetime.now().astimezone()
    stamp = when.isoformat(timespec="milliseconds")
    msg = ",".join(fields(ipver, proto, **kw))
    return f'<134>1 {stamp} {host} filterlog 71234 - [meta sequenceId="{seq}"] {msg}'
