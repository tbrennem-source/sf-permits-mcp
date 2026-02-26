"""Tests for Sprint 62B: Client-side activity tracking + search no-results fix.

Coverage:
  - POST /api/activity/track with valid JSON returns 200 with ok=True
  - POST /api/activity/track with invalid JSON returns 400
  - POST /api/activity/track with missing events key returns 400
  - POST /api/activity/track with empty events list returns 200 (count: 0)
  - POST /api/activity/track caps at 50 events per batch
  - Events written to activity_log with client_ prefix
  - _is_no_results("") returns True
  - _is_no_results("No permits found") returns True
  - _is_no_results("Please provide a permit number") returns True
  - _is_no_results("Found 5 permits") returns False
  - _is_no_results(None) returns True
  - Script tag present in index.html template
  - Script tag present in search_results_public.html template
  - Static file activity-tracker.js exists and is valid JavaScript
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets, _is_no_results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for test isolation."""
    db_path = str(tmp_path / "test_62b.duckdb")
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
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Tests: POST /api/activity/track
# ---------------------------------------------------------------------------


def test_track_valid_events(client):
    """Valid batch of events returns 200 with ok=True."""
    payload = {
        "events": [
            {
                "event": "dead_click",
                "data": {"tag": "div", "path": "/"},
                "session_id": "ses_abc123",
                "ts": "2026-02-26T10:00:00.000Z",
            }
        ]
    }
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["count"] == 1


def test_track_invalid_json(client):
    """Non-JSON body returns 400."""
    resp = client.post(
        "/api/activity/track",
        data="not json at all",
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False


def test_track_missing_events_key(client):
    """JSON without 'events' key returns 400."""
    payload = {"something_else": []}
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["ok"] is False


def test_track_empty_events(client):
    """Empty events list returns 200 with count=0."""
    payload = {"events": []}
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["count"] == 0


def test_track_caps_at_50_events(client):
    """Batches with > 50 events are capped at 50."""
    events = [
        {
            "event": "dead_click",
            "data": {"path": "/"},
            "session_id": "ses_xyz",
            "ts": "2026-02-26T10:00:00.000Z",
        }
        for _ in range(75)
    ]
    payload = {"events": events}
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["count"] == 50


def test_track_events_written_with_client_prefix(client, tmp_path, monkeypatch):
    """Events are stored in activity_log with 'client_' prefix on action."""
    import src.db as db_mod

    payload = {
        "events": [
            {
                "event": "first_action",
                "data": {"elapsed_ms": 1200, "trigger": "form_submit", "path": "/search"},
                "session_id": "ses_test01",
                "ts": "2026-02-26T10:00:00.000Z",
            }
        ]
    }
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200

    # Verify log entry was written
    conn = db_mod.get_connection()
    try:
        rows = conn.execute(
            "SELECT action FROM activity_log WHERE action = 'client_first_action'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) >= 1
    assert rows[0][0] == "client_first_action"


def test_track_anonymous_allowed(client):
    """Tracking works without a logged-in user (anonymous)."""
    payload = {
        "events": [
            {
                "event": "dead_click",
                "data": {"tag": "p", "path": "/"},
                "session_id": "ses_anon",
                "ts": "2026-02-26T10:00:00.000Z",
            }
        ]
    }
    resp = client.post(
        "/api/activity/track",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ---------------------------------------------------------------------------
# Tests: _is_no_results helper
# ---------------------------------------------------------------------------


def test_is_no_results_empty_string():
    """Empty string is treated as no results."""
    assert _is_no_results("") is True


def test_is_no_results_none():
    """None is treated as no results."""
    assert _is_no_results(None) is True


def test_is_no_results_no_permits_found():
    """'No permits found' phrase is detected."""
    assert _is_no_results("No permits found for this address.") is True


def test_is_no_results_please_provide():
    """'Please provide a permit number' phrase is detected (Chief #279 fix)."""
    assert _is_no_results("Please provide a permit number to look up.") is True


def test_is_no_results_no_matching_permits():
    """'No matching permits' phrase is detected."""
    assert _is_no_results("No matching permits were found.") is True


def test_is_no_results_no_results():
    """'No results' phrase is detected."""
    assert _is_no_results("No results found for your search.") is True


def test_is_no_results_zero_permits():
    """'0 permits found' phrase is detected."""
    assert _is_no_results("0 permits found at this address.") is True


def test_is_no_results_case_insensitive():
    """Detection is case-insensitive."""
    assert _is_no_results("NO PERMITS FOUND") is True
    assert _is_no_results("PLEASE PROVIDE A PERMIT NUMBER") is True


def test_is_no_results_false_when_results_exist():
    """Returns False when the response contains real permit data."""
    assert _is_no_results("Found 5 permits at 123 Main St.") is False


def test_is_no_results_false_for_normal_response():
    """Returns False for a typical non-empty permit results response."""
    result = "## Permits at 123 Valencia St\n\n**Permit 202301012345** — issued 2023-01-01"
    assert _is_no_results(result) is False


# ---------------------------------------------------------------------------
# Tests: Static file and template checks
# ---------------------------------------------------------------------------


def test_activity_tracker_js_exists():
    """Static file activity-tracker.js exists in web/static/."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js_path = os.path.join(repo_root, "web", "static", "activity-tracker.js")
    assert os.path.isfile(js_path), f"Missing file: {js_path}"


def test_activity_tracker_js_is_valid_js():
    """activity-tracker.js contains expected JS structure markers."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js_path = os.path.join(repo_root, "web", "static", "activity-tracker.js")
    with open(js_path, "r") as f:
        content = f.read()
    # Must be an IIFE
    assert "(function()" in content
    # Must define the session key
    assert "sfp_session_id" in content
    # Must have the track endpoint
    assert "/api/activity/track" in content
    # Must use sendBeacon for reliability
    assert "sendBeacon" in content
    # Must use setInterval for periodic flushing
    assert "setInterval" in content


def test_index_html_has_tracker_script():
    """index.html includes the activity-tracker.js script tag."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmpl_path = os.path.join(repo_root, "web", "templates", "index.html")
    with open(tmpl_path, "r") as f:
        content = f.read()
    assert 'src="/static/activity-tracker.js"' in content, (
        "activity-tracker.js script tag missing from index.html"
    )


def test_search_results_public_html_has_tracker_script():
    """search_results_public.html includes the activity-tracker.js script tag."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmpl_path = os.path.join(
        repo_root, "web", "templates", "search_results_public.html"
    )
    with open(tmpl_path, "r") as f:
        content = f.read()
    assert 'src="/static/activity-tracker.js"' in content, (
        "activity-tracker.js script tag missing from search_results_public.html"
    )
