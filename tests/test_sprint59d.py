"""Tests for Sprint 59D: Protocol Update + Search NL Guidance.

Coverage:
  - BLACKBOX_PROTOCOL.md has Stage 2 Escalation Criteria section
  - BLACKBOX_PROTOCOL.md mentions mandatory and optional criteria
  - Search results no-results block shows guidance card with example links
  - Guidance card has address, permit number, block/lot examples
  - NL query shows "How to use sfpermits.ai" heading
  - Non-NL query shows "Try searching by" heading
  - Signup CTA present in guidance card
  - Public search route passes nl_query to template
  - NL intent (general_question) sets nl_query=True
  - Address intent sets nl_query=False
"""

import os
import sys

import pytest

# Ensure both 'app' (web/) and 'web.app' resolve to the same module.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

BLACKBOX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "BLACKBOX_PROTOCOL.md"
)

import web.app as app_module  # noqa: E402  — imported before app fixture

from app import app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_59d.duckdb")
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
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _patch_permit_lookup(monkeypatch, return_value="No permits found for this address."):
    """Patch permit_lookup in the module that the app routes actually reference."""
    import sys

    # The Flask app module may be registered as 'app' (via web/ path in sys.path)
    # Patch whichever module object the route function references.
    async def fake_permit_lookup(**kwargs):
        return return_value

    # Patch both possible module keys to be safe
    for mod_key in list(sys.modules.keys()):
        if mod_key in ("app", "web.app"):
            monkeypatch.setattr(sys.modules[mod_key], "permit_lookup", fake_permit_lookup)


# ---------------------------------------------------------------------------
# BLACKBOX_PROTOCOL.md tests
# ---------------------------------------------------------------------------


def test_blackbox_has_escalation_criteria_section():
    """BLACKBOX_PROTOCOL.md must have the Stage 2 Escalation Criteria section."""
    with open(BLACKBOX_PATH) as f:
        content = f.read()
    assert "Stage 2 Escalation Criteria" in content


def test_blackbox_mentions_mandatory():
    """BLACKBOX_PROTOCOL.md escalation section must mention 'mandatory'."""
    with open(BLACKBOX_PATH) as f:
        content = f.read()
    assert "mandatory" in content


def test_blackbox_mentions_optional():
    """BLACKBOX_PROTOCOL.md escalation section must mention 'optional'."""
    with open(BLACKBOX_PATH) as f:
        content = f.read()
    assert "optional" in content


def test_blackbox_escalation_has_visual_ui_criteria():
    """Escalation criteria must list visual/UI changes as mandatory trigger."""
    with open(BLACKBOX_PATH) as f:
        content = f.read()
    # The section should mention CSS or templates or visual changes
    assert any(
        term in content
        for term in ("CSS", "templates", "Visual/UI", "visual/UI", "layout")
    )


def test_blackbox_escalation_has_backend_skip_guidance():
    """Escalation criteria must state backend-only sprints can skip DeskRelay."""
    with open(BLACKBOX_PATH) as f:
        content = f.read()
    assert "backend" in content.lower()
    assert "DeskRelay SKIPPED" in content


# ---------------------------------------------------------------------------
# Search guidance card — HTML template tests
# ---------------------------------------------------------------------------


def test_no_results_shows_guidance_card(client, monkeypatch):
    """When no_results is True, the guidance card renders with example links."""
    _patch_permit_lookup(monkeypatch)
    # "fakequery12345" classifies as general_question → else branch → calls permit_lookup
    rv = client.get("/search?q=fakequery12345")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Guidance card should be present
    assert "614 6th Ave" in html or "Try searching by" in html or "How to use" in html


def test_guidance_card_has_address_example(client, monkeypatch):
    """Guidance card must include an address example link."""
    _patch_permit_lookup(monkeypatch)
    rv = client.get("/search?q=permit+information")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "614 6th Ave" in html


def test_guidance_card_has_permit_number_example(client, monkeypatch):
    """Guidance card must include a permit number example link."""
    _patch_permit_lookup(monkeypatch)
    rv = client.get("/search?q=permit+information")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "202401015555" in html


def test_guidance_card_has_block_lot_example(client, monkeypatch):
    """Guidance card must include a block/lot example link."""
    _patch_permit_lookup(monkeypatch)
    rv = client.get("/search?q=permit+information")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "3512/001" in html


def test_guidance_card_has_signup_cta(client, monkeypatch):
    """Guidance card must include a signup CTA link."""
    _patch_permit_lookup(monkeypatch)
    rv = client.get("/search?q=permit+information")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Sign up free" in html


# ---------------------------------------------------------------------------
# NL query heading tests
# ---------------------------------------------------------------------------


def test_nl_query_shows_how_to_use_heading(client, monkeypatch):
    """NL queries (general_question/analyze_project intent) show 'How to use sfpermits.ai'."""
    _patch_permit_lookup(monkeypatch)
    # "permit information" classifies as general_question
    rv = client.get("/search?q=permit+information")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "How to use sfpermits.ai" in html


def test_address_query_shows_try_searching_heading(client, monkeypatch):
    """Non-NL queries show 'Try searching by' heading."""
    _patch_permit_lookup(monkeypatch)
    # "fakequery12345" classifies as general_question, but a query with a permit
    # number pattern should classify as lookup_permit and still render no_results
    # Use a query we know returns search_address intent
    # Actually "fakequery12345" → general_question → nl_query=True → "How to use"
    # We need something classified as search_address but returns no results
    # "123 Xyzzy Blvd" → search_address → nl_query=False
    rv = client.get("/search?q=123+Xyzzy+Blvd")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Try searching by" in html


# ---------------------------------------------------------------------------
# nl_query flag in public_search route
# ---------------------------------------------------------------------------


def test_public_search_passes_nl_query_false_for_address(client, monkeypatch):
    """public_search passes nl_query=False for address-type queries."""
    _patch_permit_lookup(monkeypatch)
    # Street address should NOT trigger nl_query → shows "Try searching by"
    rv = client.get("/search?q=123+Xyzzy+Blvd")
    assert rv.status_code == 200
    html = rv.data.decode()
    # "Try searching by" heading confirms nl_query=False rendered
    assert "Try searching by" in html
    assert "How to use sfpermits.ai" not in html


def test_nl_intent_general_question_sets_nl_query_true():
    """classify_intent returns general_question for generic permit info queries."""
    from src.tools.intent_router import classify

    result = classify("permit information", [])
    assert result.intent == "general_question"


def test_address_intent_sets_nl_query_false():
    """classify_intent returns search_address for street address queries."""
    from src.tools.intent_router import classify

    result = classify("614 6th Ave", [])
    assert result.intent == "search_address"
    # Verify this is NOT an NL intent
    assert result.intent not in ("general_question", "analyze_project")
