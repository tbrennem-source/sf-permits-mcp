"""Tests for admin persona impersonation (QS10 T2-A).

Covers:
- Auth gate (403 for non-admins)
- Applying a known persona sets correct session state
- Unknown persona returns error response
- Reset clears impersonation state
- All persona dicts have required keys
- apply_persona + admin_reset clears session state
"""

import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for test isolation."""
    db_path = str(tmp_path / "test_admin_impersonation.duckdb")
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


def _login_admin(client, email="admin_impersonate@example.com"):
    """Create admin user and establish session via magic-link flow."""
    import web.auth as auth_mod
    orig_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig_admin
    return user


def _login_user(client, email="regular_impersonate@example.com"):
    """Create non-admin user and establish session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_impersonation_requires_admin(client):
    """POST /admin/impersonate as non-admin returns 403."""
    _login_user(client, "nonadmin_impersonate@example.com")
    rv = client.post(
        "/admin/impersonate",
        data={"persona_id": "beta_active", "csrf_token": "test"},
    )
    assert rv.status_code == 403


def test_impersonation_beta_active(client):
    """Admin can impersonate beta_active persona.

    Expects:
    - 200 response with persona label in body
    - session["persona_id"] == "beta_active"
    - session["persona_tier"] == "beta"
    - session["persona_watches"] has 3 items
    """
    _login_admin(client, "admin_beta_imp@example.com")

    with client.session_transaction() as sess:
        # Disable CSRF for testing
        pass

    rv = client.post(
        "/admin/impersonate",
        data={"persona_id": "beta_active", "csrf_token": "test"},
    )
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Beta Active" in html

    with client.session_transaction() as sess:
        assert sess.get("persona_id") == "beta_active"
        assert sess.get("persona_tier") == "beta"
        watches = sess.get("persona_watches", [])
        assert len(watches) == 3


def test_impersonation_unknown_persona(client):
    """POST /admin/impersonate with unknown persona_id returns error response."""
    _login_admin(client, "admin_unknown_persona@example.com")
    rv = client.post(
        "/admin/impersonate",
        data={"persona_id": "nonexistent", "csrf_token": "test"},
    )
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should contain error indication (signal-red or "error" or "unknown")
    assert any(term in html.lower() for term in ("error", "unknown", "signal-red"))


def test_reset_impersonation(client):
    """After applying a persona, GET /admin/reset-impersonation clears it."""
    _login_admin(client, "admin_reset_imp@example.com")

    # First apply a persona
    client.post(
        "/admin/impersonate",
        data={"persona_id": "beta_active", "csrf_token": "test"},
    )

    # Verify it was set
    with client.session_transaction() as sess:
        assert sess.get("persona_id") == "beta_active"

    # Now reset
    rv = client.get("/admin/reset-impersonation", follow_redirects=True)
    assert rv.status_code == 200

    # Session impersonating key should be cleared
    with client.session_transaction() as sess:
        assert not sess.get("impersonating")


def test_all_personas_have_required_keys(client):
    """Every persona in PERSONAS has the required keys."""
    from web.admin_personas import PERSONAS

    required_keys = {"id", "label", "tier", "watches", "search_history"}
    for persona in PERSONAS:
        missing = required_keys - set(persona.keys())
        assert not missing, (
            f"Persona '{persona.get('id', '?')}' missing keys: {missing}"
        )
        # watches must be a list
        assert isinstance(persona["watches"], list), (
            f"Persona '{persona['id']}' watches must be a list"
        )
        # search_history must be a list
        assert isinstance(persona["search_history"], list), (
            f"Persona '{persona['id']}' search_history must be a list"
        )


def test_admin_reset_persona_clears_state(client):
    """apply_persona with admin_reset clears all impersonation session keys."""
    from web.admin_personas import apply_persona, get_persona

    # Simulate a session dict (plain dict, not a Flask session)
    mock_session = {}

    # Apply beta_active persona
    beta = get_persona("beta_active")
    apply_persona(mock_session, beta)

    assert mock_session.get("impersonating") is True
    assert mock_session.get("persona_id") == "beta_active"
    assert mock_session.get("persona_tier") == "beta"
    assert len(mock_session.get("persona_watches", [])) == 3

    # Now reset
    reset = get_persona("admin_reset")
    apply_persona(mock_session, reset)

    # All impersonation keys should be gone
    assert not mock_session.get("impersonating")
    assert "persona_id" not in mock_session
    assert "persona_tier" not in mock_session
    assert "persona_watches" not in mock_session
    assert "anon_searches" not in mock_session
