"""Tests for Sprint 76-2: Cost Tracking Middleware Wiring.

Tests:
- after_request hook logs usage when g.api_usage is set
- after_request hook does NOT log when g.api_usage is absent
- Rate limiter blocks excess calls
- Daily usage aggregation produces correct totals
- Kill switch returns 503 for AI routes
- Kill switch does NOT block non-AI routes
- Cron endpoint requires CRON_SECRET auth
- Cron endpoint returns 200 on success
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-secret"}


# ---------------------------------------------------------------------------
# Task 76-2-1: after_request hook logs g.api_usage
# ---------------------------------------------------------------------------

class TestAfterRequestApiUsageLogging:
    def test_logs_api_usage_when_set(self):
        """After-request hook calls log_api_call when g.api_usage is set."""
        with app.test_request_context("/ask", method="POST"):
            from flask import g
            g.api_usage = {
                "endpoint": "/ask",
                "model": "claude-sonnet-4-20250514",
                "input_tokens": 100,
                "output_tokens": 50,
                "extra": {"query": "test"},
            }
            g.user = None

            with patch("web.cost_tracking.log_api_call") as mock_log:
                from web.app import _log_api_usage
                response = MagicMock(status_code=200)
                result = _log_api_usage(response)
                # Should return the response unchanged
                assert result is response
                # Should have called log_api_call
                mock_log.assert_called_once()
                call_kwargs = mock_log.call_args
                assert call_kwargs[1]["endpoint"] == "/ask" or call_kwargs[0][0] == "/ask"

    def test_no_log_when_api_usage_absent(self):
        """After-request hook does NOT call log_api_call when g.api_usage is absent."""
        with app.test_request_context("/health", method="GET"):
            from flask import g
            # Ensure g.api_usage is NOT set
            if hasattr(g, "api_usage"):
                del g.api_usage

            with patch("web.cost_tracking.log_api_call") as mock_log:
                from web.app import _log_api_usage
                response = MagicMock(status_code=200)
                result = _log_api_usage(response)
                assert result is response
                mock_log.assert_not_called()

    def test_no_log_when_api_usage_empty_dict(self):
        """After-request hook does NOT log when g.api_usage is falsy (empty dict / None)."""
        with app.test_request_context("/ask", method="POST"):
            from flask import g
            g.api_usage = {}  # falsy
            g.user = None

            with patch("web.cost_tracking.log_api_call") as mock_log:
                from web.app import _log_api_usage
                response = MagicMock(status_code=200)
                _log_api_usage(response)
                mock_log.assert_not_called()

    def test_hook_does_not_fail_response(self):
        """After-request hook catches exceptions and never fails the response."""
        with app.test_request_context("/ask", method="POST"):
            from flask import g
            g.api_usage = {
                "endpoint": "/ask",
                "model": "test-model",
                "input_tokens": 10,
                "output_tokens": 5,
            }
            g.user = None

            with patch("web.cost_tracking.log_api_call", side_effect=Exception("DB error")):
                from web.app import _log_api_usage
                response = MagicMock(status_code=200)
                # Should NOT raise even when log_api_call fails
                result = _log_api_usage(response)
                assert result is response


# ---------------------------------------------------------------------------
# Task 76-2-6: Kill switch blocks AI routes
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_kill_switch_guard_blocks_ask_path(self):
        """_kill_switch_guard returns 503 JSON for /ask when kill switch is active."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(True)
        try:
            # Simulate a non-TESTING request context
            with app.test_request_context("/ask", method="POST"):
                app.config["TESTING"] = False
                result = _kill_switch_guard()
                app.config["TESTING"] = True
                assert result is not None, "Expected 503 response, got None"
                # result is a (response, status_code) tuple
                resp, status = result
                assert status == 503
        finally:
            set_kill_switch(False)
            app.config["TESTING"] = True

    def test_kill_switch_guard_blocks_analyze_path(self):
        """_kill_switch_guard returns 503 for /analyze when kill switch is active."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(True)
        try:
            with app.test_request_context("/analyze", method="POST"):
                app.config["TESTING"] = False
                result = _kill_switch_guard()
                app.config["TESTING"] = True
                assert result is not None
                _, status = result
                assert status == 503
        finally:
            set_kill_switch(False)
            app.config["TESTING"] = True

    def test_kill_switch_guard_passes_health(self):
        """_kill_switch_guard returns None (no-op) for /health even when active."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(True)
        try:
            with app.test_request_context("/health", method="GET"):
                app.config["TESTING"] = False
                result = _kill_switch_guard()
                app.config["TESTING"] = True
                assert result is None, "Health endpoint should NOT be blocked"
        finally:
            set_kill_switch(False)
            app.config["TESTING"] = True

    def test_kill_switch_guard_passes_root(self):
        """_kill_switch_guard returns None for / even when kill switch is active."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(True)
        try:
            with app.test_request_context("/", method="GET"):
                app.config["TESTING"] = False
                result = _kill_switch_guard()
                app.config["TESTING"] = True
                assert result is None, "Root endpoint should NOT be blocked"
        finally:
            set_kill_switch(False)
            app.config["TESTING"] = True

    def test_kill_switch_inactive_passes_ask(self):
        """Kill switch inactive → _kill_switch_guard returns None for /ask."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(False)
        with app.test_request_context("/ask", method="POST"):
            app.config["TESTING"] = False
            result = _kill_switch_guard()
            app.config["TESTING"] = True
            assert result is None, "Should not block when kill switch is off"

    def test_kill_switch_response_is_json(self):
        """_kill_switch_guard response body is valid JSON with kill_switch=True."""
        from web.cost_tracking import set_kill_switch
        from web.app import _kill_switch_guard
        set_kill_switch(True)
        try:
            with app.test_request_context("/ask", method="POST"):
                app.config["TESTING"] = False
                result = _kill_switch_guard()
                app.config["TESTING"] = True
                assert result is not None
                resp, status = result
                with app.test_request_context():
                    data = json.loads(resp.get_data(as_text=True))
                    assert data.get("kill_switch") is True
                    assert "error" in data
        finally:
            set_kill_switch(False)
            app.config["TESTING"] = True

    def test_kill_switch_does_not_block_health_via_http(self, client):
        """Kill switch active → GET /health still returns non-503 via test client."""
        from web.cost_tracking import set_kill_switch
        set_kill_switch(True)
        try:
            resp = client.get("/health")
            assert resp.status_code != 503
        finally:
            set_kill_switch(False)


