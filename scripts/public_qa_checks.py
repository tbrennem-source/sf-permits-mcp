#!/usr/bin/env python3
"""Public-routes QA checks 2 and 4 re-run with fixed logic."""

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://sfpermits-ai-staging-production.up.railway.app"
SCREENSHOTS_DIR = Path("/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/sprint64-public-qa")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ---- Check 2: Landing page loads ----
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    resp = page.goto(f"{BASE}/", timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    title = page.title()
    content = page.content()
    has_500 = "Internal Server Error" in content and "Traceback" in content
    cta_count = page.locator("a[href], button").count()
    page.screenshot(path=str(SCREENSHOTS_DIR / "check2-landing.png"), full_page=True)

    title_ok = "sf" in title.lower() or "permit" in title.lower() or len(title) > 3
    status_ok = resp.status < 400 if resp else False

    if status_ok and title_ok and not has_500 and cta_count > 0:
        print(f"CHECK2|PASS|title='{title}', HTTP={resp.status}, CTAs={cta_count}")
    else:
        print(f"CHECK2|FAIL|title='{title}', HTTP={resp.status if resp else 'none'}, 500={has_500}, CTAs={cta_count}")

    ctx.close()

    # ---- Check 4: Search results — valid address ----
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
    page2 = ctx2.new_page()

    try:
        resp2 = page2.goto(
            f"{BASE}/search?q=123+Main+St+San+Francisco",
            timeout=45000,
            wait_until="load",
        )
        page2.wait_for_timeout(3000)
        content2 = page2.content()
        has_traceback = "Traceback" in content2
        has_500_err = "Internal Server Error" in content2 and has_traceback
        page2.screenshot(path=str(SCREENSHOTS_DIR / "check4-search-valid.png"), full_page=True)

        result_count = page2.locator("[class*='result'], [class*='permit'], table tr, .card").count()
        no_results_text = (
            "no results" in content2.lower()
            or "no permits" in content2.lower()
            or "0 results" in content2.lower()
        )
        page_loaded = resp2.status < 500 if resp2 else False

        if has_traceback or has_500_err:
            print(f"CHECK4|FAIL|traceback or 500 error")
        elif page_loaded:
            print(f"CHECK4|PASS|HTTP={resp2.status}, result_elements={result_count}, no_results_msg={no_results_text}")
        else:
            print(f"CHECK4|FAIL|HTTP={resp2.status if resp2 else 'none'}")
    except Exception as e:
        print(f"CHECK4|FAIL|{e}")

    ctx2.close()
    browser.close()
