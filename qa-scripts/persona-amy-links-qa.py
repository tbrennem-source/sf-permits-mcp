#!/usr/bin/env python3
"""
Persona: Amy — Link Investigation
Find where search results actually link to, what the data freshness situation is,
and what the stuck-permit API returns.
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://sfpermits-ai-production.up.railway.app"
SESSION_ID = "persona-amy-20260228"
SCREENSHOT_DIR = Path(f"/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/{SESSION_ID}")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

notes = []

def note(msg):
    notes.append(msg)
    print(f"  NOTE: {msg}")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # ============================================================
        # LINK INVESTIGATION: Where do permit result links go?
        # ============================================================
        print("\n=== LINK INVESTIGATION: Search Result Links ===")
        page.goto(f"{BASE_URL}/search?q=2301+Mission+Street+San+Francisco",
                  wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Find all links on the page
        links = page.locator("a[href]").all()
        permit_links = []
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.inner_text()[:50] if link.is_visible() else ""
            if any(x in href for x in ["/prep/", "/lookup", "/search", "/permit"]):
                permit_links.append({"href": href, "text": text})

        print(f"  Total links: {len(links)}")
        print(f"  Permit-related links: {len(permit_links)}")
        for lnk in permit_links[:10]:
            print(f"    {lnk['href'][:80]} | {lnk['text'][:40]}")

        # Check the actual link that permit results use
        # Find the first permit card's link
        all_hrefs = []
        for link in links:
            href = link.get_attribute("href") or ""
            if href and href.startswith("/"):
                all_hrefs.append(href)

        unique_paths = list(set(all_hrefs))
        print(f"\n  All unique internal paths:")
        for p_path in sorted(unique_paths)[:30]:
            print(f"    {p_path}")

        # Now find what links are inside the permit result cards
        # Look for lookup links specifically
        lookup_links = [h for h in all_hrefs if "/lookup" in h or "/prep/" in h or "/report/" in h]
        print(f"\n  Lookup/prep/report links: {lookup_links[:10]}")

        # ============================================================
        # CHECK: What does /prep/<permit> show?
        # ============================================================
        print("\n=== CHECK: /prep/<permit_number> Route ===")
        test_permit = "202504285346"  # from earlier search
        page.goto(f"{BASE_URL}/prep/{test_permit}",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        prep_url = page.url
        prep_text = page.inner_text("body")
        page.screenshot(path=str(SCREENSHOT_DIR / "LINK-prep-page.png"), full_page=True)

        print(f"  URL: {prep_url}")
        print(f"  Length: {len(prep_text)}")
        print(f"  Preview: {prep_text[:300]}")

        # Check for core permit data
        has_permit_data = any(x in prep_text for x in [test_permit, "2301 Mission", "Mission St"])
        has_status = any(w in prep_text.lower() for w in ["status", "issued", "filed", "open"])
        has_dates = bool(re.findall(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', prep_text))
        redirected_to_login = "/login" in prep_url or "/auth" in prep_url

        print(f"  Permit data: {has_permit_data}, Status: {has_status}, Dates: {has_dates}, Login redirect: {redirected_to_login}")

        # ============================================================
        # CHECK: Stuck Permit API for a real permit
        # ============================================================
        print("\n=== CHECK: /api/stuck-permit/<permit_number> ===")
        stuck_resp = context.request.get(f"{BASE_URL}/api/stuck-permit/{test_permit}")
        print(f"  HTTP status: {stuck_resp.status}")

        if stuck_resp.status == 200:
            try:
                stuck_data = stuck_resp.json()
                print(f"  Keys: {list(stuck_data.keys()) if isinstance(stuck_data, dict) else type(stuck_data)}")
                print(f"  Preview: {json.dumps(stuck_data)[:400]}")
            except Exception as e:
                print(f"  JSON parse error: {e}")
                print(f"  Raw: {stuck_resp.text()[:200]}")
        else:
            print(f"  Non-200 response: {stuck_resp.text()[:200]}")

        # ============================================================
        # CHECK: Timeline API for a real permit
        # ============================================================
        print("\n=== CHECK: /api/timeline/<permit_number> ===")
        timeline_resp = context.request.get(f"{BASE_URL}/api/timeline/{test_permit}")
        print(f"  HTTP status: {timeline_resp.status}")

        if timeline_resp.status == 200:
            try:
                timeline_data = timeline_resp.json()
                print(f"  Keys: {list(timeline_data.keys()) if isinstance(timeline_data, dict) else type(timeline_data)}")
                print(f"  Preview: {json.dumps(timeline_data)[:500]}")
            except Exception as e:
                print(f"  JSON parse error: {e}")

        # ============================================================
        # CHECK: What does the /lookup endpoint show?
        # ============================================================
        print("\n=== CHECK: /lookup endpoint ===")
        lookup_resp = context.request.post(
            f"{BASE_URL}/lookup",
            data=json.dumps({"query": "202504285346", "permit_number": "202504285346"}),
            headers={"Content-Type": "application/json"}
        )
        print(f"  HTTP status: {lookup_resp.status}")
        if lookup_resp.status in (200, 302):
            text = lookup_resp.text()[:500]
            print(f"  Preview: {text}")

        # ============================================================
        # CHECK: What does the Intel Preview endpoint show?
        # ============================================================
        print("\n=== CHECK: /lookup/intel-preview ===")
        intel_resp = context.request.post(
            f"{BASE_URL}/lookup/intel-preview",
            data=json.dumps({"permit_number": test_permit}),
            headers={"Content-Type": "application/json"}
        )
        print(f"  HTTP status: {intel_resp.status}")
        if intel_resp.status == 200:
            try:
                intel_data = intel_resp.json()
                print(f"  Keys: {list(intel_data.keys()) if isinstance(intel_data, dict) else type(intel_data)}")
                print(f"  Preview: {json.dumps(intel_data)[:600]}")
            except:
                print(f"  Raw: {intel_resp.text()[:300]}")

        # ============================================================
        # CHECK: Predict-next API
        # ============================================================
        print("\n=== CHECK: /api/predict-next/<permit_number> ===")
        pred_resp = context.request.get(f"{BASE_URL}/api/predict-next/{test_permit}")
        print(f"  HTTP status: {pred_resp.status}")
        if pred_resp.status == 200:
            try:
                pred_data = pred_resp.json()
                print(f"  Keys: {list(pred_data.keys()) if isinstance(pred_data, dict) else type(pred_data)}")
                print(f"  Preview: {json.dumps(pred_data)[:600]}")
            except:
                print(f"  Raw: {pred_resp.text()[:300]}")
        else:
            print(f"  Response: {pred_resp.text()[:200]}")

        # ============================================================
        # CHECK: Data freshness via the actual search result dates
        # ============================================================
        print("\n=== CHECK: Data Freshness Analysis ===")
        # The search results earlier showed dates like 2025-04-28 in permit IDs
        # The permit number 202504285346 starts with 202504 = April 2025
        # Let's check what the most recent permits actually are

        # Try a search with no filter to see what comes back
        page.goto(f"{BASE_URL}/search?q=filed+2025",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        result_text = page.inner_text("body")

        dates = re.findall(r'\b(20\d{2})-(\d{2})-(\d{2})\b', result_text)
        if dates:
            date_objs = []
            for yr, mo, dy in dates:
                try:
                    date_objs.append(datetime(int(yr), int(mo), int(dy)))
                except:
                    pass
            if date_objs:
                newest = max(date_objs)
                print(f"  Most recent permit date in 'filed 2025' search: {newest.date()}")
                days_old = (datetime.now() - newest).days
                print(f"  Data age: {days_old} days")
        else:
            print("  No dates found in 'filed 2025' search")

        # Check the permit ID in search - 202504285346 means it was filed April 2025
        # Let's find the most recently-filed permit
        permit_ids = re.findall(r'\b(20\d{6})\d+\b', result_text)
        if permit_ids:
            # Permit IDs start with YYYYMM
            most_recent_prefix = max(permit_ids)
            yr = most_recent_prefix[:4]
            mo = most_recent_prefix[4:6]
            print(f"  Most recent permit filing month from IDs: {yr}-{mo}")

        # ============================================================
        # CHECK: Tools pages — what can Amy access without auth?
        # ============================================================
        print("\n=== CHECK: Tools Pages Accessibility ===")
        tools = [
            "/tools/stuck-permit",
            "/tools/station-predictor",
            "/tools/what-if",
            "/tools/cost-of-delay",
            "/tools/entity-network",
            "/tools/revision-risk",
            "/consultants",
            "/expediters",
        ]

        for tool_path in tools:
            resp = context.request.get(f"{BASE_URL}{tool_path}")
            text = ""
            if resp.status == 200:
                text_resp = page.goto(f"{BASE_URL}{tool_path}", wait_until="domcontentloaded", timeout=15000)
                time.sleep(1)
                text = page.inner_text("body")[:200]
            redirected = "/login" in (page.url or "") or "/auth" in (page.url or "")
            print(f"  {tool_path}: HTTP {resp.status}, auth_required={redirected}, len={len(text)}")

        # ============================================================
        # CHECK: Consultants page content
        # ============================================================
        print("\n=== CHECK: /consultants Page Detail ===")
        page.goto(f"{BASE_URL}/consultants", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        page.screenshot(path=str(SCREENSHOT_DIR / "LINK-consultants-page.png"), full_page=True)
        consult_text = page.inner_text("body")
        consult_url = page.url

        print(f"  URL: {consult_url}")
        print(f"  Length: {len(consult_text)}")
        print(f"  Preview: {consult_text[:500]}")

        # Check for consultant data quality
        has_names = bool(re.search(r'[A-Z][a-z]+ [A-Z][a-z]+|[A-Z]+ [A-Z][a-z]+\s+(?:Engineering|Consulting|Architecture|Design)',
                                  consult_text))
        has_contact = any(w in consult_text.lower() for w in ["email", "phone", "call", "contact", "website", "@"])
        has_sf_context = any(w in consult_text.lower() for w in ["san francisco", "sf", "bay area"])

        print(f"  Has names: {has_names}, Has contact: {has_contact}, SF context: {has_sf_context}")

        browser.close()


if __name__ == "__main__":
    print(f"Starting Amy Link Investigation — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    run()
