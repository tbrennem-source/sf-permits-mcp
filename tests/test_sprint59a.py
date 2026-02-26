"""Sprint 59 Agent A: Account Page Tab Split tests.

Tests cover:
- Tab shell loads for authenticated user
- Settings fragment loads with correct sections
- Admin fragment returns 403 for non-admin users
- Admin fragment loads for admin users with correct sections
- Hash persistence (settings/admin)
- Non-admin users see settings content directly (no tab bar)
- Admin users see tab bar HTML (not inline settings)
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_sprint59a.duckdb")
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
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


def _login_user(client, email="user@example.com"):
    """Helper: create a regular (non-admin) user and log in."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _login_admin(client, monkeypatch, email="admin@example.com"):
    """Helper: create an admin user and log in."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# 1. Account page loads for authenticated user
# ---------------------------------------------------------------------------

def test_account_page_loads_for_logged_in_user(client):
    """Account page returns 200 for a logged-in user."""
    _login_user(client)
    rv = client.get("/account")
    assert rv.status_code == 200


def test_account_page_redirects_for_anonymous(client):
    """Account page redirects to login for unauthenticated users."""
    rv = client.get("/account", follow_redirects=False)
    assert rv.status_code in (302, 303)


# ---------------------------------------------------------------------------
# 2. Non-admin users see settings inline (no tab bar)
# ---------------------------------------------------------------------------

def test_non_admin_sees_settings_inline(client):
    """Non-admin account page includes settings sections directly without HTMX tab bar."""
    _login_user(client)
    rv = client.get("/account")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Should have profile card inline
    assert "Profile" in html
    # Should have watch list section
    assert "Watch List" in html
    # Should NOT have admin tab bar (no data-tab="admin")
    assert 'data-tab="admin"' not in html


def test_non_admin_has_no_tab_bar(client):
    """Non-admin users should not see a tab-bar element."""
    _login_user(client)
    rv = client.get("/account")
    html = rv.data.decode()
    # The tab-bar is only rendered for admins
    assert 'class="tab-bar"' not in html or 'data-tab="settings"' not in html


def test_non_admin_no_settings_htmx_fetch(client):
    """Non-admin account page should not contain hx-get pointing to account fragment/settings."""
    _login_user(client)
    rv = client.get("/account")
    html = rv.data.decode()
    # For non-admins, content is inline — not fetched via hx-get
    assert 'hx-get="/account/fragment/settings"' not in html


# ---------------------------------------------------------------------------
# 3. Admin users see tab bar
# ---------------------------------------------------------------------------

def test_admin_sees_tab_bar(client, monkeypatch):
    """Admin account page shows HTMX tab bar with Settings and Admin tabs."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert 'data-tab="settings"' in html
    assert 'data-tab="admin"' in html
    assert 'hx-get="/account/fragment/settings"' in html
    assert 'hx-get="/account/fragment/admin"' in html


def test_admin_tab_shell_has_tab_content_divs(client, monkeypatch):
    """Admin account page has tab panel divs for settings and admin content."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account")
    html = rv.data.decode()
    # New design uses separate panel divs per tab
    assert 'id="tab-content-settings"' in html
    assert 'id="tab-content-admin"' in html


# ---------------------------------------------------------------------------
# 4. Settings fragment
# ---------------------------------------------------------------------------

def test_settings_fragment_loads(client):
    """Settings fragment returns 200 for logged-in user."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    assert rv.status_code == 200


def test_settings_fragment_has_profile_section(client):
    """Settings fragment contains Profile section."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    html = rv.data.decode()
    assert "Profile" in html


def test_settings_fragment_has_watch_list(client):
    """Settings fragment contains Watch List section."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    html = rv.data.decode()
    assert "Watch List" in html


def test_settings_fragment_has_voice_style(client):
    """Settings fragment contains Voice & Style section."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    html = rv.data.decode()
    assert "Voice" in html
    assert "Style" in html


def test_settings_fragment_has_points_section(client):
    """Settings fragment contains Points section."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    html = rv.data.decode()
    assert "Points" in html


def test_settings_fragment_has_plan_analyses(client):
    """Settings fragment contains Plan Analyses section."""
    _login_user(client)
    rv = client.get("/account/fragment/settings")
    html = rv.data.decode()
    assert "Plan Analyses" in html


def test_settings_fragment_redirects_for_anonymous(client):
    """Settings fragment redirects unauthenticated users."""
    rv = client.get("/account/fragment/settings", follow_redirects=False)
    assert rv.status_code in (302, 303)


# ---------------------------------------------------------------------------
# 5. Admin fragment access control
# ---------------------------------------------------------------------------

def test_admin_fragment_returns_403_for_non_admin(client):
    """Admin fragment returns 403 for non-admin users."""
    _login_user(client)
    rv = client.get("/account/fragment/admin")
    assert rv.status_code == 403


def test_admin_fragment_redirects_for_anonymous(client):
    """Admin fragment redirects unauthenticated users."""
    rv = client.get("/account/fragment/admin", follow_redirects=False)
    assert rv.status_code in (302, 303)


# ---------------------------------------------------------------------------
# 6. Admin fragment content
# ---------------------------------------------------------------------------

def test_admin_fragment_loads_for_admin(client, monkeypatch):
    """Admin fragment returns 200 for admin user."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    assert rv.status_code == 200


def test_admin_fragment_has_invite_codes_section(client, monkeypatch):
    """Admin fragment contains Invite Codes section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Invite Codes" in html


def test_admin_fragment_has_activity_section(client, monkeypatch):
    """Admin fragment contains Activity section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Activity" in html


def test_admin_fragment_has_feedback_section(client, monkeypatch):
    """Admin fragment contains Feedback Queue section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Feedback Queue" in html


def test_admin_fragment_has_impersonate_section(client, monkeypatch):
    """Admin fragment contains Impersonate User section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Impersonate" in html


def test_admin_fragment_has_send_invite_section(client, monkeypatch):
    """Admin fragment contains Send Invite section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Send Invite" in html


def test_admin_fragment_has_knowledge_sources_section(client, monkeypatch):
    """Admin fragment contains Knowledge Sources section."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account/fragment/admin")
    html = rv.data.decode()
    assert "Knowledge Sources" in html


# ---------------------------------------------------------------------------
# 7. Hash persistence (JS is in shell, but we can verify data attributes)
# ---------------------------------------------------------------------------

def test_admin_tab_bar_has_hash_persistence_js(client, monkeypatch):
    """Admin account page includes hash-based tab persistence logic."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account")
    html = rv.data.decode()
    # JS reads location.hash and sets tab state
    assert "location.hash" in html


def test_admin_tab_default_is_settings(client, monkeypatch):
    """Admin tab bar defaults to 'settings' tab."""
    _login_admin(client, monkeypatch)
    rv = client.get("/account")
    html = rv.data.decode()
    # The JS initialization uses 'settings' as default
    assert "'settings'" in html or '"settings"' in html