# ---------------------------------------------------------------------------
# Task 76-2-4: aggregate_daily_usage
# ---------------------------------------------------------------------------

class TestAggregateDailyUsage:
    def test_aggregate_returns_dict_with_expected_keys(self):
        """aggregate_daily_usage returns dict with required keys."""
        from web.cost_tracking import aggregate_daily_usage
        result = aggregate_daily_usage(date.today() - timedelta(days=1))
        assert isinstance(result, dict)
        assert "summary_date" in result
        assert "total_calls" in result
        assert "total_cost_usd" in result
        assert "inserted" in result

    def test_aggregate_handles_missing_table_gracefully(self):
        """aggregate_daily_usage handles DB errors without raising."""
        from web.cost_tracking import aggregate_daily_usage
        # aggregate_daily_usage imports query_one from src.db inside the function
        with patch("src.db.query_one", side_effect=Exception("table not found")):
            # Should not raise; returns result with inserted=False
            result = aggregate_daily_usage(date.today() - timedelta(days=1))
            assert isinstance(result, dict)
            assert result.get("inserted") is False

    def test_aggregate_with_specific_date(self):
        """aggregate_daily_usage accepts a specific target_date."""
        from web.cost_tracking import aggregate_daily_usage
        target = date(2025, 1, 15)
        result = aggregate_daily_usage(target)
        assert result["summary_date"] == "2025-01-15"

    def test_aggregate_defaults_to_yesterday(self):
        """aggregate_daily_usage defaults to yesterday when no date given."""
        from web.cost_tracking import aggregate_daily_usage
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = aggregate_daily_usage()
        assert result["summary_date"] == yesterday


# ---------------------------------------------------------------------------
# Task 76-2-5: Cron endpoint /cron/aggregate-api-usage
# ---------------------------------------------------------------------------

