#!/usr/bin/env python3
"""Dashboard QA screenshot script - takes screenshots at desktop and mobile viewports."""
import os
import sys
import json

def take_screenshots(round_num=1, base_url="https://sfpermits-ai-staging-production.up.railway.app", secret=None):
    from playwright.sync_api import sync_playwright

    screenshot_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "qa-results", "screenshots", "dashboard-loop"
    )
    os.makedirs(screenshot_dir, exist_ok=True)

    if not secret:
        secret = os.environ.get("TEST_LOGIN_SECRET", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Desktop viewport 1280x720
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded")

        resp = page.evaluate(f"""
            fetch('/auth/test-login', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{secret: '{secret}'}})
            }}).then(r => r.json()).catch(e => ({{error: e.message}}))
        """)
        print(f"Desktop auth: {json.dumps(resp)}")

        page.goto(base_url + "/", wait_until="networkidle")
        page.wait_for_timeout(2000)

        desktop_path = os.path.join(screenshot_dir, f"round-{round_num}-desktop.png")
        page.screenshot(path=desktop_path, full_page=True)
        print(f"Saved: {desktop_path}")

        # Nav screenshot
        nav = page.locator("nav").first
        if nav.is_visible():
            nav_path = os.path.join(screenshot_dir, f"round-{round_num}-nav-desktop.png")
            nav.screenshot(path=nav_path)
            print(f"Saved: {nav_path}")

        context.close()

        # Mobile viewport 375x812
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()
        page.goto(base_url, wait_until="domcontentloaded")

        resp = page.evaluate(f"""
            fetch('/auth/test-login', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{secret: '{secret}'}})
            }}).then(r => r.json()).catch(e => ({{error: e.message}}))
        """)
        print(f"Mobile auth: {json.dumps(resp)}")

        page.goto(base_url + "/", wait_until="networkidle")
        page.wait_for_timeout(2000)

        mobile_path = os.path.join(screenshot_dir, f"round-{round_num}-mobile.png")
        page.screenshot(path=mobile_path, full_page=True)
        print(f"Saved: {mobile_path}")

        nav = page.locator("nav").first
        if nav.is_visible():
            nav_path = os.path.join(screenshot_dir, f"round-{round_num}-nav-mobile.png")
            nav.screenshot(path=nav_path)
            print(f"Saved: {nav_path}")

        context.close()
        browser.close()

    print(f"Round {round_num} screenshots complete")
    return screenshot_dir


def take_local_screenshots(round_num=2, port=5099, secret=None):
    """Take screenshots from local dev server."""
    base_url = f"http://127.0.0.1:{port}"
    if not secret:
        secret = os.environ.get("TEST_LOGIN_SECRET", "")
    return take_screenshots(round_num=round_num, base_url=base_url, secret=secret)


if __name__ == "__main__":
    round_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    secret = sys.argv[2] if len(sys.argv) > 2 else "F0C_xLnjQV4wjVA_OgbbGM12Sf2qw5-Dpy0wLXvp104"

    if len(sys.argv) > 3 and sys.argv[3] == "local":
        port = int(sys.argv[4]) if len(sys.argv) > 4 else 5099
        take_local_screenshots(round_num=round_num, port=port, secret=secret)
    else:
        take_screenshots(round_num=round_num, secret=secret)
