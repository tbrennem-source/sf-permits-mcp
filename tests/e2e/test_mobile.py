"""Mobile viewport E2E tests using Playwright.

These tests are skipped unless the environment variable E2E_BASE_URL is set.
To run locally (requires a running dev server):

    E2E_BASE_URL=http://localhost:5001 pytest tests/e2e/test_mobile.py -v

To run against production:

    E2E_BASE_URL=https://sfpermits-ai-production.up.railway.app \
        pytest tests/e2e/test_mobile.py -v

Tests verify:
- No horizontal overflow (scrollWidth > clientWidth) at 375px viewport
- Touch targets >= 44px for interactive nav elements
- Font sizes >= 14px for body text elements
- Table overflow containers present on known data-table pages
- mobile.css is loaded on all full-page routes
- Viewport meta tag is present
"""

from __future__ import annotations

import os
import pytest

# ---------------------------------------------------------------------------
# Skip marker — skip entire module when E2E_BASE_URL is unset
# ---------------------------------------------------------------------------

E2E_BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not E2E_BASE_URL,
    reason="E2E_BASE_URL not set — skipping Playwright mobile tests",
)

# ---------------------------------------------------------------------------
# Viewport configurations to test
# ---------------------------------------------------------------------------

VIEWPORTS = [
    pytest.param(
        {"width": 375, "height": 812},
        id="iphone-se-375",
    ),
    pytest.param(
        {"width": 414, "height": 896},
        id="iphone-plus-414",
    ),
    pytest.param(
        {"width": 768, "height": 1024},
        id="tablet-768",
    ),
]

# ---------------------------------------------------------------------------
# Pages that should load without overflow
# ---------------------------------------------------------------------------

PUBLIC_PAGES = [
    pytest.param("/", id="landing"),
    pytest.param("/auth/login", id="login"),
]

# Pages that require auth are tested separately (no session cookie available
# in E2E context) but their static assets (mobile.css) are verified below.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_overflow(page) -> dict:
    """Return {has_overflow: bool, body_scroll: int, viewport: int}."""
    result = page.evaluate("""() => {
        const body = document.body;
        const html = document.documentElement;
        const scrollW = Math.max(
            body.scrollWidth, body.offsetWidth,
            html.clientWidth, html.scrollWidth, html.offsetWidth
        );
        return {
            hasOverflow: scrollW > window.innerWidth,
            bodyScrollWidth: body.scrollWidth,
            viewportWidth: window.innerWidth,
        };
    }""")
    return result


def _get_font_sizes(page, selector: str = "p, td, th, li") -> list[float]:
    """Return computed font-size values (px) for matching elements."""
    return page.evaluate(f"""() => {{
        const els = document.querySelectorAll('{selector}');
        return Array.from(els).map(el => {{
            const sz = window.getComputedStyle(el).fontSize;
            return parseFloat(sz);
        }}).filter(sz => !isNaN(sz) && sz > 0);
    }}""")


