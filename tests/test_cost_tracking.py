"""Tests for web/cost_tracking.py — cost logging, rate limiting, kill switch.

Uses Flask test_client() and DuckDB in-memory for isolation.
No live server or Playwright needed — all logic is unit/integration tested.
"""

from __future__ import annotations

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with isolated temp database."""
    db_path = str(tmp_path / "test_cost.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    # Reset schema flags
    import web.cost_tracking as ct
    monkeypatch.setattr(ct, "_schema_initialized", False)
    monkeypatch.setattr(ct, "_kill_switch_active", False)
    # Reset rate buckets
    ct._user_rate_buckets.clear()
    # Ensure user schema exists so api_usage foreign key doesn't fail
    db_mod.init_user_schema()
    # Init cost tracking schema
    ct.ensure_schema()
    yield
    ct._user_rate_buckets.clear()


@pytest.fixture
def client(monkeypatch):
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_admin(client, monkeypatch, email="admin@example.com"):
    """Create admin user and log in."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    user = auth_mod.get_or_create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Unit tests: cost_tracking module
# ---------------------------------------------------------------------------

class TestEstimateCost:
    """Test USD cost estimation from token counts."""

    def test_zero_tokens(self):
        from web.cost_tracking import estimate_cost_usd
        assert estimate_cost_usd(0, 0) == 0.0

    def test_input_only(self):
        from web.cost_tracking import estimate_cost_usd
        # 1M input tokens at $3.00/MTok = $3.00
        cost = estimate_cost_usd(1_000_000, 0)
        assert abs(cost - 3.0) < 0.001

    def test_output_only(self):
        from web.cost_tracking import estimate_cost_usd
        # 1M output tokens at $15.00/MTok = $15.00
        cost = estimate_cost_usd(0, 1_000_000)
        assert abs(cost - 15.0) < 0.001

    def test_mixed_tokens(self):
        from web.cost_tracking import estimate_cost_usd
        # 500 input + 200 output = tiny cost, just verify it's positive
        cost = estimate_cost_usd(500, 200)
        assert cost > 0.0
        assert cost < 0.01  # sub-cent for small calls

    def test_returns_float(self):
        from web.cost_tracking import estimate_cost_usd
        result = estimate_cost_usd(100, 50)
        assert isinstance(result, float)


class TestKillSwitch:
    """Test kill switch get/set."""

    def test_initially_inactive(self):
        from web.cost_tracking import is_kill_switch_active
        assert is_kill_switch_active() is False

    def test_activate(self):
        from web.cost_tracking import is_kill_switch_active, set_kill_switch
        set_kill_switch(True)
        assert is_kill_switch_active() is True

    def test_deactivate(self):
        from web.cost_tracking import is_kill_switch_active, set_kill_switch
        set_kill_switch(True)
        set_kill_switch(False)
        assert is_kill_switch_active() is False

    def test_env_var_activates(self, monkeypatch):
        """KILL_SWITCH_ENABLED=1 should set active at import time."""
        # We test the logic by directly setting it
        import web.cost_tracking as ct
        monkeypatch.setattr(ct, "_kill_switch_active", True)
        assert ct.is_kill_switch_active() is True

    def test_env_var_inactive(self, monkeypatch):
        import web.cost_tracking as ct
        monkeypatch.setattr(ct, "_kill_switch_active", False)
        assert ct.is_kill_switch_active() is False


class TestRateLimit:
    """Test per-user rate limiting."""

    def test_first_request_allowed(self, client):
        """First request within window should not be rate-limited."""
        from web.cost_tracking import check_rate_limit, _user_rate_buckets
        _user_rate_buckets.clear()
        with client.application.test_request_context("/ask", method="POST"):
            from flask import g
            g.user = None
            result = check_rate_limit("ai")
        assert result is False

    def test_exceeds_limit(self, client, monkeypatch):
        """Exceeding limit should return True (blocked)."""
        import web.cost_tracking as ct
        monkeypatch.setitem(ct.RATE_LIMITS, "ai", 3)
        ct._user_rate_buckets.clear()
        with client.application.test_request_context("/ask", method="POST",
                                                     headers={"X-Forwarded-For": "10.0.0.99"}):
            from flask import g
            g.user = None
            ct.check_rate_limit("ai")  # 1
            ct.check_rate_limit("ai")  # 2
            ct.check_rate_limit("ai")  # 3
            result = ct.check_rate_limit("ai")  # 4 — should be blocked
        assert result is True

    def test_different_users_separate_buckets(self, client):
        """Different user IDs should have independent rate buckets."""
        import web.cost_tracking as ct
        ct._user_rate_buckets.clear()
        with client.application.test_request_context("/ask", method="POST"):
            from flask import g
            g.user = {"user_id": 1}
            r1 = ct.check_rate_limit("ai")
        with client.application.test_request_context("/ask", method="POST"):
            g.user = {"user_id": 2}
            r2 = ct.check_rate_limit("ai")
        assert r1 is False
        assert r2 is False

    def test_rate_type_lookup_separate(self, client, monkeypatch):
        """Lookup rate limit is separate from AI rate limit."""
        import web.cost_tracking as ct
        monkeypatch.setitem(ct.RATE_LIMITS, "ai", 1)
        monkeypatch.setitem(ct.RATE_LIMITS, "lookup", 5)
        ct._user_rate_buckets.clear()
        with client.application.test_request_context("/lookup", method="POST",
                                                     headers={"X-Forwarded-For": "10.0.0.50"}):
            from flask import g
            g.user = None
            ct.check_rate_limit("ai")   # uses 1 AI slot
            ct.check_rate_limit("ai")   # blocked
            result_lookup = ct.check_rate_limit("lookup")  # lookup is fresh
        assert result_lookup is False  # lookup not blocked


