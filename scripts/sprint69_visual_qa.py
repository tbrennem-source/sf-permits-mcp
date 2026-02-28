#!/usr/bin/env python3
"""Sprint 69 Visual QA — Obsidian Intelligence Redesign.

Standalone script that checks all Sprint 69 pages at 3 viewports with
Obsidian theme-specific assertions (dark bg, cyan accent, font loading,
no horizontal overflow).

Usage:
    cd /Users/timbrenneman/AIprojects/sf-permits-mcp
    source .venv/bin/activate

    # Get TEST_LOGIN_SECRET:
    railway variables --json 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('TEST_LOGIN_SECRET',''))"

    # Run:
    TEST_LOGIN_SECRET=<secret> python scripts/sprint69_visual_qa.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://sfpermits-ai-staging-production.up.railway.app"
SPRINT = "sprint69"

PAGES = [
    # Public pages (no auth)
    {"slug": "landing", "path": "/", "auth": "public", "obsidian": True},
    {"slug": "search-results", "path": "/search?q=1455+Market+St", "auth": "public", "obsidian": True},
    {"slug": "methodology", "path": "/methodology", "auth": "public", "obsidian": True},
    {"slug": "about-data", "path": "/about-data", "auth": "public", "obsidian": True},
    {"slug": "demo", "path": "/demo", "auth": "public", "obsidian": True},
    {"slug": "login", "path": "/auth/login", "auth": "public", "obsidian": False},
    {"slug": "property-report", "path": "/report/3512/035", "auth": "public", "obsidian": False},
    # Auth pages
    {"slug": "account", "path": "/account", "auth": "auth", "obsidian": False},
    {"slug": "brief", "path": "/brief", "auth": "auth", "obsidian": False},
    {"slug": "portfolio", "path": "/portfolio", "auth": "auth", "obsidian": False},
    # Admin pages
    {"slug": "admin-ops", "path": "/admin/ops", "auth": "admin", "obsidian": False},
    {"slug": "admin-feedback", "path": "/admin/feedback", "auth": "admin", "obsidian": False},
]

VIEWPORTS = {
    "mobile": {"width": 375, "height": 812},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 900},
}

QA_ROOT = Path("qa-results")
SCREENSHOTS_DIR = QA_ROOT / "screenshots" / f"{SPRINT}-visual"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PageResult:
    slug: str
    viewport: str
    screenshot_path: str = ""
    status: str = "PASS"  # PASS, FAIL, SKIP
    notes: list[str] = field(default_factory=list)

    def fail(self, msg: str):
        self.status = "FAIL"
        self.notes.append(f"FAIL: {msg}")

    def warn(self, msg: str):
        self.notes.append(f"WARN: {msg}")

    def ok(self, msg: str):
        self.notes.append(f"OK: {msg}")


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def login_via_test_secret(page, base_url: str, role: str, secret: str) -> bool:
    """Authenticate using the test-login endpoint."""
    email = f"test-{role}@sfpermits.ai" if role == "admin" else "test-user@sfpermits.ai"
    try:
        resp = page.request.post(
            f"{base_url}/auth/test-login",
            data=json.dumps({"email": email, "secret": secret}),
            headers={"Content-Type": "application/json"},
        )
        return resp.status in (200, 302)
    except Exception as e:
        print(f"  Login failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Obsidian theme checks
# ---------------------------------------------------------------------------

def check_obsidian_theme(page, result: PageResult) -> None:
    """Check Obsidian design system elements on the page."""
    # Check body has obsidian class
    body_classes = page.evaluate("document.body.className")
    if "obsidian" in body_classes:
        result.ok("body.obsidian class present")
    else:
        result.fail("body.obsidian class NOT present")

    # Check background color (should be dark: #0B0F19 or similar)
    bg_color = page.evaluate(
        "window.getComputedStyle(document.body).backgroundColor"
    )
    if bg_color:
        # Parse rgb(r, g, b) and check if dark
        try:
            rgb = bg_color.replace("rgb(", "").replace(")", "").split(",")
            r, g, b = int(rgb[0].strip()), int(rgb[1].strip()), int(rgb[2].strip())
            luminance = (r * 299 + g * 587 + b * 114) / 1000
            if luminance < 30:
                result.ok(f"Dark background ({bg_color})")
            else:
                result.fail(f"Background not dark enough: {bg_color} (luminance={luminance:.0f})")
        except Exception:
            result.warn(f"Could not parse background color: {bg_color}")

    # Check for cyan accent (#22D3EE) presence anywhere in computed styles
    has_cyan = page.evaluate("""() => {
        const elements = document.querySelectorAll('*');
        for (const el of elements) {
            const style = window.getComputedStyle(el);
            const color = style.color;
            const bg = style.backgroundColor;
            const border = style.borderColor;
            // Check for cyan-ish colors (r < 80, g > 180, b > 200)
            for (const c of [color, bg, border]) {
                if (c && c.startsWith('rgb')) {
                    const match = c.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (match) {
                        const [_, r, g, b] = match.map(Number);
                        if (r < 80 && g > 180 && b > 200) return true;
                    }
                }
            }
        }
        return false;
    }""")
    if has_cyan:
        result.ok("Cyan accent (#22D3EE) detected")
    else:
        result.warn("Cyan accent not detected in computed styles")

    # Check font loading (JetBrains Mono + IBM Plex Sans)
    fonts_loaded = page.evaluate("""() => {
        const fonts = {jetbrains: false, ibmplex: false};
        try {
            document.fonts.forEach(f => {
                if (f.family.includes('JetBrains')) fonts.jetbrains = true;
                if (f.family.includes('IBM Plex')) fonts.ibmplex = true;
            });
        } catch(e) {}
        return fonts;
    }""")
    if fonts_loaded.get("jetbrains"):
        result.ok("JetBrains Mono font loaded")
    else:
        result.warn("JetBrains Mono font NOT detected (may be loading)")

    if fonts_loaded.get("ibmplex"):
        result.ok("IBM Plex Sans font loaded")
    else:
        result.warn("IBM Plex Sans font NOT detected (may be loading)")


def check_no_horizontal_overflow(page, result: PageResult, viewport_width: int) -> None:
    """Check that nothing causes horizontal scrolling."""
    overflow = page.evaluate("""() => {
        return {
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            bodyScrollWidth: document.body.scrollWidth,
        }
    }""")
    scroll_w = overflow.get("scrollWidth", 0)
    client_w = overflow.get("clientWidth", 0)

    if scroll_w > client_w + 5:  # 5px tolerance
        result.fail(f"Horizontal overflow: scrollWidth={scroll_w} > clientWidth={client_w}")
    else:
        result.ok(f"No horizontal overflow (scrollWidth={scroll_w}, clientWidth={client_w})")


def check_api_stats(page, result: PageResult) -> None:
    """Verify /api/stats returns valid JSON."""
    resp = page.request.get(f"{BASE_URL}/api/stats")
    if resp.status != 200:
        result.fail(f"/api/stats returned status {resp.status}")
        return

    try:
        data = resp.json()
        if "permits" in data:
            result.ok(f"/api/stats: permits={data.get('permits')}, entities={data.get('entities')}")
        else:
            result.fail(f"/api/stats JSON missing 'permits' key: {list(data.keys())}")
    except Exception as e:
        result.fail(f"/api/stats JSON parse error: {e}")


def check_robots_txt(page, result: PageResult) -> None:
    """Verify robots.txt has expected content."""
    resp = page.request.get(f"{BASE_URL}/robots.txt")
    if resp.status != 200:
        result.fail(f"/robots.txt returned status {resp.status}")
        return

    text = resp.text()
    if "Disallow: /admin/" in text and "Allow:" in text:
        result.ok("robots.txt has Allow + Disallow directives")
    elif "Disallow: /" in text:
        result.warn("robots.txt still has full Disallow: / (beta mode)")
    else:
        result.warn(f"robots.txt content unexpected: {text[:200]}")

    if "Sitemap:" in text:
        result.ok("robots.txt has Sitemap reference")
    else:
        result.warn("robots.txt missing Sitemap reference")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_qa() -> list[PageResult]:
    from playwright.sync_api import sync_playwright

    test_secret = os.environ.get("TEST_LOGIN_SECRET", "")
    if not test_secret:
        print("WARNING: TEST_LOGIN_SECRET not set -- auth/admin pages will be skipped")

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results: list[PageResult] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for vp_name, vp_size in VIEWPORTS.items():
            print(f"\n=== {vp_name.upper()} ({vp_size['width']}x{vp_size['height']}) ===")

            context = browser.new_context(
                viewport=vp_size,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Login as admin (covers auth + admin pages)
            logged_in = False
            if test_secret:
                logged_in = login_via_test_secret(page, BASE_URL, "admin", test_secret)
                if logged_in:
                    print("  Logged in as admin")
                else:
                    print("  Login FAILED")

            for page_def in PAGES:
                slug = page_def["slug"]
                path = page_def["path"]
                auth_level = page_def["auth"]
                is_obsidian = page_def["obsidian"]

                result = PageResult(slug=slug, viewport=vp_name)

                # Skip auth pages if not logged in
                if auth_level in ("auth", "admin") and not logged_in:
                    result.status = "SKIP"
                    result.notes.append("SKIP: no auth")
                    all_results.append(result)
                    print(f"  {slug}: SKIP (no auth)")
                    continue

                url = f"{BASE_URL}{path}"
                screenshot_path = SCREENSHOTS_DIR / f"{slug}-{vp_name}.png"
                result.screenshot_path = str(screenshot_path)

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Wait for fonts and JS to settle
                    page.wait_for_timeout(2500)

                    # Take screenshot
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    result.ok(f"Screenshot saved: {screenshot_path.name}")

                    # Obsidian-specific checks
                    if is_obsidian:
                        check_obsidian_theme(page, result)

                    # Horizontal overflow check (especially at mobile)
                    check_no_horizontal_overflow(page, result, vp_size["width"])

                    # Check page title is not empty
                    title = page.title()
                    if title:
                        result.ok(f"Page title: {title[:60]}")
                    else:
                        result.warn("Page title is empty")

                    # Check for JS errors in console
                    # (We can only check for visible error indicators)
                    error_elements = page.locator(".error, .alert-danger, [class*='error']").count()
                    if error_elements > 0:
                        result.warn(f"Found {error_elements} error-like elements on page")

                except Exception as e:
                    result.fail(f"Navigation/screenshot error: {e}")

                all_results.append(result)

                # Status display
                fails = [n for n in result.notes if n.startswith("FAIL")]
                status_str = "FAIL" if fails else result.status
                print(f"  {slug}: {status_str}" + (f" -- {fails[0]}" if fails else ""))

                # Pace requests
                page.wait_for_timeout(500)

            # Extra checks (only on desktop pass)
            if vp_name == "desktop":
                print("\n  --- Extra endpoint checks ---")

                # /api/stats
                api_result = PageResult(slug="api-stats", viewport="desktop")
                check_api_stats(page, api_result)
                all_results.append(api_result)
                print(f"  api-stats: {api_result.status} -- {'; '.join(api_result.notes)}")

                # /robots.txt
                robots_result = PageResult(slug="robots-txt", viewport="desktop")
                check_robots_txt(page, robots_result)
                all_results.append(robots_result)
                print(f"  robots-txt: {robots_result.status} -- {'; '.join(robots_result.notes)}")

            page.close()
            context.close()

        browser.close()

    return all_results


def write_results(results: list[PageResult]) -> Path:
    """Write markdown results file."""
    output_path = QA_ROOT / f"{SPRINT}-visual-results.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Sprint 69 Visual QA — Obsidian Intelligence Redesign",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Staging: {BASE_URL}",
        "",
    ]

    # Summary counts
    pass_count = sum(1 for r in results if r.status == "PASS" and not any(n.startswith("FAIL") for n in r.notes))
    fail_count = sum(1 for r in results if r.status == "FAIL" or any(n.startswith("FAIL") for n in r.notes))
    skip_count = sum(1 for r in results if r.status == "SKIP")
    lines.append(f"**Summary:** {pass_count} PASS / {fail_count} FAIL / {skip_count} SKIP")
    lines.append("")

    # Group by viewport
    viewports_seen = []
    for r in results:
        if r.viewport not in viewports_seen:
            viewports_seen.append(r.viewport)

    for vp in viewports_seen:
        vp_results = [r for r in results if r.viewport == vp]
        vp_size = VIEWPORTS.get(vp, {})
        w = vp_size.get("width", "?")
        h = vp_size.get("height", "?")
        lines.append(f"## {vp.title()} ({w}x{h})")
        lines.append("")
        lines.append("| Page | Status | Notes |")
        lines.append("|------|--------|-------|")

        for r in vp_results:
            has_fail = any(n.startswith("FAIL") for n in r.notes)
            status = "FAIL" if has_fail else r.status
            # Compact notes
            notes_str = "; ".join(r.notes) if r.notes else "-"
            if len(notes_str) > 200:
                notes_str = notes_str[:200] + "..."
            lines.append(f"| {r.slug} | {status} | {notes_str} |")

        lines.append("")

    # Obsidian theme checks summary
    lines.append("## Obsidian Theme Check Summary")
    lines.append("")
    obsidian_pages = ["landing", "search-results", "methodology", "about-data", "demo"]
    for vp in viewports_seen:
        lines.append(f"### {vp.title()}")
        for slug in obsidian_pages:
            matching = [r for r in results if r.slug == slug and r.viewport == vp]
            if matching:
                r = matching[0]
                has_fail = any(n.startswith("FAIL") for n in r.notes)
                status = "FAIL" if has_fail else "PASS"
                theme_notes = [n for n in r.notes if any(k in n for k in ["obsidian", "Dark", "Cyan", "JetBrains", "IBM", "overflow"])]
                lines.append(f"- **{slug}**: {status} -- {'; '.join(theme_notes) if theme_notes else 'no theme-specific notes'}")
        lines.append("")

    output_path.write_text("\n".join(lines))
    return output_path


def main() -> int:
    print(f"Sprint 69 Visual QA — Obsidian Intelligence Redesign")
    print(f"Target: {BASE_URL}")
    print(f"Pages: {len(PAGES)} | Viewports: {len(VIEWPORTS)}")
    print(f"Screenshots: {SCREENSHOTS_DIR}")
    print()

    results = run_qa()

    output_path = write_results(results)

    # Final summary
    pass_count = sum(1 for r in results if r.status == "PASS" and not any(n.startswith("FAIL") for n in r.notes))
    fail_count = sum(1 for r in results if r.status == "FAIL" or any(n.startswith("FAIL") for n in r.notes))
    skip_count = sum(1 for r in results if r.status == "SKIP")

    print(f"\n{'='*60}")
    print(f"RESULTS: {pass_count} PASS / {fail_count} FAIL / {skip_count} SKIP")
    print(f"Report: {output_path}")
    print(f"Screenshots: {SCREENSHOTS_DIR}")
    print(f"{'='*60}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
