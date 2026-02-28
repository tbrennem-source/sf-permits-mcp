"""Tests for Sprint 91 auth/supporting template migrations.

Verifies that auth_login.html, beta_request.html, and consultants.html:
1. Render without errors
2. Use no hardcoded non-token hex colors
3. Use only --mono/--sans font vars (no legacy --font-body/--font-display)
4. Contain no legacy non-token font stacks outside of CSS var definitions
"""

import re
import os
import pytest
from pathlib import Path


# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
AUTH_LOGIN = ROOT / "web/templates/auth_login.html"
BETA_REQUEST = ROOT / "web/templates/beta_request.html"
CONSULTANTS = ROOT / "web/templates/consultants.html"

# ── Token allowlist (mirrors scripts/design_lint.py) ─────────────────────────

ALLOWED_HEX = {
    "#0a0a0f", "#12121a", "#1a1a26",
    "#5eead4",
    "#34d399", "#fbbf24", "#f87171", "#60a5fa",
    "#22c55e", "#f59e0b", "#ef4444",
    "#fff", "#000",
}

LEGACY_FONT_VARS = {"--font-body", "--font-display", "--font-mono"}

LEGACY_FONT_FAMILIES = [
    re.compile(r"font-family\s*:\s*-apple-system"),
    re.compile(r"font-family\s*:\s*Roboto"),
    re.compile(r"font-family\s*:\s*Arial"),
    re.compile(r"font-family\s*:\s*Helvetica"),
    re.compile(r"font-family\s*:\s*inherit\b"),
]

NON_TOKEN_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_non_token_hex(content: str) -> list[str]:
    """Return list of hex colors not in the token palette."""
    found = []
    for match in NON_TOKEN_HEX_RE.finditer(content):
        hex_val = f"#{match.group(1).lower()}"
        # Skip SVG stroke/fill/stop-color
        ctx = content[max(0, match.start() - 30):match.end() + 10]
        if "stroke=" in ctx or "fill=" in ctx or "stop-color=" in ctx:
            continue
        # Skip var() references
        if "var(--" in ctx:
            continue
        # Skip data URIs
        if "data:image" in content[max(0, match.start() - 100):match.start()]:
            continue
        if len(hex_val) in (4, 7) and hex_val not in ALLOWED_HEX:
            found.append(hex_val)
    return found


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_migration_auth.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ── Render tests ──────────────────────────────────────────────────────────────

def test_auth_login_renders(client):
    """auth_login.html renders without server error."""
    rv = client.get("/auth/login")
    assert rv.status_code == 200, f"Expected 200, got {rv.status_code}"
    html = rv.data.decode()
    assert "sfpermits.ai" in html
    assert 'name="email"' in html


def test_beta_request_renders(client):
    """beta_request.html renders without server error."""
    rv = client.get("/beta-request")
    assert rv.status_code == 200, f"Expected 200, got {rv.status_code}"
    html = rv.data.decode()
    assert "sfpermits.ai" in html
    assert 'name="email"' in html or "beta" in html.lower()


def test_consultants_renders(client):
    """consultants.html renders without server error."""
    rv = client.get("/consultants")
    # 200 (public) or 302 (redirects to login) are both valid;
    # 500 indicates a template render error
    assert rv.status_code in (200, 302), (
        f"consultants page returned {rv.status_code} — likely a template render error"
    )


# ── Hex color tests ───────────────────────────────────────────────────────────

def test_auth_login_no_non_token_hex():
    """auth_login.html must not contain non-token hex colors."""
    content = _read(AUTH_LOGIN)
    bad = find_non_token_hex(content)
    assert not bad, f"auth_login.html contains non-token hex colors: {bad}"


def test_beta_request_no_non_token_hex():
    """beta_request.html must not contain non-token hex colors."""
    content = _read(BETA_REQUEST)
    bad = find_non_token_hex(content)
    assert not bad, f"beta_request.html contains non-token hex colors: {bad}"


def test_consultants_no_non_token_hex():
    """consultants.html must not contain non-token hex colors."""
    content = _read(CONSULTANTS)
    bad = find_non_token_hex(content)
    assert not bad, f"consultants.html contains non-token hex colors: {bad}"


# ── Font var tests ─────────────────────────────────────────────────────────────

def test_auth_login_no_legacy_font_vars():
    """auth_login.html must not reference legacy --font-body or --font-display vars."""
    content = _read(AUTH_LOGIN)
    for var in LEGACY_FONT_VARS:
        assert var not in content, (
            f"auth_login.html uses legacy font var '{var}' — use --mono or --sans"
        )


def test_beta_request_no_legacy_font_vars():
    """beta_request.html must not reference legacy --font-body or --font-display vars."""
    content = _read(BETA_REQUEST)
    for var in LEGACY_FONT_VARS:
        assert var not in content, (
            f"beta_request.html uses legacy font var '{var}' — use --mono or --sans"
        )


def test_consultants_no_legacy_font_vars():
    """consultants.html must not reference legacy --font-body or --font-display vars."""
    content = _read(CONSULTANTS)
    for var in LEGACY_FONT_VARS:
        assert var not in content, (
            f"consultants.html uses legacy font var '{var}' — use --mono or --sans"
        )


def test_consultants_uses_token_font_vars():
    """consultants.html must use --mono and --sans (not raw font stacks)."""
    content = _read(CONSULTANTS)
    # Must have token vars
    assert "var(--mono)" in content, "consultants.html missing var(--mono)"
    assert "var(--sans)" in content, "consultants.html missing var(--sans)"
    # Must not have bare legacy font stacks in CSS properties
    for pattern in LEGACY_FONT_FAMILIES:
        assert not pattern.search(content), (
            f"consultants.html contains legacy font stack matching /{pattern.pattern}/"
        )


def test_consultants_head_obsidian_include():
    """consultants.html must include fragments/head_obsidian.html."""
    content = _read(CONSULTANTS)
    assert 'head_obsidian.html' in content, (
        "consultants.html missing head_obsidian.html include — required for shared CSS and CSRF meta"
    )


def test_consultants_csrf_token_present():
    """consultants.html form must have csrf_token hidden input."""
    content = _read(CONSULTANTS)
    assert 'csrf_token' in content, (
        "consultants.html is missing csrf_token — POST form is CSRF-vulnerable"
    )


def test_consultants_uses_nav_fragment():
    """consultants.html must use fragments/nav.html for navigation."""
    content = _read(CONSULTANTS)
    assert 'fragments/nav.html' in content, (
        "consultants.html is missing fragments/nav.html include — uses custom nav instead of token nav"
    )


def test_consultants_uses_glass_card():
    """consultants.html must use glass-card class for the search form container."""
    content = _read(CONSULTANTS)
    assert 'class="glass-card"' in content or "glass-card" in content, (
        "consultants.html must use glass-card for the search form card"
    )


def test_consultants_uses_token_form_classes():
    """consultants.html must use form-label, form-input, form-select token classes."""
    content = _read(CONSULTANTS)
    assert "form-label" in content, "consultants.html missing form-label token class"
    assert "form-input" in content, "consultants.html missing form-input token class"
    assert "form-select" in content, "consultants.html missing form-select token class"


def test_consultants_uses_action_btn():
    """consultants.html must use action-btn instead of custom .btn."""
    content = _read(CONSULTANTS)
    assert "action-btn" in content, (
        "consultants.html must use action-btn token class (not custom .btn)"
    )
    # Custom non-token .btn class should not appear as a CSS definition
    assert ".btn {" not in content and ".btn{" not in content, (
        "consultants.html still defines custom .btn — should use action-btn"
    )
