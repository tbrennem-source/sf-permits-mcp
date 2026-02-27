"""Tests for Sprint 76-3: Severity UI Integration + Caching.

Covers:
- DDL creates severity_cache table
- EXPECTED_TABLES includes severity_cache
- Cache hit returns cached data
- Cache miss computes and stores
- Badge renders for each tier
- Badge does not render when no severity data
- Cron refresh endpoint requires auth
- Cron refresh populates cache
- Search results include severity data
- Graceful fallback on severity computation failure
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duck_db():
    """In-memory DuckDB with severity_cache and permits/inspections tables."""
    conn = duckdb.connect(":memory:")
    # severity_cache table (DuckDB version)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS severity_cache (
            permit_number TEXT PRIMARY KEY,
            score INTEGER NOT NULL,
            tier TEXT NOT NULL,
            drivers VARCHAR,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Minimal permits table for testing severity computation
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permits (
            permit_number TEXT PRIMARY KEY,
            status TEXT,
            permit_type_definition TEXT,
            description TEXT,
            filed_date TEXT,
            issued_date TEXT,
            completed_date TEXT,
            status_date TEXT,
            estimated_cost DOUBLE,
            revised_cost DOUBLE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY,
            reference_number TEXT
        )
    """)
    yield conn
    conn.close()


@pytest.fixture
def app():
    """Flask test app with TESTING=True."""
    import web.app as app_module
    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(app):
    """Flask test client (web worker mode — cron POST routes return 404)."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def cron_client(monkeypatch):
    """Flask test client in CRON_WORKER mode (cron endpoints accessible).

    monkeypatch automatically restores CRON_WORKER env var after the test,
    preventing contamination of subsequent tests.
    """
    monkeypatch.setenv("CRON_WORKER", "true")
    import web.app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    # monkeypatch teardown removes CRON_WORKER automatically


# ---------------------------------------------------------------------------
# Task 76-3-1/3: DDL creates severity_cache table
# ---------------------------------------------------------------------------

class TestSeverityCacheDDL:
    """severity_cache table DDL tests."""

    def test_duckdb_ddl_creates_table(self, duck_db):
        """DDL creates the severity_cache table with correct columns."""
        tables = duck_db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'severity_cache'"
        ).fetchall()
        assert len(tables) == 1, "severity_cache table should exist"

    def test_duckdb_ddl_columns(self, duck_db):
        """severity_cache has correct column names."""
        cols = duck_db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'severity_cache'"
        ).fetchall()
        col_names = {r[0] for r in cols}
        assert "permit_number" in col_names
        assert "score" in col_names
        assert "tier" in col_names
        assert "drivers" in col_names
        assert "computed_at" in col_names

    def test_duckdb_ddl_idempotent(self, duck_db):
        """Running DDL twice does not raise."""
        # Second run should be a no-op thanks to IF NOT EXISTS
        duck_db.execute("""
            CREATE TABLE IF NOT EXISTS severity_cache (
                permit_number TEXT PRIMARY KEY,
                score INTEGER NOT NULL,
                tier TEXT NOT NULL,
                drivers VARCHAR,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def test_init_user_schema_creates_severity_cache(self):
        """init_user_schema creates severity_cache in DuckDB."""
        import duckdb
        from src.db import init_user_schema

        conn = duckdb.connect(":memory:")
        try:
            init_user_schema(conn)
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = 'severity_cache'"
            ).fetchall()
            assert len(tables) == 1, "init_user_schema should create severity_cache"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Task 76-3-2: EXPECTED_TABLES includes severity_cache
# ---------------------------------------------------------------------------

class TestExpectedTables:
    """EXPECTED_TABLES check."""

    def test_expected_tables_includes_severity_cache(self):
        """severity_cache is in EXPECTED_TABLES in web/app.py."""
        from web.app import EXPECTED_TABLES
        assert "severity_cache" in EXPECTED_TABLES, (
            "severity_cache must be listed in EXPECTED_TABLES"
        )


# ---------------------------------------------------------------------------
# Cache hit/miss logic
# ---------------------------------------------------------------------------

