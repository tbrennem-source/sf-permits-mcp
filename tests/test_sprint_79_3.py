"""Tests for QS8-T1-B: brief pipeline stats + signals/velocity cron endpoints.

Tests:
- test_pipeline_stats_included_in_brief
- test_cron_signals_requires_auth
- test_cron_signals_runs_severity (signals pipeline is invoked)
- test_cron_velocity_refresh_requires_auth
- test_cron_velocity_refresh_runs
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cron_client(monkeypatch):
    """Flask test client configured for cron worker mode."""
    monkeypatch.setenv("CRON_WORKER", "1")
    monkeypatch.setenv("CRON_SECRET", "test-secret-qs8b")
    from web.app import app
    app.config["TESTING"] = True
    return app.test_client()


def _auth():
    return {"Authorization": "Bearer test-secret-qs8b"}


def _bad_auth():
    return {"Authorization": "Bearer wrong-secret"}


# ---------------------------------------------------------------------------
# Task B-1: pipeline_stats in get_morning_brief
# ---------------------------------------------------------------------------

class TestPipelineStatsInBrief:
    """get_morning_brief() must return 'pipeline_stats' key."""

    def test_pipeline_stats_included_in_brief(self, monkeypatch):
        """get_morning_brief returns a dict with pipeline_stats key."""
        # Patch all section helpers so DB is not needed
        _noop_list = MagicMock(return_value=[])
        _noop_dict = MagicMock(return_value={})
        _noop_none = MagicMock(return_value=None)

        patches = [
            patch("web.brief._get_watched_changes", _noop_list),
            patch("web.brief._get_plan_review_activity", _noop_list),
            patch("web.brief._get_predictability", _noop_list),
            patch("web.brief._get_inspection_results", _noop_list),
            patch("web.brief._get_new_filings", _noop_list),
            patch("web.brief._get_team_activity", _noop_list),
            patch("web.brief._get_expiring_permits", _noop_list),
            patch("web.brief._get_regulatory_alerts", _noop_list),
            patch("web.brief._get_property_snapshot", _noop_list),
            patch("web.brief._get_last_refresh", _noop_none),
            patch("web.brief.get_pipeline_health_for_brief", _noop_dict),
            patch("web.brief._get_planning_context", _noop_list),
            patch("web.brief._get_compliance_calendar", _noop_list),
            patch("web.brief._get_data_quality", _noop_dict),
            patch("web.brief.get_street_use_activity_for_user", _noop_list),
            patch("web.brief.get_nearby_development_for_user", _noop_list),
            patch("web.brief._get_change_velocity", _noop_dict),
            patch("web.brief._get_prep_summary", _noop_dict),
            patch("web.brief._get_pipeline_stats", MagicMock(return_value={
                "recent_jobs": [],
                "avg_duration_seconds": 42.5,
                "last_24h_success": 3,
                "last_24h_failed": 0,
                "last_24h_jobs": 3,
            })),
            # query for watch count
            patch("web.brief.query", MagicMock(return_value=[(0,)])),
        ]

        for p in patches:
            p.start()

        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1, lookback_days=1)
        finally:
            for p in patches:
                p.stop()

        assert "pipeline_stats" in result, "pipeline_stats key must be present in brief"
        ps = result["pipeline_stats"]
        assert ps["avg_duration_seconds"] == 42.5
        assert ps["last_24h_success"] == 3
        assert "recent_jobs" in ps

    def test_pipeline_stats_empty_on_db_error(self, monkeypatch):
        """_get_pipeline_stats returns {} on DB failure (non-fatal)."""
        with patch("web.brief.query", side_effect=Exception("DB unavailable")):
            from web.brief import _get_pipeline_stats
            result = _get_pipeline_stats()
        assert result == {}, "Should return empty dict on failure"


# ---------------------------------------------------------------------------
# Task B-2: /cron/signals endpoint
# ---------------------------------------------------------------------------

class TestCronSignals:
    """Tests for POST /cron/signals."""

    def test_cron_signals_requires_auth(self, cron_client):
        """POST /cron/signals with no token returns 403."""
        resp = cron_client.post("/cron/signals")
        assert resp.status_code == 403

    def test_cron_signals_requires_auth_bad_token(self, cron_client):
        """POST /cron/signals with wrong token returns 403."""
        resp = cron_client.post("/cron/signals", headers=_bad_auth())
        assert resp.status_code == 403

    def test_cron_signals_runs_severity(self, cron_client):
        """POST /cron/signals with valid auth invokes signal pipeline."""
        mock_pipeline = MagicMock(return_value={"signals": 5, "parcels": 3})
        mock_conn = MagicMock()

        with patch("src.signals.pipeline.run_signal_pipeline", mock_pipeline), \
             patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.execute_write", MagicMock()):
            resp = cron_client.post("/cron/signals", headers=_auth())

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["status"] == "success"
        assert data.get("signals") == 5
        assert "elapsed_seconds" in data

    def test_cron_signals_returns_error_on_pipeline_failure(self, cron_client):
        """POST /cron/signals returns ok=False when pipeline raises."""
        mock_conn = MagicMock()

        with patch("src.signals.pipeline.run_signal_pipeline",
                   side_effect=Exception("signal boom")), \
             patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.execute_write", MagicMock()):
            resp = cron_client.post("/cron/signals", headers=_auth())

        assert resp.status_code in (200, 500)  # endpoint signals error via ok=False or status code
        data = json.loads(resp.data)
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "error" in data


# ---------------------------------------------------------------------------
# Task B-3: /cron/velocity-refresh endpoint
# ---------------------------------------------------------------------------

class TestCronVelocityRefresh:
    """Tests for POST /cron/velocity-refresh."""

    def test_cron_velocity_refresh_requires_auth(self, cron_client):
        """POST /cron/velocity-refresh with no token returns 403."""
        resp = cron_client.post("/cron/velocity-refresh")
        assert resp.status_code == 403

    def test_cron_velocity_refresh_requires_auth_bad_token(self, cron_client):
        """POST /cron/velocity-refresh with wrong token returns 403."""
        resp = cron_client.post("/cron/velocity-refresh", headers=_bad_auth())
        assert resp.status_code == 403

    def test_cron_velocity_refresh_runs(self, cron_client):
        """POST /cron/velocity-refresh invokes refresh_velocity_v2."""
        mock_v2 = MagicMock(return_value={"rows_inserted": 120, "stations": 8, "periods": 2})
        mock_transitions = MagicMock(return_value={"transitions": 40})
        mock_conn = MagicMock()

        with patch("src.station_velocity_v2.refresh_velocity_v2", mock_v2), \
             patch("src.tools.station_predictor.refresh_station_transitions", mock_transitions), \
             patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.execute_write", MagicMock()):
            resp = cron_client.post("/cron/velocity-refresh", headers=_auth())

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["status"] == "success"
        assert data.get("rows_inserted") == 120
        assert data.get("stations") == 8
        assert data.get("transitions") == 40
        assert "elapsed_seconds" in data

    def test_cron_velocity_refresh_returns_error_on_failure(self, cron_client):
        """POST /cron/velocity-refresh returns ok=False when refresh_velocity_v2 raises."""
        mock_conn = MagicMock()

        with patch("src.station_velocity_v2.refresh_velocity_v2",
                   side_effect=Exception("velocity boom")), \
             patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.execute_write", MagicMock()):
            resp = cron_client.post("/cron/velocity-refresh", headers=_auth())

        assert resp.status_code in (200, 500)  # endpoint signals error via ok=False or status code
        data = json.loads(resp.data)
        assert data["ok"] is False
        assert data["status"] == "failed"
        assert "error" in data

    def test_cron_velocity_refresh_transitions_failure_non_fatal(self, cron_client):
        """Transitions failure does not fail the overall velocity-refresh job."""
        mock_v2 = MagicMock(return_value={"rows_inserted": 50, "stations": 4})
        mock_conn = MagicMock()

        with patch("src.station_velocity_v2.refresh_velocity_v2", mock_v2), \
             patch("src.tools.station_predictor.refresh_station_transitions",
                   side_effect=Exception("transitions boom")), \
             patch("src.db.get_connection", return_value=mock_conn), \
             patch("src.db.execute_write", MagicMock()):
            resp = cron_client.post("/cron/velocity-refresh", headers=_auth())

        assert resp.status_code == 200
        data = json.loads(resp.data)
        # Should still succeed overall despite transitions failure
        assert data["ok"] is True
        assert "transitions_error" in data
        assert data.get("rows_inserted") == 50
