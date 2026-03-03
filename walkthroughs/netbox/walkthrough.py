#!/usr/bin/env python3
"""
NetBox GPON Demo Walkthrough — Playwright screenshot automation.

Skill: migration-pipeline-orchestrator (demo tooling)
Date: 2026-02-24
Assumptions:
  - NetBox running on localhost:8000 with GPON demo data loaded
  - Playwright + Chromium installed (pip install playwright && playwright install chromium)

Usage:
    python walkthrough.py [--output-dir ./screenshots] [--base-url http://localhost:8000]
"""

import argparse
import logging
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

NETBOX_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin"
VIEWPORT = {"width": 1920, "height": 1080}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def screenshot(page: Page, out: Path, name: str, full_page: bool = True):
    """Take a screenshot and log it."""
    path = out / name
    page.screenshot(path=str(path), full_page=full_page)
    log.info("Saved %s", path)


def wait(page: Page):
    """Wait for page to settle."""
    page.wait_for_load_state("networkidle")


def first_detail_href(page: Page, table_selector: str = "table.table tbody tr") -> str:
    """Extract the href of the first link in a list table."""
    row = page.locator(table_selector).first
    link = row.locator("a").first
    return link.get_attribute("href")


def run(base_url: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True)
        page = context.new_page()

        # ------------------------------------------------------------------
        # 01 — Login page
        # ------------------------------------------------------------------
        log.info("Step 01: Login page")
        page.goto(f"{base_url}/login/")
        wait(page)
        screenshot(page, output_dir, "01-login-page.png")

        # ------------------------------------------------------------------
        # 02 — Dashboard (after login)
        # ------------------------------------------------------------------
        log.info("Step 02: Login → Dashboard")
        page.fill("#id_username", USERNAME)
        page.fill("#id_password", PASSWORD)
        page.click("button[type=submit]")
        wait(page)
        screenshot(page, output_dir, "02-dashboard.png")

        # ------------------------------------------------------------------
        # 03 — Sites list
        # ------------------------------------------------------------------
        log.info("Step 03: Sites list")
        page.goto(f"{base_url}/dcim/sites/")
        wait(page)
        screenshot(page, output_dir, "03-sites-list.png")

        # ------------------------------------------------------------------
        # 04 — Site detail (first site)
        # ------------------------------------------------------------------
        log.info("Step 04: Site detail")
        href = first_detail_href(page)
        page.goto(f"{base_url}{href}")
        wait(page)
        screenshot(page, output_dir, "04-site-detail.png")
        site_url = page.url  # remember for later

        # ------------------------------------------------------------------
        # 05 — Devices list (all)
        # ------------------------------------------------------------------
        log.info("Step 05: All devices")
        page.goto(f"{base_url}/dcim/devices/")
        wait(page)
        screenshot(page, output_dir, "05-devices-all.png")

        # ------------------------------------------------------------------
        # 06 — Devices filtered by OLT role
        # ------------------------------------------------------------------
        log.info("Step 06: Devices — OLT role")
        page.goto(f"{base_url}/dcim/devices/?role=olt")
        wait(page)
        screenshot(page, output_dir, "06-devices-olt.png")

        # ------------------------------------------------------------------
        # 07 — OLT detail
        # ------------------------------------------------------------------
        log.info("Step 07: OLT detail")
        href = first_detail_href(page)
        page.goto(f"{base_url}{href}")
        wait(page)
        screenshot(page, output_dir, "07-olt-detail.png")
        olt_url = page.url

        # ------------------------------------------------------------------
        # 08 — OLT module bays (line cards)
        # ------------------------------------------------------------------
        log.info("Step 08: OLT module bays")
        page.goto(f"{olt_url}module-bays/")
        wait(page)
        screenshot(page, output_dir, "08-olt-modules.png")

        # ------------------------------------------------------------------
        # 09 — OLT interfaces
        # ------------------------------------------------------------------
        log.info("Step 09: OLT interfaces")
        page.goto(f"{olt_url}interfaces/")
        wait(page)
        screenshot(page, output_dir, "09-olt-interfaces.png")

        # ------------------------------------------------------------------
        # 10 — Cables list
        # ------------------------------------------------------------------
        log.info("Step 10: Cables list")
        page.goto(f"{base_url}/dcim/cables/")
        wait(page)
        screenshot(page, output_dir, "10-cables.png")

        # ------------------------------------------------------------------
        # 11 — Cable detail
        # ------------------------------------------------------------------
        log.info("Step 11: Cable detail")
        href = first_detail_href(page)
        page.goto(f"{base_url}{href}")
        wait(page)
        screenshot(page, output_dir, "11-cable-detail.png")

        # ------------------------------------------------------------------
        # 12 — Splitter detail
        # ------------------------------------------------------------------
        log.info("Step 12: Splitter detail")
        page.goto(f"{base_url}/dcim/devices/?role=splitter")
        wait(page)
        href = first_detail_href(page)
        page.goto(f"{base_url}{href}")
        wait(page)
        screenshot(page, output_dir, "12-splitter-detail.png")

        # ------------------------------------------------------------------
        # 13 — ONT detail
        # ------------------------------------------------------------------
        log.info("Step 13: ONT detail")
        page.goto(f"{base_url}/dcim/devices/?role=ont")
        wait(page)
        href = first_detail_href(page)
        page.goto(f"{base_url}{href}")
        wait(page)
        screenshot(page, output_dir, "13-ont-detail.png")

        # ------------------------------------------------------------------
        log.info("Done — %d screenshots in %s", len(list(output_dir.glob("*.png"))), output_dir)
        browser.close()


def main():
    parser = argparse.ArgumentParser(description="NetBox GPON demo walkthrough — screenshot automation")
    parser.add_argument("--output-dir", type=Path, default=Path("./screenshots"),
                        help="Directory for screenshot PNGs (default: ./screenshots)")
    parser.add_argument("--base-url", default=NETBOX_URL,
                        help=f"NetBox base URL (default: {NETBOX_URL})")
    args = parser.parse_args()
    run(args.base_url, args.output_dir)


if __name__ == "__main__":
    main()
