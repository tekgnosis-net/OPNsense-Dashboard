#!/usr/bin/env python3
"""Screenshot both dashboards for docs/images (runs in the Playwright image).
  screenshots.py BASE_URL USER PASSWORD OUT_DIR"""
import sys

from playwright.sync_api import sync_playwright

base, user, password, out = sys.argv[1:5]
SHOTS = (("suTmk8c7k", "opnsense.png", 3200), ("94raP_-7z", "opnsense-suricata.png", 1500))

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    # Basic auth covers the API only; the UI needs a session cookie.
    login = context.request.post(f"{base}/login", data={"user": user, "password": password})
    assert login.ok, f"Grafana login failed: HTTP {login.status}"
    page = context.new_page()
    for uid, name, height in SHOTS:
        page.set_viewport_size({"width": 1600, "height": height})
        page.goto(f"{base}/d/{uid}?orgId=1&from=now-30m&to=now&var-Host=fw-a.example.lan&kiosk",
                  wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(8000)
        page.screenshot(path=f"{out}/{name}", full_page=True)
        print(f"saved {name}")
    browser.close()