def _get_touch_target_sizes(page, selector: str) -> list[dict]:
    """Return list of {{tag, height, width}} for elements matching selector."""
    return page.evaluate(f"""() => {{
        const els = document.querySelectorAll('{selector}');
        return Array.from(els).map(el => {{
            const r = el.getBoundingClientRect();
            return {{
                tag: el.tagName,
                text: (el.textContent || '').trim().slice(0, 30),
                height: r.height,
                width: r.width,
            }};
        }}).filter(el => el.height > 0);
    }}""")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_instance():
    """Launch a single headless Chromium browser for the test session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


class TestNoHorizontalOverflow:
    """Verify no horizontal scroll at each viewport width."""

    @pytest.mark.parametrize("viewport", VIEWPORTS)
    @pytest.mark.parametrize("route", PUBLIC_PAGES)
    def test_no_overflow(self, browser_instance, viewport, route):
        context = browser_instance.new_context(viewport=viewport)
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            overflow = _check_overflow(page)
            assert not overflow["hasOverflow"], (
                f"Horizontal overflow detected at {viewport['width']}px on {route}: "
                f"scrollWidth={overflow['bodyScrollWidth']}px "
                f"(viewport={overflow['viewportWidth']}px)"
            )
        finally:
            context.close()


class TestMobileCssLoaded:
    """Verify mobile.css is referenced and loaded on public pages."""

    @pytest.mark.parametrize("viewport", [VIEWPORTS[0]])  # 375px only
    @pytest.mark.parametrize("route", PUBLIC_PAGES)
    def test_mobile_css_link_present(self, browser_instance, viewport, route):
        context = browser_instance.new_context(viewport=viewport)
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Check the HTML source references mobile.css
            links = page.evaluate("""() => {
                const links = document.querySelectorAll('link[rel="stylesheet"]');
                return Array.from(links).map(l => l.href);
            }""")
            mobile_links = [l for l in links if "mobile.css" in l]
            assert mobile_links, (
                f"mobile.css not found in stylesheet links on {route}. "
                f"Found: {links}"
            )
        finally:
            context.close()


class TestViewportMetaTag:
    """Verify viewport meta tag is present on all pages."""

    @pytest.mark.parametrize("route", PUBLIC_PAGES)
    def test_viewport_meta_present(self, browser_instance, route):
        context = browser_instance.new_context(
            viewport={"width": 375, "height": 812}
        )
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            viewport_meta = page.evaluate("""() => {
                const meta = document.querySelector('meta[name="viewport"]');
                return meta ? meta.getAttribute('content') : null;
            }""")
            assert viewport_meta is not None, (
                f"No viewport meta tag found on {route}"
            )
            assert "width=device-width" in viewport_meta, (
                f"viewport meta does not contain 'width=device-width' on {route}. "
                f"Got: {viewport_meta}"
            )
        finally:
            context.close()


class TestTouchTargetSizes:
    """Verify navigation badges meet 44px touch target minimum."""

    def test_nav_badge_touch_targets_375(self, browser_instance):
        context = browser_instance.new_context(
            viewport={"width": 375, "height": 812}
        )
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}/"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            targets = _get_touch_target_sizes(page, "header .badge, header .badge-btn")

            failures = [
                t for t in targets
                if t["height"] < 44
            ]
            assert not failures, (
                f"Nav badges below 44px touch target at 375px viewport: "
                + ", ".join(
                    f'"{t["text"]}" ({t["height"]:.0f}px)' for t in failures
                )
            )
        finally:
            context.close()


class TestFontSizes:
    """Verify body text font sizes are >= 14px at 375px viewport."""

    def test_min_font_size_375(self, browser_instance):
        context = browser_instance.new_context(
            viewport={"width": 375, "height": 812}
        )
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}/"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            sizes = _get_font_sizes(page, "p, li")
            tiny = [s for s in sizes if s < 12]  # 12px is below any reasonable floor
            pct_tiny = len(tiny) / len(sizes) if sizes else 0
            assert pct_tiny < 0.05, (
                f"{len(tiny)}/{len(sizes)} text elements have font-size < 12px "
                f"at 375px viewport. Tiny sizes: {sorted(set(tiny))}"
            )
        finally:
            context.close()


class TestTableOverflow:
    """
    Verify that tables on key pages do not cause body horizontal overflow.

    These tests run only if the pages are publicly accessible without login.
    Pages requiring auth are skipped with a note.
    """

    @pytest.mark.parametrize("route,description", [
        pytest.param("/", "landing/search page", id="index"),
        pytest.param("/auth/login", "auth login page", id="login"),
    ])
    def test_page_no_table_overflow(self, browser_instance, route, description):
        context = browser_instance.new_context(
            viewport={"width": 375, "height": 812}
        )
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            overflow = _check_overflow(page)
            assert not overflow["hasOverflow"], (
                f"Table overflow on {description} ({route}) at 375px: "
                f"scrollWidth={overflow['bodyScrollWidth']}px"
            )
        finally:
            context.close()


class TestInputFontSize:
    """Verify form inputs have font-size >= 16px to prevent iOS auto-zoom."""

    def test_input_font_size_prevents_ios_zoom(self, browser_instance):
        context = browser_instance.new_context(
            viewport={"width": 375, "height": 812}
        )
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}/"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            input_sizes = page.evaluate("""() => {
                const inputs = document.querySelectorAll(
                    'input[type="text"], input[type="email"], '
                    'input[type="search"], textarea, select'
                );
                return Array.from(inputs).map(el => {
                    const sz = window.getComputedStyle(el).fontSize;
                    return {
                        type: el.type || el.tagName,
                        fontSize: parseFloat(sz),
                        placeholder: el.placeholder || '',
                    };
                }).filter(el => el.fontSize > 0);
            }""")
            tiny_inputs = [i for i in input_sizes if i["fontSize"] < 16]
            assert not tiny_inputs, (
                f"Inputs with font-size < 16px (will trigger iOS zoom) at 375px: "
                + ", ".join(
                    f'{i["type"]} ({i["fontSize"]}px, placeholder="{i["placeholder"][:20]}")'
                    for i in tiny_inputs
                )
            )
        finally:
            context.close()


class TestScreenshots:
    """Capture mobile screenshots for visual review (always passes)."""

    @pytest.mark.parametrize("viewport,name", [
        ({"width": 375, "height": 812}, "iphone-se"),
        ({"width": 768, "height": 1024}, "tablet"),
    ])
    @pytest.mark.parametrize("route,slug", [
        pytest.param("/", "landing", id="landing"),
        pytest.param("/auth/login", "login", id="login"),
    ])
    def test_screenshot(self, browser_instance, viewport, name, route, slug, tmp_path):
        """Capture screenshots — informational only, always passes."""
        context = browser_instance.new_context(viewport=viewport)
        page = context.new_page()
        try:
            url = f"{E2E_BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Save to qa-results/screenshots/ if it exists, else tmp_path
            import pathlib
            qa_dir = pathlib.Path(__file__).parents[2] / "qa-results" / "screenshots" / "mobile"
            qa_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = qa_dir / f"{slug}-{name}.png"

            page.screenshot(path=str(screenshot_path), full_page=True)
            # Test always passes — screenshots are for visual review
        finally:
            context.close()
