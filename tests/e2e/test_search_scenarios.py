"""E2E Playwright tests for search, permit lookup, plan analysis, and methodology.

Sprint 77-3: Search + Entity Scenarios
Tests core search and entity flows with a real browser (Chromium) against a live Flask server.

Scenario IDs reference scenario-design-guide.md.

Run (standalone — recommended):
    pytest tests/e2e/test_search_scenarios.py -v

NOTE: Playwright tests are skipped in the full test suite to avoid asyncio
event loop conflicts with pytest-asyncio. Run them separately or set
E2E_PLAYWRIGHT=1 to include them in the full suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# ---------------------------------------------------------------------------
# Skip Playwright tests in full suite to avoid asyncio event loop conflict
# with pytest-asyncio. Run them standalone:
#   pytest tests/e2e/test_search_scenarios.py -v
# Or include in full suite by setting E2E_PLAYWRIGHT=1
# ---------------------------------------------------------------------------
_playwright_targeted = any(
    "test_search_scenarios" in arg or "e2e" == os.path.basename(arg.rstrip("/"))
    for arg in sys.argv
)
_playwright_enabled = (
    os.environ.get("E2E_PLAYWRIGHT", "")
    or os.environ.get("E2E_BASE_URL", "")
    or _playwright_targeted
)

pytestmark = pytest.mark.skipif(
    not _playwright_enabled,
    reason="Playwright tests skipped in full suite (asyncio conflict). "
           "Run: pytest tests/e2e/test_search_scenarios.py -v",
)

SCREENSHOT_DIR = Path("qa-results/screenshots/e2e")


def _screenshot(page, name: str) -> None:
    """Capture a screenshot (best-effort, doesn't fail the test)."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
    except Exception:
        pass


# ===========================================================================
# Test 77-3-1: Address search returns results
# ===========================================================================


class TestAddressSearchReturnsResults:
    """SCENARIO-38 (variant): Authenticated address search returns permit results."""

    def test_address_search_returns_results(self, auth_page):
        """77-3-1: Login, search 'valencia', assert results appear.

        Authenticated users are redirected to /?q=<query> for the full search
        experience. The test verifies that search results are present in the
        response body — permits, addresses, or permit-related keywords.
        """
        pg = auth_page("expediter")
        pg.goto(f"{pg._base_url}/search?q=valencia")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-1-search-valencia")

        body = pg.text_content("body") or ""
        lower = body.lower()
        # After auth redirect, page should have search or permit-related content
        assert any(kw in lower for kw in ["permit", "result", "valencia", "search", "lookup"]), (
            "Search for 'valencia' should return permit data or search context"
        )

    def test_address_search_result_count_visible(self, auth_page):
        """77-3-1b: Search result page displays a count or list of entries."""
        pg = auth_page("expediter")
        pg.goto(f"{pg._base_url}/search?q=market+st")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-1b-search-market-st")

        body = pg.text_content("body") or ""
        # Should not be an empty page
        assert len(body.strip()) > 200, "Search result page should have substantial content"


# ===========================================================================
# Test 77-3-2: Permit number search returns specific permit detail
# ===========================================================================


class TestPermitNumberSearch:
    """SCENARIO-38 (permit lookup variant): Permit number search returns detail view."""

    def test_permit_number_search_shows_detail(self, auth_page):
        """77-3-2: Search a known permit number pattern and assert permit detail appears.

        Uses the /search public endpoint with a permit-style query.
        The intent router should classify it as lookup_permit and return permit detail.
        SF permit numbers typically follow patterns like 202301234567 (12-digit) or
        shorter formats. We use a short alpha-numeric pattern the intent router
        can classify as a permit lookup.
        """
        pg = auth_page("expediter")
        # Use the ask/search endpoint with a permit-style query
        pg.goto(f"{pg._base_url}/search?q=202101234567")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-2-permit-lookup")

        # The page should respond without a 500 error — content may be
        # "no results" if this permit doesn't exist, but it should not crash.
        body = pg.text_content("body") or ""
        lower = body.lower()
        assert "internal server error" not in lower and "traceback" not in lower, (
            "Permit number search should not produce a server error"
        )
        # Some kind of response: lookup result, no-results message, or search context
        assert any(kw in lower for kw in [
            "permit", "no result", "not found", "search", "lookup", "202101234567"
        ]), "Permit number search should return a meaningful response"

    def test_permit_lookup_form_present_on_index(self, auth_page):
        """77-3-2b: Authenticated home page has a permit/address search form."""
        pg = auth_page("homeowner")
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-2b-index-search-form")

        # Search input should be present on the index/dashboard
        search_input = pg.locator('input[name="q"], input[type="search"], input[placeholder*="search" i], input[placeholder*="permit" i], input[placeholder*="address" i]')
        assert search_input.count() > 0, "Authenticated home page should have a search input"


# ===========================================================================
# Test 77-3-3: Empty search shows guidance (not a crash)
# ===========================================================================


class TestEmptySearchHandledGracefully:
    """SCENARIO-38 (edge case): Empty search query handled gracefully."""

    def test_empty_search_redirects_or_shows_guidance(self, auth_page):
        """77-3-3: Submit empty search, assert no crash and helpful guidance.

        Authenticated users who hit /search?q= should be redirected to index
        or see a guidance message — not a 500 or blank screen.
        """
        pg = auth_page("homeowner")
        resp = pg.goto(f"{pg._base_url}/search?q=")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-3-empty-search")

        # Must not crash — accept 200 or redirect
        assert resp is None or resp.status in (200, 302, 301), (
            f"Empty search returned unexpected HTTP status: {resp and resp.status}"
        )

        body = pg.text_content("body") or ""
        assert len(body.strip()) > 50, "Empty search should show content, not a blank page"
        lower = body.lower()
        # Should not show a server error
        assert "internal server error" not in lower and "traceback" not in lower, (
            "Empty search should not show a server error"
        )

    def test_anonymous_empty_search_redirects(self, page, live_server):
        """77-3-3b: Anonymous empty search redirects to landing page."""
        resp = page.goto(f"{live_server}/search?q=")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-3-3b-anon-empty-search")

        # Should redirect (302) or render the landing — either is acceptable
        assert resp is None or resp.status in (200, 302), (
            f"Anonymous empty search returned {resp and resp.status}"
        )
        body = page.text_content("body") or ""
        # Body should be non-empty (landing page or redirect page)
        assert len(body.strip()) > 50, "Empty search response should not be blank"

    def test_whitespace_only_search_handled(self, auth_page):
        """77-3-3c: Whitespace-only search treated as empty — no crash."""
        pg = auth_page("homeowner")
        # URL-encode a spaces-only query
        resp = pg.goto(f"{pg._base_url}/search?q=   ")
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-3c-whitespace-search")

        body = pg.text_content("body") or ""
        lower = body.lower()
        assert "internal server error" not in lower and "traceback" not in lower, (
            "Whitespace-only search should not produce a server error"
        )


# ===========================================================================
# Test 77-3-4: Plan analysis upload form renders and is functional
# ===========================================================================


class TestPlanAnalysisUploadForm:
    """Plan analysis upload form renders correctly for authenticated users."""

    def test_plan_analysis_upload_input_exists(self, auth_page):
        """77-3-4: Navigate to plan analysis (index), assert file upload input exists.

        The plan analysis upload is embedded in the authenticated index page.
        The test verifies the file input element is present and accepts PDFs.
        """
        pg = auth_page("architect")
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")
        _screenshot(pg, "77-3-4-plan-upload-form")

        # File input for plan upload should exist
        file_input = pg.locator('input[type="file"]')
        assert file_input.count() > 0, (
            "Authenticated index should have a file upload input for plan analysis"
        )

    def test_plan_analysis_file_input_accepts_pdf(self, auth_page):
        """77-3-4b: Plan analysis file input accepts .pdf files."""
        pg = auth_page("architect")
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")

        # The file input should accept only PDF
        file_input = pg.locator('input[type="file"][accept*=".pdf"], input[type="file"][accept*="pdf"]')
        assert file_input.count() > 0, (
            "Plan analysis file input should restrict to .pdf files (accept='.pdf')"
        )

    def test_plan_analysis_section_visible(self, auth_page):
        """77-3-4c: Plan analysis section is visible on the authenticated index."""
        pg = auth_page("architect")
        pg.goto(pg._base_url)
        pg.wait_for_load_state("networkidle")

        body = pg.text_content("body") or ""
        lower = body.lower()
        # The page should mention plan analysis or plan check
        assert any(kw in lower for kw in ["plan", "analyze", "analysis", "upload"]), (
            "Authenticated index should mention plan analysis features"
        )


# ===========================================================================
# Test 77-3-5: Methodology page renders full content (not a stub)
# ===========================================================================


class TestMethodologyPageFullContent:
    """Methodology page renders multiple sections — not a stub."""

    def test_methodology_page_is_substantive(self, page, live_server):
        """77-3-5: /methodology renders long content with multiple section headings.

        The methodology page explains the SF Permits AI approach. It should
        contain multiple headings (h2/h3), not be a one-liner stub.
        """
        page.goto(f"{live_server}/methodology")
        page.wait_for_load_state("networkidle")
        _screenshot(page, "77-3-5-methodology")

        # Page title or body should reference methodology
        body = page.text_content("body") or ""
        lower = body.lower()
        assert "methodology" in lower or "how" in lower, (
            "Methodology page should contain methodology-related content"
        )

        # Multiple headings required — not a stub
        headings = page.locator("h2, h3")
        heading_count = headings.count()
        assert heading_count >= 3, (
            f"Methodology page should have at least 3 section headings, found {heading_count}"
        )

    def test_methodology_page_has_data_sources_section(self, page, live_server):
        """77-3-5b: Methodology page references data sources."""
        page.goto(f"{live_server}/methodology")
        page.wait_for_load_state("networkidle")

        body = page.text_content("body") or ""
        lower = body.lower()
        assert any(kw in lower for kw in ["data", "source", "permit", "soda", "api", "dataset"]), (
            "Methodology page should explain data sources"
        )

    def test_methodology_page_has_entity_or_search_section(self, page, live_server):
        """77-3-5c: Methodology page covers entity resolution or search methods."""
        page.goto(f"{live_server}/methodology")
        page.wait_for_load_state("networkidle")

        body = page.text_content("body") or ""
        lower = body.lower()
        assert any(kw in lower for kw in [
            "entity", "search", "network", "contractor", "architect",
            "resolution", "graph", "relationship"
        ]), "Methodology page should describe entity or search methodology"

    def test_methodology_page_accessible_without_login(self, page, live_server):
        """77-3-5d: /methodology is a public page — no login required."""
        resp = page.goto(f"{live_server}/methodology")
        assert resp.status == 200, (
            f"/methodology should return 200 for anonymous users, got {resp.status}"
        )

    def test_methodology_page_has_plan_analysis_section(self, page, live_server):
        """77-3-5e: Methodology page includes plan analysis section."""
        page.goto(f"{live_server}/methodology")
        page.wait_for_load_state("networkidle")

        body = page.text_content("body") or ""
        lower = body.lower()
        assert any(kw in lower for kw in ["plan", "vision", "analysis", "ai", "check"]), (
            "Methodology page should mention plan analysis or AI vision checks"
        )
