#!/usr/bin/env python3
"""Take screenshots from local dev server."""
import os, sys, json

def main():
    from playwright.sync_api import sync_playwright

    round_num = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5099
    secret = sys.argv[3] if len(sys.argv) > 3 else "F0C_xLnjQV4wjVA_OgbbGM12Sf2qw5-Dpy0wLXvp104"
    base_url = f"http://127.0.0.1:{port}"

    screenshot_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "qa-results", "screenshots", "dashboard-loop"
    )
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Desktop 1280x720
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

        path = os.path.join(screenshot_dir, f"round-{round_num}-desktop.png")
        page.screenshot(path=path, full_page=True)
        print(f"Saved: {path}")

        nav = page.locator("header").first
        if nav.is_visible():
            nav_path = os.path.join(screenshot_dir, f"round-{round_num}-nav-desktop.png")
            nav.screenshot(path=nav_path)
            print(f"Saved: {nav_path}")

        context.close()

        # Mobile 375x812
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

        path = os.path.join(screenshot_dir, f"round-{round_num}-mobile.png")
        page.screenshot(path=path, full_page=True)
        print(f"Saved: {path}")

        nav = page.locator("header").first
        if nav.is_visible():
            nav_path = os.path.join(screenshot_dir, f"round-{round_num}-nav-mobile.png")
            nav.screenshot(path=nav_path)
            print(f"Saved: {nav_path}")

        context.close()
        browser.close()

    print(f"Round {round_num} screenshots complete")

if __name__ == "__main__":
    main()
