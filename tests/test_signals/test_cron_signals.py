"""Tests for the /cron/signals endpoint in web.app."""

import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Flask test client with CRON_SECRET configured."""
    with patch.dict("os.environ", {"CRON_SECRET": "test-secret"}):
        from web.app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c


class TestCronSignals:
    def test_blocked_on_web_worker(self, client):
        resp = client.post("/cron/signals")
        assert resp.status_code == 404  # Cron guard blocks POST /cron/* on web workers

    def test_returns_200_with_auth(self, client, monkeypatch):
        monkeypatch.setenv("CRON_WORKER", "true")
        mock_conn = MagicMock()
        mock_stats = {
            "total_signals": 42,
            "permit_signals": 30,
            "property_signals": 35,
            "properties": 10,
            "tier_distribution": {"at_risk": 5, "on_track": 5},
            "detectors": {},
        }
        with patch("src.signals.pipeline.run_signal_pipeline", return_value=mock_stats):
            with patch("src.db.get_connection", return_value=mock_conn):
                resp = client.post(
                    "/cron/signals",
                    headers={"Authorization": "Bearer test-secret"},
                )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"
        assert data["total_signals"] == 42

    def test_returns_500_on_error(self, client, monkeypatch):
        monkeypatch.setenv("CRON_WORKER", "true")
        with patch("src.db.get_connection", side_effect=Exception("db error")):
            resp = client.post(
                "/cron/signals",
                headers={"Authorization": "Bearer test-secret"},
            )
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert data["status"] == "error"