class TestCronAggregateApiUsage:
    def test_cron_requires_auth(self, client):
        """POST /cron/aggregate-api-usage without auth returns 403."""
        # Need to be in cron worker mode for the cron route to be accessible
        import os
        with patch.dict(os.environ, {"CRON_WORKER": "1", "CRON_SECRET": "test-secret"}):
            resp = client.post(
                "/cron/aggregate-api-usage",
                headers={},  # no auth header
            )
            assert resp.status_code == 403

    def test_cron_requires_valid_secret(self, client):
        """POST /cron/aggregate-api-usage with wrong secret returns 403."""
        import os
        with patch.dict(os.environ, {"CRON_WORKER": "1", "CRON_SECRET": "test-secret"}):
            resp = client.post(
                "/cron/aggregate-api-usage",
                headers={"Authorization": "Bearer wrong-secret"},
            )
            assert resp.status_code == 403

    def test_cron_returns_200_on_success(self, client):
        """POST /cron/aggregate-api-usage with valid auth returns 200."""
        import os
        secret = "test-secret-76-2"
        with patch.dict(os.environ, {"CRON_WORKER": "1", "CRON_SECRET": secret}):
            with patch("web.cost_tracking.aggregate_daily_usage", return_value={
                "summary_date": "2025-01-15",
                "total_calls": 10,
                "total_cost_usd": 0.05,
                "inserted": True,
            }):
                resp = client.post(
                    "/cron/aggregate-api-usage",
                    headers={"Authorization": f"Bearer {secret}"},
                )
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data.get("ok") is True

    def test_cron_accepts_date_param(self, client):
        """POST /cron/aggregate-api-usage accepts ?date=YYYY-MM-DD query param."""
        import os
        secret = "test-secret-76-2"
        with patch.dict(os.environ, {"CRON_WORKER": "1", "CRON_SECRET": secret}):
            with patch("web.cost_tracking.aggregate_daily_usage", return_value={
                "summary_date": "2025-01-10",
                "total_calls": 5,
                "total_cost_usd": 0.02,
                "inserted": True,
            }) as mock_agg:
                resp = client.post(
                    "/cron/aggregate-api-usage?date=2025-01-10",
                    headers={"Authorization": f"Bearer {secret}"},
                )
                assert resp.status_code == 200
                # Verify the date was passed correctly
                mock_agg.assert_called_once()
                call_args = mock_agg.call_args
                passed_date = call_args[0][0] if call_args[0] else call_args[1].get("target_date")
                assert passed_date == date(2025, 1, 10)

    def test_cron_rejects_invalid_date(self, client):
        """POST /cron/aggregate-api-usage with invalid date returns 400."""
        import os
        secret = "test-secret-76-2"
        with patch.dict(os.environ, {"CRON_WORKER": "1", "CRON_SECRET": secret}):
            resp = client.post(
                "/cron/aggregate-api-usage?date=not-a-date",
                headers={"Authorization": f"Bearer {secret}"},
            )
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiter basics
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_rate_limiter_allows_initial_calls(self):
        """Rate limiter allows calls within limit."""
        from web.cost_tracking import check_rate_limit, _user_rate_buckets
        # Use a unique key so we don't cross-contaminate other tests
        import time
        unique_ip = f"ip:test-76-2-{time.time()}"

        with patch("web.cost_tracking._get_user_key", return_value=unique_ip):
            result = check_rate_limit("ai")
            assert result is False  # not rate limited

    def test_rate_limiter_blocks_excess_calls(self):
        """Rate limiter blocks calls exceeding the limit."""
        from web.cost_tracking import check_rate_limit, RATE_LIMITS
        import time

        unique_ip = f"ip:test-76-2-excess-{time.time()}"
        ai_limit = RATE_LIMITS["ai"]

        with patch("web.cost_tracking._get_user_key", return_value=unique_ip):
            # Fill up the bucket
            for _ in range(ai_limit):
                check_rate_limit("ai")
            # Next call should be rate-limited
            result = check_rate_limit("ai")
            assert result is True  # rate limited
