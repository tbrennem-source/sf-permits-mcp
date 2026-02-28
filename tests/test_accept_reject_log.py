"""Tests for POST /admin/qa-decision — Accept/Reject/Note log (QS10 T2-B).

Covers:
- Auth gate (403 for non-admins)
- Accept verdict writes review-decisions.json
- Reject verdict appends to existing file
- Invalid verdict returns 400
- Missing file handled gracefully (no crash)
- Matching pending-reviews.json entry removed on decision
"""

import json
import os
import pytest

import web.routes_admin
from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for test isolation."""
    db_path = str(tmp_path / "test_accept_reject.duckdb")
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


def _login_admin(client, email="admin_arlog@example.com"):
    """Create admin user and establish session via magic-link flow."""
    import web.auth as auth_mod
    orig_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig_admin
    return user


def _login_user(client, email="regular_arlog@example.com"):
    """Create non-admin user and establish session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_qa_decision_requires_admin(client):
    """POST /admin/qa-decision as non-admin → 403."""
    _login_user(client)
    resp = client.post(
        "/admin/qa-decision",
        data={"tim_verdict": "accept", "page": "/search", "dimension": "cards",
              "pipeline_score": "2.4", "sprint": "qs10"},
    )
    assert resp.status_code == 403


def test_qa_decision_accept_writes_file(tmp_path, monkeypatch, client):
    """Accept verdict writes review-decisions.json with correct fields."""
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))

    _login_admin(client)
    resp = client.post(
        "/admin/qa-decision",
        data={
            "tim_verdict": "accept",
            "page": "/search",
            "persona": "beta_active",
            "viewport": "desktop",
            "dimension": "cards",
            "pipeline_score": "2.4",
            "sprint": "qs10",
            "note": "looks fine",
        },
    )
    assert resp.status_code == 200

    decisions_path = tmp_path / "review-decisions.json"
    assert decisions_path.exists(), "review-decisions.json should be created"
    decisions = json.loads(decisions_path.read_text())
    assert len(decisions) == 1
    entry = decisions[0]
    assert entry["tim_verdict"] == "accept"
    assert entry["page"] == "/search"
    assert "timestamp" in entry


def test_qa_decision_reject_appends(tmp_path, monkeypatch, client):
    """Reject verdict appends to existing review-decisions.json."""
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))

    # Pre-populate with 1 existing entry
    existing = [{"tim_verdict": "accept", "page": "/", "dimension": "layout",
                 "pipeline_score": 3.1, "sprint": "qs10", "timestamp": "2026-01-01T00:00:00Z"}]
    decisions_path = tmp_path / "review-decisions.json"
    decisions_path.write_text(json.dumps(existing))

    _login_admin(client)
    resp = client.post(
        "/admin/qa-decision",
        data={
            "tim_verdict": "reject",
            "page": "/search",
            "dimension": "centering",
            "pipeline_score": "1.8",
            "sprint": "qs10",
        },
    )
    assert resp.status_code == 200

    decisions = json.loads(decisions_path.read_text())
    assert len(decisions) == 2
    assert decisions[1]["tim_verdict"] == "reject"


def test_qa_decision_invalid_verdict(client, tmp_path, monkeypatch):
    """POST /admin/qa-decision with invalid verdict → 400."""
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))

    _login_admin(client)
    resp = client.post(
        "/admin/qa-decision",
        data={
            "tim_verdict": "maybe",
            "page": "/search",
            "dimension": "cards",
            "pipeline_score": "2.4",
            "sprint": "qs10",
        },
    )
    assert resp.status_code == 400


def test_qa_decision_missing_file_graceful(tmp_path, monkeypatch, client):
    """Missing review-decisions.json is handled gracefully — file created with 1 entry."""
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))

    # Ensure no pre-existing file
    decisions_path = tmp_path / "review-decisions.json"
    assert not decisions_path.exists()

    _login_admin(client)
    resp = client.post(
        "/admin/qa-decision",
        data={
            "tim_verdict": "note",
            "page": "/property/123",
            "dimension": "centering",
            "pipeline_score": "2.8",
            "sprint": "qs10",
            "note": "borderline but ok",
        },
    )
    assert resp.status_code == 200

    assert decisions_path.exists(), "review-decisions.json should be created"
    decisions = json.loads(decisions_path.read_text())
    assert len(decisions) == 1
    assert decisions[0]["tim_verdict"] == "note"


def test_pending_reviews_pruned_on_decision(tmp_path, monkeypatch, client):
    """Matching entry removed from pending-reviews.json after a decision."""
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))

    # Write pending-reviews.json with a matching entry + one non-matching
    pending = [
        {"page": "/search", "dimension": "cards", "sprint": "qs10", "pipeline_score": 2.4},
        {"page": "/about", "dimension": "layout", "sprint": "qs10", "pipeline_score": 3.0},
    ]
    pending_path = tmp_path / "pending-reviews.json"
    pending_path.write_text(json.dumps(pending))

    _login_admin(client)
    resp = client.post(
        "/admin/qa-decision",
        data={
            "tim_verdict": "accept",
            "page": "/search",
            "dimension": "cards",
            "pipeline_score": "2.4",
            "sprint": "qs10",
        },
    )
    assert resp.status_code == 200

    remaining = json.loads(pending_path.read_text())
    assert isinstance(remaining, list)
    # The /search · cards entry should be gone
    pages = [p["page"] for p in remaining]
    assert "/search" not in pages, "Matching pending-reviews entry should be removed"
    # Non-matching entry should remain
    assert "/about" in pages, "Non-matching pending-reviews entry should remain"