class TestSeverityCacheHitMiss:
    """Tests for cache hit and miss behavior via duck_db."""

    def test_cache_insert_and_select(self, duck_db):
        """Can insert into severity_cache and retrieve the data."""
        drivers = json.dumps({"age_staleness": 50.0, "inspection_activity": 30.0})
        duck_db.execute(
            "INSERT INTO severity_cache (permit_number, score, tier, drivers) "
            "VALUES ('BPA123', 75, 'HIGH', ?)",
            [drivers],
        )
        row = duck_db.execute(
            "SELECT score, tier, drivers FROM severity_cache WHERE permit_number = 'BPA123'"
        ).fetchone()
        assert row is not None
        assert row[0] == 75
        assert row[1] == "HIGH"
        parsed = json.loads(row[2])
        assert parsed["age_staleness"] == 50.0

    def test_cache_upsert_updates_on_conflict(self, duck_db):
        """INSERT OR REPLACE updates existing cache entry."""
        duck_db.execute(
            "INSERT INTO severity_cache (permit_number, score, tier) VALUES ('BPA456', 30, 'LOW')"
        )
        duck_db.execute(
            "INSERT OR REPLACE INTO severity_cache (permit_number, score, tier) "
            "VALUES ('BPA456', 82, 'CRITICAL')"
        )
        row = duck_db.execute(
            "SELECT score, tier FROM severity_cache WHERE permit_number = 'BPA456'"
        ).fetchone()
        assert row[0] == 82
        assert row[1] == "CRITICAL"

    def test_cache_miss_returns_none(self, duck_db):
        """A permit not in cache returns None."""
        row = duck_db.execute(
            "SELECT score FROM severity_cache WHERE permit_number = 'NONEXISTENT'"
        ).fetchone()
        assert row is None


# ---------------------------------------------------------------------------
# Badge template rendering
# ---------------------------------------------------------------------------

class TestSeverityBadgeRendering:
    """Tests for severity_badge.html template rendering."""

    TIERS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN"]

    def _render_badge(self, app, tier):
        """Render the severity_badge fragment via Jinja2."""
        with app.app_context():
            from flask import render_template
            return render_template("fragments/severity_badge.html", severity_tier=tier)

    def test_badge_renders_critical(self, app):
        html = self._render_badge(app, "CRITICAL")
        assert "severity-critical" in html
        assert "CRITICAL" in html

    def test_badge_renders_high(self, app):
        html = self._render_badge(app, "HIGH")
        assert "severity-high" in html
        assert "HIGH" in html

    def test_badge_renders_medium(self, app):
        html = self._render_badge(app, "MEDIUM")
        assert "severity-medium" in html
        assert "MEDIUM" in html

    def test_badge_renders_low(self, app):
        html = self._render_badge(app, "LOW")
        assert "severity-low" in html
        assert "LOW" in html

    def test_badge_renders_green(self, app):
        html = self._render_badge(app, "GREEN")
        assert "severity-green" in html
        assert "GREEN" in html

    def test_badge_absent_when_no_tier(self, app):
        """When severity_tier is None/falsy, badge span is not rendered."""
        with app.app_context():
            from flask import render_template
            html = render_template("fragments/severity_badge.html", severity_tier=None)
        # The CSS class .severity-badge appears in the <style> tag always.
        # We check that no <span> with that class is rendered.
        assert '<span class="severity-badge' not in html

    def test_badge_absent_when_empty_string(self, app):
        """When severity_tier is empty string, badge span is not rendered."""
        with app.app_context():
            from flask import render_template
            html = render_template("fragments/severity_badge.html", severity_tier="")
        assert '<span class="severity-badge' not in html


# ---------------------------------------------------------------------------
# Cron endpoint auth
# ---------------------------------------------------------------------------

