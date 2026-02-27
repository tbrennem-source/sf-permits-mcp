"""Tests for /brief route cache integration and /cron/compute-caches endpoint.

Written against the spec (Agent 1B builds brief cache, Agent 1C builds cron endpoint).
These tests will FAIL until Terminal 1's code is merged — that's expected.

Expected new behavior:
  - GET /brief: served from page cache on second request (compute_fn called once)
  - POST /brief/refresh: invalidates cache, forces recompute on next GET
  - POST /brief/refresh twice quickly: second returns 429 (rate limited)
  - POST /cron/compute-caches: pre-populates cache for all users, returns computed count
"""

from __future__ import annotations

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
    """Force DuckDB backend with isolated temp database."""
    db_path = str(tmp_path / "test_brief_cache.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TESTING", "1")

    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)

    # Clear page cache between tests
    try:
        from web.helpers import _page_cache
        _page_cache.clear()
    except (ImportError, AttributeError):
        pass

    db_mod.init_user_schema()

    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
        # Create minimal tables needed by get_morning_brief
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timeline_stats (
                permit_number TEXT,
                permit_type_definition TEXT,
                review_path TEXT,
                neighborhood TEXT,
                estimated_cost DOUBLE,
                revised_cost DOUBLE,
                cost_bracket TEXT,
                filed DATE,
                issued DATE,
                completed DATE,
                days_to_issuance INTEGER,
                days_to_completion INTEGER,
                supervisor_district TEXT
            )
        """)
    finally:
        conn.close()

    yield

    # Clear page cache after test
    try:
        from web.helpers import _page_cache
        _page_cache.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_user(client, email="briefcache@example.com"):
    """Helper: create user and authenticate via magic-link."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# GET /brief — cache integration
# ---------------------------------------------------------------------------

