"""Tests for Sprint 57.5B cron guard — route isolation between web and cron workers."""

import pytest


@pytest.fixture
def cron_worker_client(monkeypatch):
    """Flask test client with CRON_WORKER=true (cron worker mode)."""
    monkeypatch.setenv("CRON_WORKER", "true")
    import web.app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture
def web_worker_client(monkeypatch):
    """Flask test client with CRON_WORKER=false (web worker mode, default)."""
    monkeypatch.delenv("CRON_WORKER", raising=False)
    import web.app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Cron worker mode tests (CRON_WORKER=true)
# ---------------------------------------------------------------------------


class TestCronWorkerMode:
    """When CRON_WORKER=true, only /cron/* and /health are served."""

    def test_health_returns_200(self, cron_worker_client):
        """Cron worker must serve /health for Railway health checks."""
        resp = cron_worker_client.get("/health")
        assert resp.status_code == 200

    def test_cron_nightly_not_blocked(self, cron_worker_client):
        """Cron worker allows POST /cron/nightly (guard doesn't return 404).

        The endpoint itself will return 403 (auth failure) since we don't
        pass CRON_SECRET, but that proves the guard let it through.
        """
        resp = cron_worker_client.post("/cron/nightly")
        # 403 = auth check ran (guard allowed it), NOT 404
        assert resp.status_code != 404

    def test_cron_status_allowed(self, cron_worker_client):
        """Cron worker allows GET /cron/status."""
        resp = cron_worker_client.get("/cron/status")
        # Should get 200 or 500 (DB not available), but NOT 404 from guard
        assert resp.status_code != 404

    def test_homepage_returns_404(self, cron_worker_client):
        """Cron worker blocks all non-cron, non-health routes."""
        resp = cron_worker_client.get("/")
        assert resp.status_code == 404

    def test_ask_returns_404(self, cron_worker_client):
        """Cron worker blocks /ask (a web-only route)."""
        resp = cron_worker_client.get("/ask")
        assert resp.status_code == 404

    def test_admin_returns_404(self, cron_worker_client):
        """Cron worker blocks /admin routes."""
        resp = cron_worker_client.get("/admin")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Web worker mode tests (CRON_WORKER=false, default)
# ---------------------------------------------------------------------------


class TestWebWorkerMode:
    """When CRON_WORKER is unset/false, POST /cron/* is blocked, GET allowed."""

    def test_homepage_returns_200(self, web_worker_client):
        """Web worker serves the homepage."""
        resp = web_worker_client.get("/")
        assert resp.status_code == 200

    def test_health_returns_200(self, web_worker_client):
        """Web worker serves /health."""
        resp = web_worker_client.get("/health")
        assert resp.status_code == 200

    def test_cron_nightly_post_blocked(self, web_worker_client):
        """Web worker blocks POST /cron/nightly with 404."""
        resp = web_worker_client.post("/cron/nightly")
        assert resp.status_code == 404

    def test_cron_backup_post_blocked(self, web_worker_client):
        """Web worker blocks POST /cron/backup with 404."""
        resp = web_worker_client.post("/cron/backup")
        assert resp.status_code == 404

    def test_cron_status_get_allowed(self, web_worker_client):
        """Web worker allows GET /cron/status (read-only dashboard)."""
        resp = web_worker_client.get("/cron/status")
        # Should get 200 or 500 (DB not available), but NOT 404 from guard
        assert resp.status_code != 404

    def test_cron_pipeline_health_get_allowed(self, web_worker_client):
        """Web worker allows GET /cron/pipeline-health (not a POST)."""
        resp = web_worker_client.get("/cron/pipeline-health")
        # GET requests to /cron/* are allowed through (only POST is blocked)
        assert resp.status_code != 404
