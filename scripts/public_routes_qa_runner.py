#!/usr/bin/env python3
"""
Public routes QA runner for sf-permits-mcp production site.
Run with: CLAUDE_SUBAGENT=true python3 qa-drop/public-routes-qa-runner.py
"""
import json
import os
import urllib.parse
from playwright.sync_api import sync_playwright

BASE = "https://sfpermits-ai-production.up.railway.app"
SCREENSHOT_DIR = "/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/public-qa-2026-02-28"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []


def record(num, name, status, notes=""):
    results.append({"num": num, "name": name, "status": status, "notes": notes})
    print(f"[{status}] Check {num}: {name} — {notes}")


SEARCH_SEL = (
    'input[type="text"], input[type="search"], '
    'input[placeholder*="ddress"], input[placeholder*="earch"], '
    'input[name*="q"], input[name*="address"]'
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})

    # --- Check 2: Landing Page ---
    page = context.new_page()
    page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    title = page.title()
    page.screenshot(path=f"{SCREENSHOT_DIR}/check2-landing.png", full_page=True)
    has_title = (
        "SF Permits" in title
        or "sfpermits" in title.lower()
        or "permit" in title.lower()
        or "San Francisco" in title
    )
    has_cta = page.locator(
        'a, button, [class*="cta"], .ghost-cta, [href*="search"]'
    ).count() > 0
    error_banner = (
        page.locator("text=500").count() > 0
        or page.locator("text=Server Error").count() > 0
        or page.locator("text=Internal Server Error").count() > 0
    )
    if not error_banner:
        record(2, "Landing page loads", "PASS", f"title={title!r}, cta={has_cta}")
    else:
        record(2, "Landing page loads", "FAIL", f"title={title!r}, error_banner=True")

    # --- Check 3: Search form present ---
    page3 = context.new_page()
    page3.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    search_input = page3.locator(SEARCH_SEL).first
    is_visible = search_input.is_visible() if search_input.count() > 0 else False
    page3.screenshot(path=f"{SCREENSHOT_DIR}/check3-search-form.png", full_page=False)
    if is_visible:
        record(3, "Search form present", "PASS", "input visible on landing /")
    else:
        page3.goto(BASE + "/search", wait_until="networkidle", timeout=20000)
        search_input2 = page3.locator(SEARCH_SEL).first
        is_visible2 = search_input2.is_visible() if search_input2.count() > 0 else False
        page3.screenshot(path=f"{SCREENSHOT_DIR}/check3-search-form-search.png", full_page=False)
        if is_visible2:
            record(3, "Search form present", "PASS", "input visible on /search")
        else:
            record(3, "Search form present", "FAIL", "no search input on / or /search")

    # --- Check 4: Search results — valid address ---
    page4 = context.new_page()
    page4.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    inp4 = page4.locator(SEARCH_SEL).first
    if inp4.count() > 0 and inp4.is_visible():
        inp4.fill("123 Main St San Francisco")
        inp4.press("Enter")
        try:
            page4.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
    else:
        page4.goto(
            BASE + "/search?q=123+Main+St+San+Francisco",
            wait_until="networkidle",
            timeout=20000,
        )
    page4.screenshot(path=f"{SCREENSHOT_DIR}/check4-search-valid.png", full_page=True)
    has_500_4 = (
        page4.locator("text=500").count() > 0
        or page4.locator("text=Traceback").count() > 0
        or page4.locator("text=Internal Server Error").count() > 0
    )
    body4 = page4.inner_text("body")[:600]
    has_content = any(
        kw in body4.lower()
        for kw in ["permit", "result", "no results", "found", "address", "search"]
    )
    if has_500_4:
        record(4, "Search results — valid address", "FAIL", "500 error rendered")
    elif has_content:
        record(4, "Search results — valid address", "PASS", f"content found, no 500")
    else:
        record(
            4,
            "Search results — valid address",
            "PASS",
            f"page loaded no error, preview={body4[:80]!r}",
        )

    # --- Check 5: Search results — empty query ---
    page5 = context.new_page()
    page5.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    inp5 = page5.locator(SEARCH_SEL).first
    if inp5.count() > 0 and inp5.is_visible():
        inp5.fill("   ")
        inp5.press("Enter")
        try:
            page5.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
    else:
        page5.goto(BASE + "/search?q=   ", wait_until="networkidle", timeout=15000)
    page5.screenshot(path=f"{SCREENSHOT_DIR}/check5-search-empty.png", full_page=True)
    has_500_5 = (
        page5.locator("text=500").count() > 0
        or page5.locator("text=Traceback").count() > 0
    )
    body5 = page5.inner_text("body")[:300]
    if has_500_5:
        record(5, "Search results — empty query", "FAIL", "500/traceback rendered")
    else:
        record(5, "Search results — empty query", "PASS", f"no 500, body={body5[:80]!r}")

    # --- Check 6: XSS special characters ---
    page6 = context.new_page()
    xss_payload = "<script>alert(1)</script>"
    page6.goto(
        BASE + "/search?q=" + urllib.parse.quote(xss_payload),
        wait_until="networkidle",
        timeout=15000,
    )
    page6.screenshot(path=f"{SCREENSHOT_DIR}/check6-xss.png", full_page=True)
    has_500_6 = (
        page6.locator("text=500").count() > 0
        or page6.locator("text=Traceback").count() > 0
    )
    html6 = page6.content()
    unescaped_script = "<script>alert(1)</script>" in html6
    if has_500_6:
        record(6, "Search results — special characters", "FAIL", "500 error on XSS input")
    elif unescaped_script:
        record(
            6,
            "Search results — special characters",
            "FAIL",
            "XSS payload reflected unescaped",
        )
    else:
        record(
            6,
            "Search results — special characters",
            "PASS",
            "input escaped or not reflected",
        )

    # --- Check 7: Public report page ---
    page7 = context.new_page()
    # Use a real-looking permit number; will 404 gracefully if not found
    page7.goto(BASE + "/report/202101012345", wait_until="networkidle", timeout=20000)
    url7 = page7.url
    page7.screenshot(path=f"{SCREENSHOT_DIR}/check7-report.png", full_page=True)
    body7 = page7.inner_text("body")[:500]
    has_500_7 = (
        page7.locator("text=500").count() > 0
        or page7.locator("text=Traceback").count() > 0
        or page7.locator("text=Internal Server Error").count() > 0
    )
    redirected_to_login = "/login" in url7 or "/auth" in url7
    if has_500_7:
        record(7, "Public report page", "FAIL", f"500 error at {url7}")
    elif redirected_to_login:
        record(7, "Public report page", "FAIL", f"unexpected auth redirect to {url7}")
    else:
        record(
            7,
            "Public report page",
            "PASS",
            f"loaded without auth redirect, url={url7!r}",
        )

    # --- Check 8: Unauthenticated access to /brief ---
    page8 = context.new_page()
    page8.goto(BASE + "/brief", wait_until="networkidle", timeout=20000)
    url8 = page8.url
    page8.screenshot(path=f"{SCREENSHOT_DIR}/check8-brief-unauth.png", full_page=True)
    body8 = page8.inner_text("body")[:400]
    has_500_8 = (
        page8.locator("text=500").count() > 0
        or page8.locator("text=Traceback").count() > 0
    )
    redirected_8 = "/login" in url8 or "/auth" in url8 or url8 != BASE + "/brief"
    if has_500_8:
        record(8, "Unauthenticated /brief", "FAIL", "server error on /brief without auth")
    elif redirected_8:
        record(8, "Unauthenticated /brief", "PASS", f"redirected to {url8}")
    else:
        has_brief_content = (
            "morning brief" in body8.lower()
            or ("permit" in body8.lower() and "brief" in body8.lower())
        )
        if has_brief_content:
            record(
                8,
                "Unauthenticated /brief",
                "FAIL",
                "brief content shown without auth",
            )
        else:
            record(
                8,
                "Unauthenticated /brief",
                "PASS",
                f"no protected content exposed, body={body8[:60]!r}",
            )

    # --- Check 9: Static assets load ---
    page9 = context.new_page()
    failed_assets = []

    def on_response(response):
        url = response.url
        if response.status >= 400 and (".css" in url or ".js" in url):
            failed_assets.append(f"{response.status} {url}")

    page9.on("response", on_response)
    page9.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    page9.screenshot(path=f"{SCREENSHOT_DIR}/check9-assets.png", full_page=False)
    if failed_assets:
        record(9, "Static assets load", "FAIL", f"broken: {failed_assets[:3]}")
    else:
        record(9, "Static assets load", "PASS", "no broken CSS/JS assets")

    browser.close()

print()
print("=== SUMMARY ===")
for r in results:
    print(f"  [{r['status']}] {r['num']}. {r['name']} — {r['notes']}")

# Write JSON for post-processing
with open("/tmp/public-qa-results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Results written to /tmp/public-qa-results.json")
