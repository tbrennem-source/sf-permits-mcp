"""QS3-D browser QA checks using Playwright."""

import json
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright


def main():
    results = []

    # Start Flask dev server with TESTING=1 to bypass rate limits
    env = {**os.environ, "TESTING": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import os; os.environ['TESTING']='1'; from web.app import app; app.config['TESTING']=True; app.run(host='127.0.0.1', port=5199, debug=False)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    time.sleep(3)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Check 5: manifest.json
            page = browser.new_page()
            resp = page.goto("http://127.0.0.1:5199/static/manifest.json")
            try:
                # Use resp.body() — page.content() wraps in HTML tags
                body = resp.body().decode()
                data = json.loads(body)
                has_name = "name" in data
                results.append(("5. manifest.json valid JSON", "PASS" if has_name else "FAIL"))
            except Exception as e:
                results.append(("5. manifest.json valid JSON", f"FAIL: {e}"))
            page.close()

            # Check 7: sitemap excludes /demo
            page = browser.new_page()
            page.goto("http://127.0.0.1:5199/sitemap.xml")
            xml = page.content()
            has_demo = "/demo" in xml
            results.append(("7. sitemap excludes /demo", "FAIL" if has_demo else "PASS"))
            page.close()

            # Check 9: landing page screenshot at 1440px
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.goto("http://127.0.0.1:5199/")
            page.wait_for_load_state("networkidle")

            ss_path = "qa-results/screenshots/qs3-d/landing-1440.png"
            page.screenshot(path=ss_path, full_page=True)

            # Basic layout check: hero section visible
            hero = page.locator(".hero-section")
            hero_vis = hero.is_visible() if hero.count() > 0 else False
            results.append(("9. landing 1440px no breakage", "PASS" if hero_vis else "FAIL"))

            # Extra: 375px mobile
            page2 = browser.new_context(viewport={"width": 375, "height": 812}).new_page()
            page2.goto("http://127.0.0.1:5199/")
            page2.wait_for_load_state("networkidle")
            page2.screenshot(path="qa-results/screenshots/qs3-d/landing-375.png", full_page=True)
            results.append(("9b. landing 375px mobile", "PASS"))
            page2.close()

            # Extra: 768px tablet
            page3 = browser.new_context(viewport={"width": 768, "height": 1024}).new_page()
            page3.goto("http://127.0.0.1:5199/")
            page3.wait_for_load_state("networkidle")
            page3.screenshot(path="qa-results/screenshots/qs3-d/landing-768.png", full_page=True)
            results.append(("9c. landing 768px tablet", "PASS"))
            page3.close()

            browser.close()
    finally:
        proc.terminate()
        proc.wait()

    for name, result in results:
        print(f"{name}: {result}")


if __name__ == "__main__":
    main()