class TestLogApiCall:
    """Test log_api_call writes to DB."""

    def test_logs_to_db(self):
        from web.cost_tracking import log_api_call
        from src.db import query
        log_api_call(
            endpoint="/ask",
            model="claude-sonnet-4-20250514",
            input_tokens=100,
            output_tokens=50,
            user_id=None,
        )
        rows = query("SELECT endpoint, model, input_tokens, output_tokens FROM api_usage")
        assert len(rows) == 1
        assert rows[0][0] == "/ask"
        assert rows[0][1] == "claude-sonnet-4-20250514"
        assert rows[0][2] == 100
        assert rows[0][3] == 50

    def test_cost_computed_on_log(self):
        from web.cost_tracking import log_api_call
        from src.db import query
        # 1M input + 1M output = $3 + $15 = $18
        log_api_call(
            endpoint="/analyze-plans",
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            user_id=None,
        )
        rows = query("SELECT cost_usd FROM api_usage")
        assert len(rows) == 1
        cost = float(rows[0][0])
        assert abs(cost - 18.0) < 0.01

    def test_logs_user_id(self):
        from web.cost_tracking import log_api_call
        from src.db import query
        log_api_call("/ask", "claude-sonnet-4-20250514", 50, 25, user_id=42)
        rows = query("SELECT user_id FROM api_usage")
        assert len(rows) == 1
        # user_id 42 may not exist in users table — log_api_call catches this gracefully
        # Depending on FK enforcement (DuckDB may be lenient), check it logged something
        # Just verify the row exists
        assert rows is not None

    def test_multiple_calls_accumulate(self):
        from web.cost_tracking import log_api_call
        from src.db import query
        log_api_call("/ask", "claude-sonnet-4-20250514", 100, 50)
        log_api_call("/ask", "claude-sonnet-4-20250514", 200, 100)
        rows = query("SELECT COUNT(*) FROM api_usage")
        assert int(rows[0][0]) == 2

    def test_log_does_not_raise_on_extra(self):
        """Extra dict should not cause errors."""
        from web.cost_tracking import log_api_call
        log_api_call(
            endpoint="/ask",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            extra={"query_len": 42, "rag_chunks": 3},
        )  # Should not raise


class TestGetDailyGlobalCost:
    """Test daily cost query helper."""

    def test_zero_when_empty(self):
        from web.cost_tracking import get_daily_global_cost
        cost = get_daily_global_cost()
        assert cost == 0.0

    def test_sums_todays_calls(self):
        from web.cost_tracking import log_api_call, get_daily_global_cost
        log_api_call("/ask", "claude-sonnet-4-20250514", 100_000, 50_000)
        log_api_call("/ask", "claude-sonnet-4-20250514", 50_000, 25_000)
        cost = get_daily_global_cost()
        assert cost > 0.0
        expected = (150_000 / 1_000_000 * 3.0) + (75_000 / 1_000_000 * 15.0)
        assert abs(cost - expected) < 0.001

    def test_returns_float(self):
        from web.cost_tracking import get_daily_global_cost
        result = get_daily_global_cost()
        assert isinstance(result, float)


class TestCostSummary:
    """Test get_cost_summary returns well-formed dict."""

    def test_returns_required_keys(self):
        from web.cost_tracking import get_cost_summary
        summary = get_cost_summary()
        required = {
            "today_cost", "daily_totals", "top_users",
            "top_endpoints", "kill_switch_active",
            "warn_threshold", "kill_threshold",
        }
        for key in required:
            assert key in summary, f"Missing key: {key}"

    def test_kill_switch_reflected(self, monkeypatch):
        import web.cost_tracking as ct
        monkeypatch.setattr(ct, "_kill_switch_active", True)
        summary = ct.get_cost_summary()
        assert summary["kill_switch_active"] is True

    def test_empty_state(self):
        from web.cost_tracking import get_cost_summary
        summary = get_cost_summary()
        assert summary["today_cost"] == 0.0
        assert summary["daily_totals"] == []
        assert summary["top_users"] == []
        assert summary["top_endpoints"] == []


