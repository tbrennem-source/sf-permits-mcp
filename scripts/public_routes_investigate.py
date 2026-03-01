#!/usr/bin/env python3
"""
Investigate FAILs from public routes QA.
Check 2: Is 'text=500' a false positive on the landing page?
Check 5: What does the empty query search actually return?
"""
import os
from playwright.sync_api import sync_playwright

BASE = "https://sfpermits-ai-production.up.railway.app"
SCREENSHOT_DIR = "/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/public-qa-2026-02-28"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})

    # --- Investigate Check 2: Does landing page actually have '500' text? ---
    print("=== Investigating Check 2: Landing Page ===")
    page2 = context.new_page()
    page2.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    html2 = page2.content()
    body2 = page2.inner_text("body")

    # Find occurrences of '500' in the body text
    lines_with_500 = [line.strip() for line in body2.split('\n') if '500' in line and line.strip()]
    print(f"Lines containing '500' in body text: {lines_with_500[:10]}")

    # Check for actual error indicators
    has_server_error = 'Server Error' in body2 or 'Internal Server Error' in body2
    has_traceback = 'Traceback' in body2
    has_werkzeug = 'werkzeug' in html2.lower() or 'debugger' in html2.lower()
    print(f"has_server_error={has_server_error}, has_traceback={has_traceback}, has_werkzeug={has_werkzeug}")
    print(f"Page title: {page2.title()!r}")

    # Check HTTP status via page.goto response
    response2 = page2.goto(BASE + "/")
    print(f"HTTP status: {response2.status}")

    # --- Investigate Check 5: Empty query search ---
    print()
    print("=== Investigating Check 5: Empty Query Search ===")

    # Try direct URL with empty q
    page5a = context.new_page()
    resp5a = page5a.goto(BASE + "/search?q=", wait_until="networkidle", timeout=15000)
    print(f"GET /search?q= -> HTTP {resp5a.status}")
    body5a = page5a.inner_text("body")
    html5a = page5a.content()
    has_traceback5a = 'Traceback' in body5a or 'Traceback' in html5a
    has_500_5a = resp5a.status == 500 or 'Internal Server Error' in body5a
    print(f"  has_traceback={has_traceback5a}, has_500={has_500_5a}")
    print(f"  Body preview: {body5a[:300]!r}")
    page5a.screenshot(path=f"{SCREENSHOT_DIR}/check5-investigate-empty-q.png", full_page=True)

    # Try whitespace q
    page5b = context.new_page()
    import urllib.parse
    resp5b = page5b.goto(BASE + "/search?q=" + urllib.parse.quote("   "), wait_until="networkidle", timeout=15000)
    print(f"\nGET /search?q=spaces -> HTTP {resp5b.status}")
    body5b = page5b.inner_text("body")
    html5b = page5b.content()
    has_traceback5b = 'Traceback' in body5b or 'Traceback' in html5b
    has_500_5b = resp5b.status == 500 or 'Internal Server Error' in body5b
    print(f"  has_traceback={has_traceback5b}, has_500={has_500_5b}")
    print(f"  Body preview: {body5b[:300]!r}")
    page5b.screenshot(path=f"{SCREENSHOT_DIR}/check5-investigate-whitespace.png", full_page=True)

    # Try submitting the form with whitespace
    page5c = context.new_page()
    page5c.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    SEARCH_SEL = (
        'input[type="text"], input[type="search"], '
        'input[placeholder*="ddress"], input[placeholder*="earch"], '
        'input[name*="q"], input[name*="address"]'
    )
    inp = page5c.locator(SEARCH_SEL).first
    if inp.count() > 0 and inp.is_visible():
        inp.fill("   ")
        inp.press("Enter")
        try:
            page5c.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        final_url = page5c.url
        resp_status = None  # can't get status after navigation this way
        body5c = page5c.inner_text("body")
        html5c = page5c.content()
        has_500c = 'Internal Server Error' in body5c or page5c.locator("text=500").count() > 0
        has_traceback5c = 'Traceback' in body5c or 'Traceback' in html5c
        print(f"\nForm submit with whitespace -> URL={final_url}")
        print(f"  has_500={has_500c}, has_traceback={has_traceback5c}")
        print(f"  Body preview: {body5c[:300]!r}")
        page5c.screenshot(path=f"{SCREENSHOT_DIR}/check5-investigate-form-whitespace.png", full_page=True)
    else:
        print("No search form found on landing page for form submission test")

    browser.close()
    print("\nInvestigation complete. Screenshots saved.")