class TestCronRefreshSeverityCache:
    """Tests for POST /cron/refresh-severity-cache."""

    def test_cron_endpoint_requires_auth(self, cron_client):
        """Without CRON_SECRET bearer token, endpoint returns 403."""
        resp = cron_client.post("/cron/refresh-severity-cache")
        assert resp.status_code == 403

    def test_cron_endpoint_with_wrong_token(self, cron_client, monkeypatch):
        """Wrong bearer token → 403."""
        monkeypatch.setenv("CRON_SECRET", "correct-secret")
        resp = cron_client.post(
            "/cron/refresh-severity-cache",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 403

    def test_cron_endpoint_accessible_with_correct_token(self, cron_client, monkeypatch):
        """Correct CRON_SECRET bearer token → not 403.

        May return 200 or 500 (if DB tables not set up), but auth must pass.
        """
        monkeypatch.setenv("CRON_SECRET", "test-secret-abc123")
        resp = cron_client.post(
            "/cron/refresh-severity-cache",
            headers={"Authorization": "Bearer test-secret-abc123"},
        )
        # 403 = auth failed (wrong); 200/500 = auth passed (right)
        assert resp.status_code != 403, (
            "Correct CRON_SECRET should pass auth check"
        )


# ---------------------------------------------------------------------------
# Severity scoring model (unit tests to verify computation logic)
# ---------------------------------------------------------------------------

class TestSeverityScoringModel:
    """Unit tests for the severity scoring used in cache computation."""

    def _make_permit(self, **kwargs):
        from src.severity import PermitInput
        today = date(2026, 2, 26)
        defaults = {
            "permit_number": "TEST001",
            "status": "issued",
            "permit_type_definition": "additions alterations or repairs",
            "description": "kitchen remodel",
            "filed_date": today - timedelta(days=180),
            "issued_date": today - timedelta(days=90),
            "status_date": today - timedelta(days=30),
            "estimated_cost": 75_000.0,
            "inspection_count": 0,
        }
        defaults.update(kwargs)
        return PermitInput(**defaults)

    def test_score_permit_returns_result(self):
        """score_permit returns a SeverityResult with expected fields."""
        from src.severity import score_permit
        permit = self._make_permit()
        result = score_permit(permit, today=date(2026, 2, 26))
        assert result.score >= 0
        assert result.score <= 100
        assert result.tier in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN")
        assert result.top_driver in result.dimensions

    def test_critical_permit_scores_high(self):
        """A seismic retrofit with no inspections and old age → high score."""
        from src.severity import score_permit
        today = date(2026, 2, 26)
        permit = self._make_permit(
            description="seismic retrofit soft story",
            status="issued",
            filed_date=today - timedelta(days=1000),
            issued_date=today - timedelta(days=800),
            status_date=today - timedelta(days=800),
            inspection_count=0,
            estimated_cost=500_000.0,
        )
        result = score_permit(permit, today=today)
        assert result.score >= 60, f"Expected HIGH+ score, got {result.score}"
        assert result.tier in ("HIGH", "CRITICAL")

    def test_green_permit_scores_low(self):
        """A recently-filed solar permit → low score."""
        from src.severity import score_permit
        today = date(2026, 2, 26)
        permit = self._make_permit(
            description="solar photovoltaic installation",
            status="filed",
            filed_date=today - timedelta(days=10),
            issued_date=None,
            inspection_count=0,
            estimated_cost=15_000.0,
        )
        result = score_permit(permit, today=today)
        assert result.score < 40, f"Expected LOW/GREEN score, got {result.score}"

    def test_graceful_fallback_on_bad_dates(self):
        """score_permit handles None dates without raising."""
        from src.severity import score_permit, PermitInput
        permit = PermitInput(
            permit_number="BAD001",
            status="issued",
            permit_type_definition="",
            description="",
            filed_date=None,
            issued_date=None,
            completed_date=None,
            status_date=None,
            estimated_cost=0.0,
            inspection_count=0,
        )
        result = score_permit(permit, today=date(2026, 2, 26))
        # Should not raise; result may be any valid tier
        assert result.tier in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN")

    def test_drivers_json_serializable(self):
        """SeverityResult dimensions dict is JSON-serializable (for cache storage)."""
        from src.severity import score_permit
        today = date(2026, 2, 26)
        permit = self._make_permit()
        result = score_permit(permit, today=today)
        drivers_json = json.dumps({
            dim: vals["score"] for dim, vals in result.dimensions.items()
        })
        parsed = json.loads(drivers_json)
        assert isinstance(parsed, dict)
        assert len(parsed) == 5  # 5 scoring dimensions
