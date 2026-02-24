"""Tests for /cron/pipeline-health and /admin/pipeline routes — Sprint 53 Session C.

Uses Flask test_client() with proper auth simulation.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _make_admin_client(client):
    """Log in as an admin user via magic token."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    from src.db import execute_write, BACKEND

    user = get_or_create_user("pipeline_admin_test@sfpermits.ai")
    user_id = user["user_id"]

    # Make admin
    ph = "%s" if BACKEND == "postgres" else "?"
    execute_write(
        f"UPDATE users SET is_admin = TRUE WHERE user_id = {ph}",
        (user_id,),
    )

    token = create_magic_token(user_id)
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user_id


def _make_nonadmin_client(client):
    """Log in as a non-admin user."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token

    user = get_or_create_user("pipeline_user_test@sfpermits.ai")
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user["user_id"]


# ── GET /cron/pipeline-health ─────────────────────────────────────


def test_pipeline_health_get_ok(client):
    """GET /cron/pipeline-health returns health JSON."""
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="ok",
        checks=[HealthCheck("cron_nightly", "ok", "12.0h ago")],
        summary_line="All pipeline checks passed",
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/cron/pipeline-health")

    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert "health" in data
    assert data["health"]["overall_status"] == "ok"


def test_pipeline_health_get_returns_checks(client):
    """GET /cron/pipeline-health includes checks list."""
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="warn",
        checks=[
            HealthCheck("cron_nightly", "warn", "26h ago"),
            HealthCheck("data_freshness", "ok", "Fresh"),
        ],
        summary_line="1 issue",
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/cron/pipeline-health")

    data = json.loads(resp.data)
    assert len(data["health"]["checks"]) == 2
    assert data["health"]["checks"][0]["name"] == "cron_nightly"


def test_pipeline_health_get_handles_error(client):
    """GET /cron/pipeline-health returns error JSON on failure."""
    with patch("web.pipeline_health.get_pipeline_health", side_effect=Exception("DB error")):
        resp = client.get("/cron/pipeline-health")

    assert resp.status_code == 500
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert "error" in data


def test_pipeline_health_summary_line_in_response(client):
    """GET /cron/pipeline-health returns summary_line."""
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="ok",
        checks=[],
        summary_line="All clear",
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/cron/pipeline-health")

    data = json.loads(resp.data)
    assert data["health"]["summary_line"] == "All clear"


# ── POST /cron/pipeline-health?action=run_nightly ────────────────


def test_pipeline_health_post_requires_auth(client):
    """POST without auth returns 403."""
    with patch.dict("os.environ", {"CRON_SECRET": "test-secret"}):
        resp = client.post("/cron/pipeline-health")
    assert resp.status_code == 403


def test_pipeline_health_post_wrong_token(client):
    """POST with wrong token returns 403."""
    with patch.dict("os.environ", {"CRON_SECRET": "correct-secret"}):
        resp = client.post(
            "/cron/pipeline-health?action=run_nightly",
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert resp.status_code == 403


def test_pipeline_health_post_unknown_action(client):
    """POST with unknown action returns 400."""
    with patch.dict("os.environ", {"CRON_SECRET": "test-secret"}):
        resp = client.post(
            "/cron/pipeline-health?action=unknown_thing",
            headers={"Authorization": "Bearer test-secret"},
        )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert data["ok"] is False


# ── GET /admin/pipeline ───────────────────────────────────────────


def test_admin_pipeline_requires_login(client):
    """GET /admin/pipeline redirects unauthenticated users."""
    resp = client.get("/admin/pipeline")
    assert resp.status_code in (302, 401, 403)


def test_admin_pipeline_nonadmin_gets_403(client):
    """Non-admin user gets 403 from /admin/pipeline."""
    _make_nonadmin_client(client)
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="ok",
        checks=[],
        summary_line="ok",
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/admin/pipeline")
    assert resp.status_code == 403


def test_admin_pipeline_admin_gets_page(client):
    """Admin user gets the pipeline dashboard page (200)."""
    _make_admin_client(client)
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="ok",
        checks=[HealthCheck("cron_nightly", "ok", "12h ago")],
        summary_line="All good",
        cron_history=[],
        data_freshness={},
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/admin/pipeline")

    assert resp.status_code == 200
    assert b"Pipeline Health" in resp.data


def test_admin_pipeline_shows_status(client):
    """Pipeline page shows the overall status."""
    _make_admin_client(client)
    from web.pipeline_health import PipelineHealthReport, HealthCheck
    mock_report = PipelineHealthReport(
        run_at="2026-02-24T08:00:00Z",
        overall_status="critical",
        checks=[HealthCheck("cron_nightly", "critical", "72h ago")],
        summary_line="Pipeline critical",
        cron_history=[],
        data_freshness={},
    )
    with patch("web.pipeline_health.get_pipeline_health", return_value=mock_report):
        resp = client.get("/admin/pipeline")

    assert resp.status_code == 200
    assert b"CRITICAL" in resp.data or b"critical" in resp.data