class TestBriefCacheIntegration:
    """GET /brief uses page cache to serve repeat requests without recomputing."""

    def test_brief_serves_200_when_logged_in(self, client):
        """Sanity check: /brief is accessible after login."""
        _login_user(client)
        resp = client.get("/brief")
        assert resp.status_code == 200

    def test_brief_redirects_unauthenticated(self, client):
        """GET /brief without login should redirect to login."""
        resp = client.get("/brief", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_brief_serves_from_cache(self, client, monkeypatch):
        """Second request to /brief should use cached data (compute_fn called once)."""
        _login_user(client)
        compute_call_count = {"n": 0}
        original_get_morning_brief = None

        try:
            import web.brief as brief_mod
            original_get_morning_brief = brief_mod.get_morning_brief

            def patched_brief(user_id, lookback_days, **kwargs):
                compute_call_count["n"] += 1
                return original_get_morning_brief(user_id, lookback_days, **kwargs)

            monkeypatch.setattr(brief_mod, "get_morning_brief", patched_brief)
        except (ImportError, AttributeError):
            pytest.skip("web.brief.get_morning_brief not available")

        # First request — should compute
        resp1 = client.get("/brief")
        assert resp1.status_code == 200

        # Second request — should use cache
        resp2 = client.get("/brief")
        assert resp2.status_code == 200

        assert compute_call_count["n"] == 1, (
            "get_morning_brief should be called once; second request should use cache"
        )

    def test_brief_cache_keyed_per_user(self, client, monkeypatch):
        """Different users get independent cache entries."""
        compute_calls = []

        try:
            import web.brief as brief_mod
            original = brief_mod.get_morning_brief

            def patched(user_id, lookback_days, **kwargs):
                compute_calls.append(user_id)
                return original(user_id, lookback_days, **kwargs)

            monkeypatch.setattr(brief_mod, "get_morning_brief", patched)
        except (ImportError, AttributeError):
            pytest.skip("web.brief.get_morning_brief not available")

        # Log in as user A
        user_a = _login_user(client, "user_a@example.com")
        client.get("/brief")

        # Log in as user B in same session (simulate different session)
        with app.test_client() as client_b:
            user_b = _login_user(client_b, "user_b@example.com")
            client_b.get("/brief")

        # Both users should have triggered compute
        unique_users = set(compute_calls)
        assert len(unique_users) >= 2, "Each user should get their own cache entry"


# ---------------------------------------------------------------------------
# POST /brief/refresh — cache invalidation
# ---------------------------------------------------------------------------

class TestBriefRefresh:
    """POST /brief/refresh invalidates cache and is rate-limited."""

    def test_brief_refresh_invalidates_cache(self, client, monkeypatch):
        """After POST /brief/refresh, next GET /brief should recompute."""
        _login_user(client)
        compute_call_count = {"n": 0}

        try:
            import web.brief as brief_mod
            original = brief_mod.get_morning_brief

            def patched(user_id, lookback_days, **kwargs):
                compute_call_count["n"] += 1
                return original(user_id, lookback_days, **kwargs)

            monkeypatch.setattr(brief_mod, "get_morning_brief", patched)
        except (ImportError, AttributeError):
            pytest.skip("web.brief.get_morning_brief not available")

        # Prime the cache
        client.get("/brief")
        assert compute_call_count["n"] == 1

        # Refresh
        resp = client.post("/brief/refresh")
        assert resp.status_code in (200, 204, 302), (
            f"Expected 200/204/302 from /brief/refresh, got {resp.status_code}"
        )

        # Next GET should recompute
        client.get("/brief")
        assert compute_call_count["n"] == 2, (
            "After refresh, get_morning_brief should be called again"
        )

    def test_brief_refresh_requires_login(self, client):
        """POST /brief/refresh without login should return 302 or 401."""
        resp = client.post("/brief/refresh", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_brief_refresh_rate_limited(self, client):
        """POST /brief/refresh twice quickly should return 429 on the second attempt."""
        _login_user(client)

        # First refresh — should succeed
        resp1 = client.post("/brief/refresh")
        assert resp1.status_code in (200, 204, 302), (
            f"First refresh should succeed, got {resp1.status_code}"
        )

        # Second refresh immediately — should be rate limited
        resp2 = client.post("/brief/refresh")
        assert resp2.status_code == 429, (
            f"Second refresh should be rate limited (429), got {resp2.status_code}"
        )

    def test_brief_refresh_response_format(self, client):
        """POST /brief/refresh should return JSON or redirect (not 404 or 500)."""
        _login_user(client)
        resp = client.post("/brief/refresh")
        # Route must exist (not 404) and must not error (not 5xx)
        assert resp.status_code != 404, "POST /brief/refresh route must be registered"
        assert resp.status_code < 500


# ---------------------------------------------------------------------------
# POST /cron/compute-caches — pre-population endpoint
# ---------------------------------------------------------------------------

class TestCronComputeCaches:
    """POST /cron/compute-caches pre-populates cache for all users."""

    def test_cron_compute_caches_requires_auth(self, client):
        """POST /cron/compute-caches without CRON_SECRET should return 403."""
        resp = client.post("/cron/compute-caches")
        assert resp.status_code == 403

    def test_cron_compute_caches_with_valid_auth(self, client, monkeypatch):
        """POST /cron/compute-caches with valid bearer token returns computed count."""
        monkeypatch.setenv("CRON_WORKER", "1")
        monkeypatch.setenv("CRON_SECRET", "test-secret-xyz")

        resp = client.post(
            "/cron/compute-caches",
            headers={"Authorization": "Bearer test-secret-xyz"},
        )

        # Should return 200 (or 202/204) with a result, not 403/404/500
        assert resp.status_code in (200, 202, 204), (
            f"Expected 200/202/204, got {resp.status_code}: {resp.data[:200]}"
        )

    def test_cron_compute_caches_response_includes_count(self, client, monkeypatch):
        """Response JSON should include a computed count field."""
        monkeypatch.setenv("CRON_WORKER", "1")
        monkeypatch.setenv("CRON_SECRET", "test-secret-xyz")

        resp = client.post(
            "/cron/compute-caches",
            headers={"Authorization": "Bearer test-secret-xyz"},
        )

        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}, skipping JSON assertions")

        data = resp.get_json()
        assert data is not None, "Response should be JSON"
        # Must contain at least one of: computed, count, users, total
        has_count_field = any(k in data for k in ("computed", "count", "users", "total", "ok"))
        assert has_count_field, (
            f"Response JSON should include a count/status field, got: {data}"
        )

    def test_cron_compute_caches_wrong_secret(self, client, monkeypatch):
        """POST /cron/compute-caches with wrong secret returns 403."""
        monkeypatch.setenv("CRON_SECRET", "correct-secret")

        resp = client.post(
            "/cron/compute-caches",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 403

    def test_cron_compute_caches_no_header(self, client, monkeypatch):
        """POST /cron/compute-caches with no Authorization header returns 403."""
        monkeypatch.setenv("CRON_SECRET", "some-secret")

        resp = client.post("/cron/compute-caches")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cache isolation between test runs
# ---------------------------------------------------------------------------

class TestCacheIsolation:
    """Verify test fixtures clear cache correctly so tests don't bleed into each other."""

    def test_page_cache_cleared_before_test(self):
        """The _page_cache dict should be empty at the start of each test."""
        try:
            from web.helpers import _page_cache
            assert len(_page_cache) == 0, (
                "Page cache should be empty at test start (fixture should clear it)"
            )
        except (ImportError, AttributeError):
            pytest.skip("web.helpers._page_cache not yet implemented")

    def test_page_cache_import_available(self):
        """The _page_cache dict must be importable from web.helpers."""
        try:
            from web.helpers import _page_cache, get_cached_or_compute, invalidate_cache
        except ImportError as e:
            pytest.fail(
                f"web.helpers does not expose expected cache API: {e}\n"
                "Expected: _page_cache, get_cached_or_compute, invalidate_cache"
            )
