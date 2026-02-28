"""Tests for QS4-B: Pool monitoring, /health/ready, Docker CI, demo polish."""

import json
import os
import yaml

import pytest

from web.app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


# ── B-1: Pool stats ──────────────────────────────────────────────

class TestPoolStats:
    def test_get_pool_stats_returns_dict(self):
        """get_pool_stats returns a dict with expected keys."""
        from src.db import get_pool_stats
        stats = get_pool_stats()
        assert isinstance(stats, dict)
        assert "backend" in stats

    def test_get_pool_stats_no_pool(self, monkeypatch):
        """get_pool_stats returns no_pool status when pool is None."""
        import src.db as db_mod
        original_pool = db_mod._pool
        monkeypatch.setattr(db_mod, "_pool", None)
        stats = db_mod.get_pool_stats()
        assert stats["status"] == "no_pool"
        assert stats["backend"] == db_mod.BACKEND
        monkeypatch.setattr(db_mod, "_pool", original_pool)

    def test_get_pool_stats_has_maxconn(self):
        """get_pool_stats includes maxconn when pool exists (Postgres) or no_pool (DuckDB)."""
        from src.db import get_pool_stats, BACKEND
        stats = get_pool_stats()
        if BACKEND == "postgres":
            assert "maxconn" in stats
        else:
            # DuckDB has no pool
            assert stats.get("status") == "no_pool"

    def test_db_pool_max_env_override(self, monkeypatch):
        """DB_POOL_MAX env var overrides default maxconn."""
        import src.db as db_mod
        if db_mod.BACKEND != "postgres":
            pytest.skip("Pool config only applies to Postgres")
        # Save original pool reference
        original_pool = db_mod._pool
        monkeypatch.setattr(db_mod, "_pool", None)
        monkeypatch.setenv("DB_POOL_MAX", "15")
        pool = db_mod._get_pool()
        assert pool.maxconn == 15
        pool.closeall()
        monkeypatch.setattr(db_mod, "_pool", original_pool)

    def test_default_maxconn_is_20(self):
        """Default maxconn is 20 (Railway limit: 100 / 5 workers = 20)."""
        import src.db as db_mod
        if db_mod.BACKEND != "postgres":
            pytest.skip("Pool config only applies to Postgres")
        if db_mod._pool is not None:
            assert db_mod._pool.maxconn == int(os.environ.get("DB_POOL_MAX", "20"))


# ── B-2: /health/ready ───────────────────────────────────────────

class TestHealthReady:
    def test_health_ready_returns_json(self, client):
        """/health/ready returns JSON with 'ready' and 'checks' keys."""
        rv = client.get("/health/ready")
        assert rv.status_code in (200, 503)
        data = json.loads(rv.data)
        assert "ready" in data
        assert "checks" in data

    def test_health_ready_checks_structure(self, client):
        """/health/ready checks include db_pool, tables, migrations."""
        rv = client.get("/health/ready")
        data = json.loads(rv.data)
        checks = data["checks"]
        assert "db_pool" in checks
        assert "tables" in checks
        assert "migrations" in checks

    def test_health_ready_db_pool_check(self, client):
        """/health/ready reports db_pool as True when connection succeeds."""
        rv = client.get("/health/ready")
        data = json.loads(rv.data)
        # On DuckDB (test env), pool check should pass since get_connection works
        assert data["checks"]["db_pool"] is True

    def test_health_ready_status_code_200_or_503(self, client):
        """/health/ready returns 200 when ready, 503 when not."""
        rv = client.get("/health/ready")
        data = json.loads(rv.data)
        if data["ready"]:
            assert rv.status_code == 200
        else:
            assert rv.status_code == 503

    def test_health_ready_missing_tables_returns_503(self, client, monkeypatch):
        """/health/ready returns 503 when expected tables are missing."""
        # Patch via the web.app module
        import web.app as app_mod
        monkeypatch.setattr(app_mod, "EXPECTED_TABLES", ["nonexistent_table_xyz_999"])
        rv = client.get("/health/ready")
        data = json.loads(rv.data)
        assert rv.status_code == 503
        assert data["ready"] is False
        assert "nonexistent_table_xyz_999" in data["checks"].get("missing_tables", [])


# ── B-3: Pool stats in /health ────────────────────────────────────

class TestHealthPoolStats:
    def test_health_includes_pool_key(self, client):
        """/health response includes 'pool' key."""
        rv = client.get("/health")
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert "pool" in data

    def test_health_pool_has_backend(self, client):
        """/health pool stats include backend information."""
        rv = client.get("/health")
        data = json.loads(rv.data)
        pool = data["pool"]
        assert "backend" in pool


# ── B-4: Docker CI ────────────────────────────────────────────────

class TestDockerCI:
    def test_docker_build_workflow_exists(self):
        """GitHub Actions workflow file exists."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github", "workflows", "docker-build.yml"
        )
        assert os.path.exists(workflow_path)

    def test_docker_build_workflow_valid_yaml(self):
        """GitHub Actions workflow is valid YAML."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github", "workflows", "docker-build.yml"
        )
        with open(workflow_path) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "jobs" in data
        assert "build" in data["jobs"]

    def test_docker_build_pushes_to_ghcr(self):
        """Workflow pushes images to ghcr.io."""
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github", "workflows", "docker-build.yml"
        )
        with open(workflow_path) as f:
            content = f.read()
        assert "ghcr.io" in content

    def test_dockerfile_exists(self):
        """Main Dockerfile exists."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "Dockerfile"
        )
        assert os.path.exists(dockerfile_path)

    def test_dockerfile_has_python_base(self):
        """Dockerfile uses Python base image."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "Dockerfile"
        )
        with open(dockerfile_path) as f:
            content = f.read()
        assert "python:" in content.lower()


# ── /health/schema regression ────────────────────────────────────

class TestHealthSchemaRegression:
    def test_health_schema_still_works(self, client):
        """/health/schema endpoint returns valid JSON (CC0 regression check)."""
        rv = client.get("/health/schema")
        assert rv.status_code in (200, 503)
        data = json.loads(rv.data)
        assert "status" in data
        assert "tables" in data


# ── B-5: Demo page ───────────────────────────────────────────────

class TestDemoPage:
    def test_demo_renders_200(self, client):
        """/demo returns 200."""
        rv = client.get("/demo")
        assert rv.status_code == 200

    def test_demo_contains_mcp_keyword(self, client):
        """/demo mentions MCP architecture."""
        rv = client.get("/demo")
        html = rv.data.decode()
        assert "MCP" in html

    def test_demo_contains_entity_resolution(self, client):
        """/demo mentions entity resolution."""
        rv = client.get("/demo")
        html = rv.data.decode()
        assert "entity" in html.lower() or "Entity" in html

    def test_demo_has_cta_with_invite_code(self, client):
        """/demo has a CTA linking to signup with friends-gridcare invite code."""
        rv = client.get("/demo")
        html = rv.data.decode()
        assert "friends-gridcare" in html
        assert "/auth/login" in html

    def test_demo_has_architecture_stats(self, client):
        """/demo shows architecture numbers (30 tools, 1M entities, etc)."""
        rv = client.get("/demo")
        html = rv.data.decode()
        # Check for the architecture showcase numbers
        assert "30" in html  # 30 MCP tools
        assert "576K" in html  # relationship edges

    def test_demo_has_try_it_cta(self, client):
        """/demo has 'Try it yourself' CTA text."""
        rv = client.get("/demo")
        html = rv.data.decode()
        assert "Try it yourself" in html
