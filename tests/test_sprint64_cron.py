"""Tests for Sprint 64 cron pipeline additions: signals + velocity v2 in nightly."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def cron_client(monkeypatch):
    """Flask test client configured for cron worker mode."""
    monkeypatch.setenv("CRON_WORKER", "true")
    monkeypatch.setenv("CRON_SECRET", "test-secret-sprint64")
    from web.app import app
    app.config["TESTING"] = True
    return app.test_client()


def _auth_header():
    return {"Authorization": "Bearer test-secret-sprint64"}


def _mock_nightly_subtasks():
    """Context manager that mocks all nightly sub-task imports."""
    return _NightlyMocks()


class _NightlyMocks:
    """Helper to mock all sub-tasks called during cron_nightly."""

    def __init__(self):
        self.patches = []
        self._mocks = {}

    def __enter__(self):
        targets = {
            "run_async": ("web.routes_cron.run_async", MagicMock(return_value={"status": "ok", "changes_inserted": 2})),
            "execute_write": ("src.db.execute_write", MagicMock()),
            "run_triage": ("scripts.feedback_triage.run_triage", MagicMock(return_value={})),
            "admin_users": ("web.activity.get_admin_users", MagicMock(return_value=[])),
            "cleanup_expired": ("web.plan_images.cleanup_expired", MagicMock(return_value=0)),
            "cleanup_jobs": ("web.plan_jobs.cleanup_old_jobs", MagicMock(return_value=0)),
            "velocity_v1": ("web.station_velocity.refresh_station_velocity", MagicMock(return_value={})),
            "congestion": ("web.station_velocity.refresh_station_congestion", MagicMock(return_value={"congestion_stations": 0})),
            "reviewer": ("web.reviewer_graph.refresh_reviewer_interactions", MagicMock(return_value={})),
            "ops_chunks": ("web.ops_chunks.ingest_ops_chunks", MagicMock(return_value=0)),
            "dq_cache": ("web.data_quality.refresh_dq_cache", MagicMock(return_value={"checks": 12})),
            "signal_pipeline": ("src.signals.pipeline.run_signal_pipeline", MagicMock(return_value={"signals": 10})),
            "velocity_v2": ("src.station_velocity_v2.refresh_velocity_v2", MagicMock(return_value={"stations": 42})),
            "transitions": ("src.tools.station_predictor.refresh_station_transitions", MagicMock(return_value={"transitions": 5})),
            "get_connection": ("src.db.get_connection", MagicMock(return_value=MagicMock())),
        }
        for key, (target, mock_obj) in targets.items():
            p = patch(target, mock_obj)
            p.start()
            self.patches.append(p)
            self._mocks[key] = mock_obj
        return self._mocks

    def __exit__(self, *args):
        for p in reversed(self.patches):
            p.stop()


class TestNightlyIncludesSignals:
    """Verify signals pipeline is called and returned in nightly response."""

    def test_signals_in_response(self, cron_client):
        with _mock_nightly_subtasks() as mocks:
            resp = cron_client.post("/cron/nightly", headers=_auth_header())

        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert "signals" in data
        assert data["signals"]["signals"] == 10

    def test_velocity_v2_in_response(self, cron_client):
        with _mock_nightly_subtasks() as mocks:
            resp = cron_client.post("/cron/nightly", headers=_auth_header())

        data = json.loads(resp.data)
        assert "velocity_v2" in data
        assert data["velocity_v2"]["stations"] == 42
        assert data["velocity_v2"]["transitions"] == 5


class TestNightlyNonFatal:
    """Signal/velocity failures should not fail the nightly pipeline."""

    def test_signals_error_captured(self, cron_client):
        with _mock_nightly_subtasks() as mocks:
            mocks["signal_pipeline"].side_effect = Exception("signal boom")
            resp = cron_client.post("/cron/nightly", headers=_auth_header())

        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data["signals"]["error"] == "signal boom"

    def test_velocity_v2_error_captured(self, cron_client):
        with _mock_nightly_subtasks() as mocks:
            mocks["velocity_v2"].side_effect = Exception("v2 boom")
            resp = cron_client.post("/cron/nightly", headers=_auth_header())

        data = json.loads(resp.data)
        assert resp.status_code == 200
        assert data["velocity_v2"]["error"] == "v2 boom"


class TestStuckJobThreshold:
    """Verify the stuck job threshold was tightened to 10 minutes."""

    def test_stuck_job_sql_uses_10_minutes(self):
        import inspect
        from web.routes_cron import cron_nightly
        source = inspect.getsource(cron_nightly)
        assert "INTERVAL '10 minutes'" in source
        assert "INTERVAL '15 minutes'" not in source
