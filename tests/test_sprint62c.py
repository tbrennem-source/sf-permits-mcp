"""Tests for Sprint 62C: Security headers + rate limiting (web/security.py)."""
from __future__ import annotations

import os
import time
import types
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Return a configured Flask test client."""
    # Must be imported AFTER env is clean so security module uses correct backend
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Security header tests
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_csp_header_present(self, client):
        resp = client.get("/health")
        assert "Content-Security-Policy" in resp.headers

    def test_csp_unsafe_inline_script(self, client):
        resp = client.get("/health")
        csp = resp.headers["Content-Security-Policy"]
        assert "'unsafe-inline'" in csp
        assert "script-src" in csp

    def test_csp_unsafe_inline_style(self, client):
        resp = client.get("/health")
        csp = resp.headers["Content-Security-Policy"]
        assert "style-src" in csp
        assert "'unsafe-inline'" in csp

    def test_x_frame_options_deny(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_content_type_options_nosniff(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy_present(self, client):
        resp = client.get("/health")
        assert "Referrer-Policy" in resp.headers
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_present(self, client):
        resp = client.get("/health")
        assert "Permissions-Policy" in resp.headers

    def test_hsts_present_in_production(self, client, monkeypatch):
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        # Re-import so the env var is picked up inside the function
        resp = client.get("/health")
        assert "Strict-Transport-Security" in resp.headers

    def test_hsts_absent_without_railway_env(self, client, monkeypatch):
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("BASE_URL", raising=False)
        resp = client.get("/health")
        assert "Strict-Transport-Security" not in resp.headers


# ---------------------------------------------------------------------------
# User-agent blocking unit tests (pure function)
# ---------------------------------------------------------------------------

class TestIsBlockedUserAgent:
    def setup_method(self):
        from web.security import is_blocked_user_agent
        self.fn = is_blocked_user_agent

    def test_blocks_python_requests(self):
        assert self.fn("python-requests/2.28.0") is True

    def test_blocks_scrapy(self):
        assert self.fn("Scrapy/2.7 (+https://scrapy.org)") is True

    def test_blocks_go_http_client(self):
        assert self.fn("Go-http-client/1.1") is True

    def test_blocks_googlebot(self):
        # All bots blocked in beta
        assert self.fn("Googlebot/2.1 (+http://www.google.com/bot.html)") is True

    def test_allows_chrome(self):
        assert self.fn("Mozilla/5.0 (Windows NT 10.0) Chrome/120.0.0.0") is False

    def test_allows_curl(self):
        assert self.fn("curl/7.88.1") is False

    def test_allows_none(self):
        assert self.fn(None) is False

    def test_allows_empty_string(self):
        assert self.fn("") is False

    def test_blocks_wget(self):
        assert self.fn("Wget/1.21.3") is True

    def test_blocks_spider(self):
        assert self.fn("MySpider/1.0") is True

    def test_blocks_crawler(self):
        assert self.fn("SomeCrawler/2.0") is True


# ---------------------------------------------------------------------------
# UA blocking integration tests (Flask routes)
# ---------------------------------------------------------------------------

class TestUABlockingRoutes:
    def test_health_accessible_with_bot_ua(self, client):
        resp = client.get("/health", headers={"User-Agent": "python-requests/2.28.0"})
        assert resp.status_code == 200

    def test_non_health_returns_403_for_bot_ua(self, client):
        resp = client.get("/", headers={"User-Agent": "Scrapy/2.7"})
        assert resp.status_code == 403

    def test_cron_accessible_with_bot_ua(self, client):
        # /cron/* endpoints are exempt from UA blocking
        resp = client.get("/cron/status", headers={"User-Agent": "python-requests/2.28.0"})
        # 200 or 405 (method not allowed) is fine — just not 403
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Extended blocked paths
# ---------------------------------------------------------------------------

class TestExtendedBlockedPaths:
    def test_api_v1_returns_404(self, client):
        resp = client.get("/api/v1/something")
        assert resp.status_code == 404

    def test_graphql_returns_404(self, client):
        resp = client.get("/graphql")
        assert resp.status_code == 404

    def test_debug_returns_404(self, client):
        resp = client.get("/debug")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Daily limit unit tests (pure function)
# ---------------------------------------------------------------------------

class TestCheckDailyLimit:
    """Unit tests for check_daily_limit using mocked DB."""

    def _call(self, user_id=None, ip="1.2.3.4", limit=None, db_count=0):
        from web import security
        # Clear cache between tests
        security._daily_cache.clear()

        with mock.patch("web.security.query", return_value=[(db_count,)]):
            return security.check_daily_limit(user_id, ip, limit=limit)

    def test_returns_false_when_under_limit(self):
        result = self._call(user_id=1, db_count=50, limit=200)
        assert result is False

    def test_returns_true_when_over_limit(self):
        result = self._call(user_id=1, db_count=200, limit=200)
        assert result is True

    def test_returns_true_when_at_exact_limit(self):
        result = self._call(user_id=None, ip="1.2.3.4", db_count=50, limit=50)
        assert result is True

    def test_cache_returns_same_result_within_ttl(self):
        from web import security
        security._daily_cache.clear()

        call_count = 0

        def mock_query(sql, params=None):
            nonlocal call_count
            call_count += 1
            return [(10,)]

        with mock.patch("web.security.query", side_effect=mock_query):
            r1 = security.check_daily_limit(None, "1.2.3.4", limit=50)
            r2 = security.check_daily_limit(None, "1.2.3.4", limit=50)

        # Second call should hit cache, not DB
        assert call_count == 1
        assert r1 == r2

    def test_fails_open_on_db_error(self):
        from web import security
        security._daily_cache.clear()

        with mock.patch("web.security.query", side_effect=Exception("DB down")):
            result = security.check_daily_limit(1, "1.2.3.4")

        assert result is False  # Fail open — don't block on DB error

    def test_anon_limit_is_50(self):
        from web import security
        security._daily_cache.clear()

        with mock.patch("web.security.query", return_value=[(51,)]) as m:
            result = security.check_daily_limit(None, "1.2.3.4")

        assert result is True

    def test_auth_limit_is_200(self):
        from web import security
        security._daily_cache.clear()

        with mock.patch("web.security.query", return_value=[(199,)]) as m:
            result = security.check_daily_limit(42, "1.2.3.4")

        assert result is False


# ---------------------------------------------------------------------------
# Daily limit exemption tests (Flask routes)
# ---------------------------------------------------------------------------

class TestDailyLimitExemptions:
    """Ensure critical paths are exempt from daily limits."""

    def _patch_over_limit(self):
        """Patch check_daily_limit to always return True (over limit)."""
        return mock.patch("web.security.check_daily_limit", return_value=True)

    def test_activity_track_exempt(self, client):
        with self._patch_over_limit():
            resp = client.post("/api/activity/track", json={})
        # Should NOT be 429 — exempt from daily limits
        assert resp.status_code != 429

    def test_health_exempt(self, client):
        with self._patch_over_limit():
            resp = client.get("/health")
        assert resp.status_code != 429

    def test_robots_txt_exempt(self, client):
        with self._patch_over_limit():
            resp = client.get("/robots.txt")
        assert resp.status_code != 429

    def test_static_files_exempt(self, client):
        with self._patch_over_limit():
            resp = client.get("/static/style.css")
        # 200 or 404 (file may not exist), but NOT 429
        assert resp.status_code != 429

    def test_auth_routes_exempt(self, client):
        with self._patch_over_limit():
            resp = client.get("/auth/login")
        assert resp.status_code != 429
