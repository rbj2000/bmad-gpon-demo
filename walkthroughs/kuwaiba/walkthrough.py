#!/usr/bin/env python3
"""
Kuwaiba GPON Demo Walkthrough — Playwright screenshot automation.

Skill: migration-pipeline-orchestrator (demo tooling)
Date: 2026-02-24
Assumptions:
  - Kuwaiba 2.1 running on localhost:8880 with GPON demo data loaded
  - Playwright + Chromium installed (pip install playwright && playwright install chromium)
  - Kuwaiba is a Vaadin SPA — navigation via drill-down clicks, not URL routing

Usage:
    python walkthrough.py [--output-dir ./screenshots] [--base-url http://localhost:8880/kuwaiba/]
"""

import argparse
import logging
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, Page

KUWAIBA_URL = "http://localhost:8880/kuwaiba/"
USERNAME = "admin"
PASSWORD = "kuwaiba"
VIEWPORT = {"width": 1920, "height": 1080}
# Vaadin renders are async — generous settle time
SETTLE_MS = 2000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def screenshot(page: Page, out: Path, name: str, full_page: bool = False):
    """Take a screenshot and log it."""
    path = out / name
    page.screenshot(path=str(path), full_page=full_page)
    log.info("Saved %s", path)


def settle(page: Page, ms: int = SETTLE_MS):
    """Wait for Vaadin SPA to finish rendering."""
    page.wait_for_timeout(ms)


def click_child(page: Page, label: str, timeout: int = 10000):
    """Click a child item in the right-side children panel.

    Kuwaiba navman shows children as table rows with <span> text.
    Clicking a child navigates into it (shows its properties on the
    left and its children on the right).
    """
    node = page.locator(f"td span:has-text('{label}')").first
    node.scroll_into_view_if_needed()
    node.click(timeout=timeout)
    settle(page, 3000)


def click_breadcrumb(page: Page, label: str, timeout: int = 10000):
    """Click a breadcrumb button to navigate back up the hierarchy."""
    page.locator(f"vaadin-button:has-text('{label}')").first.click(timeout=timeout)
    settle(page, 3000)


# ---------------------------------------------------------------------------
# Main walkthrough
# ---------------------------------------------------------------------------

def run(base_url: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(15000)

        # ==================================================================
        # 01 — Login page
        # ==================================================================
        log.info("Step 01: Login page")
        page.goto(base_url)
        settle(page, 3000)
        screenshot(page, output_dir, "01-login-page.png")

        # ==================================================================
        # 02 — Dashboard / home
        # ==================================================================
        log.info("Step 02: Login → Dashboard")
        page.locator("vaadin-text-field").first.locator("input").fill(USERNAME)
        page.locator("vaadin-password-field").first.locator("input").fill(PASSWORD)
        page.locator("vaadin-button:has-text('Login')").click()
        settle(page, 5000)
        screenshot(page, output_dir, "02-dashboard.png")

        # ==================================================================
        # 03 — Navigation module (empty state)
        # ==================================================================
        log.info("Step 03: Navigation module")
        # Direct URL navigation — Vaadin router handles the route
        navman_url = base_url.rstrip("/") + "/navman"
        page.goto(navman_url)
        settle(page, 3000)
        screenshot(page, output_dir, "03-navigation-module.png")

        # ==================================================================
        # 04 — Root tree (after clicking Go to Root)
        # ==================================================================
        log.info("Step 04: Root tree")
        page.locator("vaadin-button:has-text('Go to Root')").click()
        settle(page, 3000)
        screenshot(page, output_dir, "04-root-tree.png")

        # ==================================================================
        # 05 — GPON Demo → 5 cities
        # ==================================================================
        log.info("Step 05: GPON Demo → cities")
        click_child(page, "GPON Demo")
        screenshot(page, output_dir, "05-cities.png")

        # ==================================================================
        # 06 — Prague Central CO → equipment list
        # ==================================================================
        log.info("Step 06: Prague Central CO")
        click_child(page, "Prague Central CO")
        screenshot(page, output_dir, "06-prague-co.png")

        # ==================================================================
        # 07 — OLT detail + children (slots)
        # ==================================================================
        log.info("Step 07: OLT detail")
        click_child(page, "OLT-SITE-0001-01")
        screenshot(page, output_dir, "07-olt-detail.png")

        # ==================================================================
        # 08 — Slot → line card
        # ==================================================================
        log.info("Step 08: Slot → line card")
        # REVIEW: Slot number depends on demo data
        click_child(page, "Slot 9")
        screenshot(page, output_dir, "08-slot-linecard.png")

        # ==================================================================
        # 09 — Line card → ports + transceivers
        # ==================================================================
        log.info("Step 09: Line card → ports")
        click_child(page, "CARD-SLOT-OLT-SITE-0001-01-09")
        screenshot(page, output_dir, "09-ports.png")

        # ==================================================================
        # 10 — Port detail (click a connected port)
        # ==================================================================
        log.info("Step 10: Port detail")
        # Ports with [+] prefix have connections
        click_child(page, "0/9/1")
        screenshot(page, output_dir, "10-port-detail.png")

        # ==================================================================
        # 11 — Navigate back to Prague via breadcrumb
        # ==================================================================
        log.info("Step 11: Back to Prague (breadcrumb)")
        click_breadcrumb(page, "Prague Central CO")
        screenshot(page, output_dir, "11-prague-breadcrumb.png")

        # ==================================================================
        # 12 — ONT detail
        # ==================================================================
        log.info("Step 12: ONT detail")
        click_child(page, "ONT-000001")
        screenshot(page, output_dir, "12-ont-detail.png")

        # ==================================================================
        # 13 — ONT children (PON port)
        # ==================================================================
        log.info("Step 13: ONT PON port")
        # ONT children should include an OpticalPort
        children = page.evaluate("""() => {
            let tds = document.querySelectorAll('td span');
            return Array.from(tds).map(s => s.textContent.trim()).filter(t => t.includes('Port'));
        }""")
        if children:
            log.info("ONT port found: %s", children[0])
            click_child(page, children[0].split(" [")[0])
        screenshot(page, output_dir, "13-ont-port.png")

        # ==================================================================
        log.info("Done — %d screenshots in %s",
                 len(list(output_dir.glob("*.png"))), output_dir)
        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Kuwaiba GPON demo walkthrough — screenshot automation"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("./screenshots"),
        help="Directory for screenshot PNGs (default: ./screenshots)"
    )
    parser.add_argument(
        "--base-url", default=KUWAIBA_URL,
        help=f"Kuwaiba base URL (default: {KUWAIBA_URL})"
    )
    args = parser.parse_args()
    run(args.base_url, args.output_dir)


if __name__ == "__main__":
    main()
