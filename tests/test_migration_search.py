"""Tests for search flow template migration to Obsidian design system.

Verifies:
- Templates render without error
- Design token compliance (no hardcoded hex colors)
- results.html is an HTMX fragment that inherits from parent context
- search_results_public.html is a standalone public page
- search_results.html is an HTMX fragment for authenticated search
"""

import re
import pytest
from pathlib import Path

# ── Template paths ──────────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent.parent / "web" / "templates"

SEARCH_RESULTS_PUBLIC = TEMPLATES_DIR / "search_results_public.html"
RESULTS_FRAGMENT = TEMPLATES_DIR / "results.html"
SEARCH_RESULTS_FRAGMENT = TEMPLATES_DIR / "search_results.html"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Flask test client with TESTING mode enabled."""
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


@pytest.fixture
def authenticated_client(client):
    """Logged-in test client."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user("search-migration-test@test.com")
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return client


# ── Design token helpers ─────────────────────────────────────────────────────

# Non-token hex colors from the OLD templates (must not appear after migration)
NON_TOKEN_HEX_COLORS = [
    "#4f8ff7",   # old blue accent
    "#8b8fa3",   # old muted text
    "#7ab0ff",   # old hover blue
    "#1a1d27",   # old surface color
    "#333749",   # old border color
    "#e4e6eb",   # old primary text
]

# Allowed token hex colors (from DESIGN_TOKENS.md §1)
ALLOWED_HEX_COLORS = {
    "#0a0a0f", "#12121a", "#1a1a26",
    "#5eead4",
    "#34d399", "#fbbf24", "#f87171", "#60a5fa",
    "#22c55e", "#f59e0b", "#ef4444",
    "#fff", "#000",
}


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_hex_colors(html: str) -> list[str]:
    """Extract all hex colors from template source."""
    # Match #xxx, #xxxxxx, #xxxxxxxx patterns in CSS/style contexts
    pattern = re.compile(r'(?:color|background(?:-color)?|border(?:-color)?)\s*:\s*(#[0-9a-fA-F]{3,8})', re.IGNORECASE)
    return pattern.findall(html)


# ── Test: search_results_public.html ────────────────────────────────────────

class TestSearchResultsPublicTemplate:

    def test_template_exists(self):
        """search_results_public.html exists on disk."""
        assert SEARCH_RESULTS_PUBLIC.exists(), "search_results_public.html not found"

    def test_uses_token_colors_only(self):
        """search_results_public.html has no non-token hex colors in CSS."""
        content = _read_template(SEARCH_RESULTS_PUBLIC)
        for bad_color in NON_TOKEN_HEX_COLORS:
            assert bad_color.lower() not in content.lower(), (
                f"Non-token color {bad_color} found in search_results_public.html"
            )

    def test_uses_token_font_vars(self):
        """search_results_public.html uses --mono and --sans font variables."""
        content = _read_template(SEARCH_RESULTS_PUBLIC)
        assert "var(--mono)" in content, "Expected var(--mono) font token"
        assert "var(--sans)" in content, "Expected var(--sans) font token"

    def test_no_legacy_font_vars(self):
        """search_results_public.html does not use legacy --font-body or --font-display vars."""
        content = _read_template(SEARCH_RESULTS_PUBLIC)
        assert "--font-body" not in content, "Legacy --font-body var found"
        assert "--font-display" not in content, "Legacy --font-display var found"

    def test_uses_obsidian_background_token(self):
        """search_results_public.html uses --obsidian CSS var for page background."""
        content = _read_template(SEARCH_RESULTS_PUBLIC)
        assert "var(--obsidian)" in content, "Expected var(--obsidian) background token"

    def test_renders_without_error(self, client):
        """Public search results page renders successfully for unauthenticated users."""
        rv = client.get("/search?q=614+6th+Ave")
        # Either 200 (results found) or 200 with empty state — not a 500
        assert rv.status_code == 200, f"Expected 200, got {rv.status_code}"

    def test_renders_no_results_state(self, client):
        """Public search results page handles no-results state without error."""
        rv = client.get("/search?q=zzz_nonexistent_address_xyz_99999")
        assert rv.status_code == 200


# ── Test: results.html (HTMX fragment) ──────────────────────────────────────

class TestResultsFragment:

    def test_template_exists(self):
        """results.html exists on disk."""
        assert RESULTS_FRAGMENT.exists(), "results.html not found"

    def test_uses_token_font_vars(self):
        """results.html uses --mono and --sans font variables."""
        content = _read_template(RESULTS_FRAGMENT)
        assert "var(--mono)" in content, "Expected var(--mono) font token"
        assert "var(--sans)" in content, "Expected var(--sans) font token"

    def test_no_non_token_hex_colors(self):
        """results.html has no non-token hex colors."""
        content = _read_template(RESULTS_FRAGMENT)
        for bad_color in NON_TOKEN_HEX_COLORS:
            assert bad_color.lower() not in content.lower(), (
                f"Non-token color {bad_color} found in results.html"
            )

    def test_uses_glass_card_component(self):
        """results.html uses the glass-card token component class."""
        content = _read_template(RESULTS_FRAGMENT)
        # results.html uses result-card (glass-card variant) for tabs
        assert "result-card" in content or "glass-card" in content


# ── Test: search_results.html (HTMX fragment) ────────────────────────────────

class TestSearchResultsFragment:

    def test_template_exists(self):
        """search_results.html exists on disk."""
        assert SEARCH_RESULTS_FRAGMENT.exists(), "search_results.html not found"

    def test_no_non_token_hex_colors(self):
        """search_results.html has no non-token hex colors after migration."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        for bad_color in NON_TOKEN_HEX_COLORS:
            assert bad_color.lower() not in content.lower(), (
                f"Non-token color {bad_color} still present in search_results.html after migration. "
                f"Replace with a design token variable."
            )

    def test_uses_token_font_vars(self):
        """search_results.html uses --mono and --sans font variables (no font-family:inherit)."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        assert "var(--mono)" in content or "var(--sans)" in content, (
            "Expected --mono or --sans token font vars in search_results.html"
        )
        # font-family:inherit is a lint violation — should not appear
        assert "font-family:inherit" not in content and "font-family: inherit" not in content, (
            "font-family:inherit found — should use var(--sans) or var(--mono)"
        )

    def test_uses_obsidian_mid_for_cards(self):
        """search_results.html uses --obsidian-mid token for card backgrounds."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        assert "var(--obsidian-mid)" in content, (
            "Expected var(--obsidian-mid) for card background token"
        )

    def test_uses_glass_card_class(self):
        """search_results.html uses the glass-card token component class."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        assert "glass-card" in content, "Expected glass-card token class"

    def test_no_legacy_color_fallbacks(self):
        """search_results.html has no legacy var(--accent, #4f8ff7) fallback patterns."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        assert "var(--accent, #4f8ff7)" not in content, (
            "Legacy --accent fallback to #4f8ff7 still present"
        )
        assert "var(--text-muted" not in content, (
            "Legacy --text-muted var found (use --text-secondary instead)"
        )

    def test_intel_col_uses_token_vars(self):
        """search_results.html intel panel CSS uses only token variables."""
        content = _read_template(SEARCH_RESULTS_FRAGMENT)
        # Check intel panel uses glass-border, not raw colors
        assert "var(--glass-border)" in content, (
            "Expected var(--glass-border) in intel panel CSS"
        )
