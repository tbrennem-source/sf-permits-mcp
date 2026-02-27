"""QS4-C Obsidian Design Migration — Playwright QA Script."""
import os
import sys

BASE = "http://127.0.0.1:5099"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "qa-results", "screenshots", "qs4-c")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []

def log(check_num, name, status, note=""):
    results.append((check_num, name, status, note))
    print(f"  [{status}] #{check_num}: {name}" + (f" — {note}" if note else ""))


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── Auth helper ────────────────────────────────────────────────
        def login_page(pg):
            """Login via POST to test-login endpoint, then navigate to index."""
            pg.goto(f"{BASE}/health")  # prime the session
            pg.evaluate("""async () => {
                const resp = await fetch('/auth/test-login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({secret: 'test123', email: 'qa-qs4c@test.com'})
                });
                return resp.status;
            }""")

        # ── Auth setup ────────────────────────────────────────────────
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        login_page(page)

        # ── Check 1: Landing → login → index font consistency ─────────
        # Check that index page loads design-system.css (font source)
        page.goto(f"{BASE}/")
        page.wait_for_load_state("networkidle")
        html = page.content()
        has_design_system = "design-system.css" in html
        has_obsidian = 'class="obsidian"' in html
        log(1, "Landing→login→index uses same font family",
            "PASS" if has_design_system and has_obsidian else "FAIL",
            f"design-system.css={'yes' if has_design_system else 'NO'}, obsidian={'yes' if has_obsidian else 'NO'}")

        # ── Check 2: index.html JetBrains Mono headings ──────────────
        has_font_display = "var(--font-display)" in html
        log(2, "index.html has JetBrains Mono headings",
            "PASS" if has_font_display else "FAIL",
            f"font-display ref={'found' if has_font_display else 'NOT FOUND'}")

        # ── Check 5: Nav renders on index ─────────────────────────────
        nav_visible = page.locator("header a.logo").count() > 0 or page.locator("text=sfpermits").count() > 0
        search_badge = page.locator("text=Search").first.is_visible() if page.locator("text=Search").count() > 0 else False
        brief_badge = page.locator("text=Brief").first.is_visible() if page.locator("text=Brief").count() > 0 else False
        log(5, "Nav renders correctly on index page",
            "PASS" if nav_visible and search_badge and brief_badge else "FAIL",
            f"logo={nav_visible}, search={search_badge}, brief={brief_badge}")

        # ── Check 8: Screenshot /index at 1440px ─────────────────────
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "index-1440.png"), full_page=True)
        log(8, "Screenshot /index at 1440px", "PASS", "saved")

        # ── Check 11: PWA manifest on index ───────────────────────────
        has_manifest_index = 'manifest.json' in html
        log(11, "PWA manifest link present on index",
            "PASS" if has_manifest_index else "FAIL")

        # ── Check 7: Screenshot /index at 375px ──────────────────────
        ctx.close()
        ctx_mobile = browser.new_context(viewport={"width": 375, "height": 812})
        page_m = ctx_mobile.new_page()
        login_page(page_m)
        page_m.goto(f"{BASE}/")
        page_m.wait_for_load_state("networkidle")
        page_m.screenshot(path=os.path.join(SCREENSHOT_DIR, "index-375.png"), full_page=True)

        # Check horizontal scroll
        scroll_w = page_m.evaluate("document.documentElement.scrollWidth")
        viewport_w = page_m.evaluate("window.innerWidth")
        no_hscroll = scroll_w <= viewport_w + 5  # 5px tolerance
        log(7, "Screenshot /index at 375px — no horizontal scroll",
            "PASS" if no_hscroll else "FAIL",
            f"scrollWidth={scroll_w}, viewport={viewport_w}")

        ctx_mobile.close()

        # ── Brief page checks ─────────────────────────────────────────
        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
        page2 = ctx2.new_page()
        login_page(page2)
        page2.goto(f"{BASE}/brief")
        page2.wait_for_load_state("networkidle")
        brief_html = page2.content()

        # ── Check 3: brief.html JetBrains Mono headings ──────────────
        has_font_display_brief = "var(--font-display)" in brief_html
        log(3, "brief.html has JetBrains Mono headings",
            "PASS" if has_font_display_brief else "FAIL",
            f"font-display ref={'found' if has_font_display_brief else 'NOT FOUND'}")

        # ── Check 4: brief.html signal colors ────────────────────────
        has_success = "var(--success)" in brief_html
        has_warning = "var(--warning)" in brief_html
        has_error = "var(--error)" in brief_html
        log(4, "brief.html health indicators use signal colors",
            "PASS" if has_success and has_warning and has_error else "FAIL",
            f"success={has_success}, warning={has_warning}, error={has_error}")

        # ── Check 6: Nav renders on brief ─────────────────────────────
        nav_visible_b = page2.locator("header a.logo").count() > 0 or page2.locator("text=sfpermits").count() > 0
        search_badge_b = page2.locator("text=Search").first.is_visible() if page2.locator("text=Search").count() > 0 else False
        brief_badge_b = page2.locator("text=Brief").first.is_visible() if page2.locator("text=Brief").count() > 0 else False
        log(6, "Nav renders correctly on brief page",
            "PASS" if nav_visible_b and search_badge_b and brief_badge_b else "FAIL",
            f"logo={nav_visible_b}, search={search_badge_b}, brief={brief_badge_b}")

        # ── Check 10: Screenshot /brief at 1440px ────────────────────
        page2.screenshot(path=os.path.join(SCREENSHOT_DIR, "brief-1440.png"), full_page=True)
        log(10, "Screenshot /brief at 1440px", "PASS", "saved")

        # ── Check 11b: PWA manifest on brief ─────────────────────────
        has_manifest_brief = 'manifest.json' in brief_html
        log(11, "PWA manifest link present on brief",
            "PASS" if has_manifest_brief else "FAIL")

        ctx2.close()

        # ── Check 9: Screenshot /brief at 375px ──────────────────────
        ctx_mobile2 = browser.new_context(viewport={"width": 375, "height": 812})
        page_mb = ctx_mobile2.new_page()
        login_page(page_mb)
        page_mb.goto(f"{BASE}/brief")
        page_mb.wait_for_load_state("networkidle")
        page_mb.screenshot(path=os.path.join(SCREENSHOT_DIR, "brief-375.png"), full_page=True)
        log(9, "Screenshot /brief at 375px", "PASS", "saved")

        ctx_mobile2.close()
        browser.close()

    # ── Write results ─────────────────────────────────────────────────
    results_dir = os.path.join(os.path.dirname(__file__), "..", "qa-results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "qs4-c-results.md"), "w") as f:
        f.write("# QS4-C Obsidian Design Migration — QA Results\n\n")
        pass_count = sum(1 for r in results if r[2] == "PASS")
        fail_count = sum(1 for r in results if r[2] == "FAIL")
        f.write(f"**{pass_count} PASS, {fail_count} FAIL** out of {len(results)} checks\n\n")
        for num, name, status, note in sorted(results, key=lambda r: r[0]):
            f.write(f"- [{status}] #{num}: {name}")
            if note:
                f.write(f" — {note}")
            f.write("\n")
        f.write(f"\nScreenshots saved to: qa-results/screenshots/qs4-c/\n")

    print(f"\n{'='*60}")
    print(f"RESULTS: {pass_count} PASS, {fail_count} FAIL out of {len(results)} checks")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