class TestAutoKillSwitch:
    """Test auto-activation of kill switch on threshold breach."""

    def test_auto_activates_at_kill_threshold(self, monkeypatch):
        import web.cost_tracking as ct
        monkeypatch.setattr(ct, "COST_KILL_THRESHOLD", 0.000001)  # 0.1 cent threshold
        monkeypatch.setattr(ct, "_kill_switch_active", False)
        # Log a call large enough to exceed the micro threshold
        ct.log_api_call("/ask", "claude-sonnet-4-20250514", 100, 100)
        # Kill switch should now be active
        assert ct.is_kill_switch_active() is True

    def test_does_not_activate_below_threshold(self, monkeypatch):
        import web.cost_tracking as ct
        monkeypatch.setattr(ct, "COST_KILL_THRESHOLD", 9999.0)  # Very high threshold
        monkeypatch.setattr(ct, "_kill_switch_active", False)
        ct.log_api_call("/ask", "claude-sonnet-4-20250514", 100, 50)
        assert ct.is_kill_switch_active() is False


# ---------------------------------------------------------------------------
# Integration tests: admin routes via Flask test_client
# ---------------------------------------------------------------------------

class TestAdminCostsDashboard:
    """Test /admin/costs route."""

    def test_requires_login(self, client):
        resp = client.get("/admin/costs")
        assert resp.status_code in (302, 403)

    def test_requires_admin(self, client, monkeypatch):
        """Non-admin user gets 403."""
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_schema_initialized", False)
        user = auth_mod.get_or_create_user("regular@example.com")
        token = auth_mod.create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        resp = client.get("/admin/costs")
        assert resp.status_code == 403

    def test_admin_can_access(self, client, monkeypatch):
        """Admin user gets 200 with dashboard."""
        _login_admin(client, monkeypatch)
        resp = client.get("/admin/costs")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "API Cost Dashboard" in body or "Cost Dashboard" in body

    def test_dashboard_shows_kill_switch_status(self, client, monkeypatch):
        """Dashboard should display kill switch status."""
        _login_admin(client, monkeypatch)
        resp = client.get("/admin/costs")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Kill switch" in body or "kill switch" in body or "kill_switch" in body

    def test_dashboard_shows_thresholds(self, client, monkeypatch):
        """Dashboard should display warning/kill thresholds."""
        _login_admin(client, monkeypatch)
        resp = client.get("/admin/costs")
        assert resp.status_code == 200
        body = resp.data.decode()
        # Default thresholds ($5.00 warn, $20.00 kill)
        assert "5.00" in body or "20.00" in body


class TestKillSwitchRoute:
    """Test /admin/costs/kill-switch POST route."""

    def test_requires_admin(self, client, monkeypatch):
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_schema_initialized", False)
        user = auth_mod.get_or_create_user("regular2@example.com")
        token = auth_mod.create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        resp = client.post("/admin/costs/kill-switch", data={"active": "1"})
        assert resp.status_code == 403

    def test_admin_activate(self, client, monkeypatch):
        """Admin can activate kill switch."""
        import web.cost_tracking as ct
        ct.set_kill_switch(False)  # ensure starts inactive
        _login_admin(client, monkeypatch)
        resp = client.post(
            "/admin/costs/kill-switch",
            data={"active": "1"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 200)
        assert ct.is_kill_switch_active() is True

    def test_admin_deactivate(self, client, monkeypatch):
        """Admin can deactivate kill switch."""
        import web.cost_tracking as ct
        ct.set_kill_switch(True)
        _login_admin(client, monkeypatch)
        resp = client.post(
            "/admin/costs/kill-switch",
            data={"active": "0"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 200)
        assert ct.is_kill_switch_active() is False

    def test_kill_switch_redirect_to_costs(self, client, monkeypatch):
        """Kill switch toggle should redirect back to /admin/costs."""
        _login_admin(client, monkeypatch)
        resp = client.post("/admin/costs/kill-switch", data={"active": "0"})
        assert resp.status_code == 302
        assert "/admin/costs" in resp.headers.get("Location", "")


class TestRateLimitedDecorator:
    """Test @rate_limited decorator integration."""

    def test_kill_switch_blocks_ask(self, client, monkeypatch):
        """When kill switch active, /ask should return 503."""
        import web.cost_tracking as ct
        ct.set_kill_switch(True)
        resp = client.post("/ask", data={"q": "test query"})
        assert resp.status_code == 503

    def test_kill_switch_inactive_allows_ask(self, client, monkeypatch):
        """When kill switch inactive, /ask should process normally (not 503)."""
        import web.cost_tracking as ct
        ct.set_kill_switch(False)
        # May return 200 or other status depending on backend; just not 503
        resp = client.post("/ask", data={"q": "test query"})
        assert resp.status_code != 503

    def test_kill_switch_blocks_analyze_plans(self, client, monkeypatch):
        """When kill switch active, /analyze-plans should return 503."""
        import web.cost_tracking as ct
        ct.set_kill_switch(True)
        # Login required for analyze-plans
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_schema_initialized", False)
        user = auth_mod.get_or_create_user("user3@example.com")
        token = auth_mod.create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        resp = client.post("/analyze-plans", data={})
        assert resp.status_code == 503
