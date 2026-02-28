"""Tests for /admin/health system health panel (Sprint 82-B).

Covers:
- Auth gate (403 for non-admins, 200 for admins)
- Pool stats section rendered
- Cache count section rendered
"""

import pytest

from web.app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for test isolation."""
    db_path = str(tmp_path / "test_admin_health.duckdb")
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


def _login_admin(client, email="admin_health@example.com"):
    """Create admin user and establish session via magic-link flow."""
    import web.auth as auth_mod
    orig_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = email
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    auth_mod.ADMIN_EMAIL = orig_admin
    return user


def _login_user(client, email="regular@example.com"):
    """Create non-admin user and establish session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# test_admin_health_requires_auth
# ---------------------------------------------------------------------------

def test_admin_health_requires_auth(client):
    """Unauthenticated requests are rejected."""
    rv = client.get("/admin/health")
    # Expect redirect to login or 403
    assert rv.status_code in (302, 403), (
        f"Expected 302 or 403 for unauthenticated, got {rv.status_code}"
    )


def test_admin_health_non_admin_forbidden(client):
    """Non-admin users receive 403."""
    _login_user(client, "regular_health_test@example.com")
    rv = client.get("/admin/health")
    assert rv.status_code == 403


def test_admin_health_admin_ok(client):
    """Admin users receive 200 with health fragment."""
    _login_admin(client, "admin_syshealth@example.com")
    rv = client.get("/admin/health")
    assert rv.status_code == 200


# ---------------------------------------------------------------------------
# test_admin_health_shows_pool_stats
# ---------------------------------------------------------------------------

def test_admin_health_shows_pool_stats(client):
    """Health fragment renders pool card with connection stats."""
    _login_admin(client, "admin_pool_test@example.com")
    rv = client.get("/admin/health")
    assert rv.status_code == 200
    html = rv.data.decode()
    # Pool card title
    assert "DB Connection Pool" in html
    # Progress bar element
    assert "progress-track" in html


# ---------------------------------------------------------------------------
# test_admin_health_shows_cache_count
# ---------------------------------------------------------------------------

def test_admin_health_shows_cache_count(client):
    """Health fragment renders cache card with row count."""
    _login_admin(client, "admin_cache_test@example.com")
    rv = client.get("/admin/health")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Page Cache" in html
    assert "cached entries" in html


# ---------------------------------------------------------------------------
# test_admin_health_shows_circuit_breaker
# ---------------------------------------------------------------------------

def test_admin_health_shows_circuit_breaker(client):
    """Health fragment renders circuit breaker card."""
    _login_admin(client, "admin_cb_test@example.com")
    rv = client.get("/admin/health")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "SODA Circuit Breaker" in html
    # Should show one of the three valid states
    assert any(state in html for state in ("CLOSED", "OPEN", "HALF-OPEN", "unknown"))


# ---------------------------------------------------------------------------
# test_admin_health_tab_in_ops
# ---------------------------------------------------------------------------

def test_admin_health_tab_in_ops(client):
    """System Health tab appears in admin ops hub."""
    _login_admin(client, "admin_ops_tab@example.com")
    rv = client.get("/admin/ops")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "System Health" in html
    assert "syshealth" in html
