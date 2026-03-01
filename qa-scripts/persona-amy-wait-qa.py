#!/usr/bin/env python3
"""
Persona: Amy — Wait for JS render and capture real search results.
The previous screenshots captured loading state. This script waits for
the permit table to fully render before screenshotting.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "https://sfpermits-ai-production.up.railway.app"
SESSION_ID = "persona-amy-20260228"
SCREENSHOT_DIR = Path(f"/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/{SESSION_ID}")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # ============================================================
        # SEARCH RESULT — wait for table to render
        # ============================================================
        print("\n=== Waiting for search results to fully render ===")
        page.goto(
            f"{BASE_URL}/search?q=1660+Mission+Street",
            wait_until="networkidle",
            timeout=60000,
        )

        # Wait specifically for the permit table or result content
        # The page loads via HTMX — wait for network idle plus extra time
        print("  Waiting for HTMX render...")
        try:
            # Wait for a table row or any element with permit data
            page.wait_for_selector("table tr:nth-child(2), .permit-row, [data-permit], .glass-card", timeout=20000)
            print("  Permit content element found")
        except Exception as e:
            print(f"  Selector timeout: {e} — waiting extra 8s")
            time.sleep(8)

        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-1660-mission-loaded.png"), full_page=True)
        text = page.inner_text("body")
        print(f"  Page length: {len(text)}")
        print(f"  Preview: {text[:600]}")

        # ============================================================
        # SEARCH RESULT — 2301 Mission with longer wait
        # ============================================================
        print("\n=== 2301 Mission Street — full render ===")
        page.goto(
            f"{BASE_URL}/search?q=2301+Mission+Street",
            wait_until="networkidle",
            timeout=60000,
        )
        try:
            page.wait_for_selector("table tr:nth-child(2), .permit-row, td, .result", timeout=20000)
        except:
            time.sleep(8)

        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-2301-mission-loaded.png"), full_page=True)
        text = page.inner_text("body")
        print(f"  Page length: {len(text)}")
        print(f"  First 800 chars: {text[:800]}")

        # ============================================================
        # LANDING PAGE — full render
        # ============================================================
        print("\n=== Landing page — full render ===")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-landing-full.png"), full_page=True)

        # ============================================================
        # ENTITY NETWORK TOOL — publicly accessible
        # ============================================================
        print("\n=== Entity Network Tool ===")
        page.goto(f"{BASE_URL}/tools/entity-network", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-entity-network.png"), full_page=True)
        entity_text = page.inner_text("body")
        print(f"  Entity network page: {len(entity_text)} chars")
        print(f"  Preview: {entity_text[:500]}")

        # ============================================================
        # ERROR STATE — confirm graceful handling visual
        # ============================================================
        print("\n=== Error state — graceful ===")
        page.goto(f"{BASE_URL}/search?q=9999999999", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-error-state.png"), full_page=True)

        # ============================================================
        # DEMO PAGE
        # ============================================================
        print("\n=== Demo page ===")
        page.goto(f"{BASE_URL}/demo", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-demo-page.png"), full_page=True)
        demo_text = page.inner_text("body")
        print(f"  Demo page: {len(demo_text)} chars, preview: {demo_text[:300]}")

        # ============================================================
        # SEARCH + WAIT: Check if the search page eventually shows data
        # or stays blank (HTMX timeout?)
        # ============================================================
        print("\n=== HTMX render timing investigation ===")
        page.goto(
            f"{BASE_URL}/search?q=2301+Mission+Street",
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # Check content at intervals
        for wait_secs in [1, 3, 5, 8, 12]:
            time.sleep(wait_secs if wait_secs == 1 else wait_secs - (wait_secs - 1))
            text = page.inner_text("body")
            has_table = "Permit #" in text or "permit" in text.lower() and len(text) > 500
            print(f"  After {wait_secs}s: length={len(text)}, has_table={has_table}, preview={text[:100]}")

        page.screenshot(path=str(SCREENSHOT_DIR / "WAIT-htmx-timing-12s.png"), full_page=True)
        final_text = page.inner_text("body")
        print(f"\n  Final text at 12s: {len(final_text)} chars")
        print(f"  Content: {final_text[:1000]}")

        browser.close()


if __name__ == "__main__":
    from datetime import datetime
    print(f"Amy visual render QA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    run()
    print("\nDone. Screenshots saved.")
