#!/usr/bin/env python3
"""Screenshot both dashboards for docs/images and check what the firewall
tables render (runs in the Playwright image).
  screenshots.py BASE_URL USER PASSWORD OUT_DIR

The checks go through the browser because the API harness cannot see
transformations or value mappings, and only Grafana's own variable formatting
proves that an IPv6 $src_ip (colons) survives the Lucene query."""
import sys

from playwright.sync_api import sync_playwright

base, user, password, out = sys.argv[1:5]
MAIN = "suTmk8c7k"
SHOTS = ((MAIN, "opnsense.png", 4200), ("94raP_-7z", "opnsense-suricata.png", 1500))
INSIDE = "2001:db8:1:10::200e"  # send_syslog.py: a LAN host opening new connections
RENDERED = ("Blocked from the Internet", "Blocked from Your Networks", "Recent Blocked Events",
            "New connection", "Late packet", "Not TCP", INSIDE, "192.168.1.50", "2.125.160.216")


def load(page, uid, extra=""):
    page.goto(f"{base}/d/{uid}?orgId=1&from=now-30m&to=now&var-Host=fw-a.example.lan{extra}&kiosk",
              wait_until="networkidle", timeout=120000)
    page.wait_for_timeout(8000)
    return page.inner_text("body")


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    # Basic auth covers the API only; the UI needs a session cookie.
    login = context.request.post(f"{base}/login", data={"user": user, "password": password})
    assert login.ok, f"Grafana login failed: HTTP {login.status}"
    page = context.new_page()
    for uid, name, height in SHOTS:
        page.set_viewport_size({"width": 1600, "height": height})  # every panel in view, so all load
        body = load(page, uid)
        page.screenshot(path=f"{out}/{name}", full_page=True)
        print(f"saved {name}")
        if uid == MAIN:
            missing = [t for t in RENDERED if t not in body]
            assert not missing, f"OPNsense dashboard does not render {missing}"

    # Clicking a source sets $src_ip; every firewall panel must narrow to it.
    page.set_viewport_size({"width": 1600, "height": SHOTS[0][2]})
    body = load(page, MAIN, f"&var-src_ip={INSIDE}")
    others = [ip for ip in ("2.125.160.216", "192.168.1.50") if ip in body]
    assert body.count(INSIDE) >= 3 and not others, \
        f"$src_ip={INSIDE}: {body.count(INSIDE)} mentions, other sources still shown: {others}"
    print("firewall tables render; IPv6 source drill-down works")
    browser.close()
