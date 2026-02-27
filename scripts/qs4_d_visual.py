"""QS4-D Visual QA — screenshot /auth/login at desktop and mobile."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5099"
OUT = "qa-results/screenshots/qs4-d"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # Desktop (1440px)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/auth/login", wait_until="networkidle")
    page.screenshot(path=f"{OUT}/auth-login-desktop-1440.png", full_page=True)
    ctx.close()

    # Mobile (375px)
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    page.goto(f"{BASE}/auth/login", wait_until="networkidle")
    page.screenshot(path=f"{OUT}/auth-login-mobile-375.png", full_page=True)
    ctx.close()

    browser.close()

print("Screenshots saved to", OUT)
