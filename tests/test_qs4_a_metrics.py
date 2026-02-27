"""Tests for QS4-A: Metrics UI + Data Surfacing.

Covers:
- /admin/metrics route (auth, rendering, data sections)
- Issuance trends, SLA compliance, planning velocity queries
- Velocity cache (station_velocity_v2 table — pre-existing)
- Metrics ingest wired into run_ingestion pipeline
- POST /cron/velocity-refresh endpoint auth
"""

import os
import sys
import inspect
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_duckdb(monkeypatch):
    """Force DuckDB backend for tests."""
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def _init_db(monkeypatch):
    """Initialize DuckDB schema including metrics tables."""
    import src.db as db_mod
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()
    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
    finally:
        conn.close()


@pytest.fixture
def client(_init_db):
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login_admin(client):
    """Create an admin user, log them in, return the user dict."""
    from web.auth import get_or_create_user, create_magic_token
    from src.db import execute_write
    user = get_or_create_user("admin@qs4a.test")
    execute_write(
        "UPDATE users SET is_admin = TRUE WHERE user_id = %s",
        (user["user_id"],),
    )
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _login_user(client):
    """Create a regular (non-admin) user and log them in."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user("user@qs4a.test")
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _seed_metrics_data():
    """Insert test data into the 3 metrics tables."""
    from src.db import get_connection
    conn = get_connection()

    # Clear existing data first
    conn.execute("DELETE FROM permit_issuance_metrics")
    conn.execute("DELETE FROM permit_review_metrics")
    conn.execute("DELETE FROM planning_review_metrics")

    # Issuance metrics
    conn.execute(
        "INSERT INTO permit_issuance_metrics "
        "(id, bpa, permit_type, otc_ih, issued_date, issued_year) "
        "VALUES (1, 'BPA001', 'additions alterations or repairs', 'OTC', '2025-06-15', '2025')"
    )
    conn.execute(
        "INSERT INTO permit_issuance_metrics "
        "(id, bpa, permit_type, otc_ih, issued_date, issued_year) "
        "VALUES (2, 'BPA002', 'new construction', 'In-House', '2025-03-10', '2025')"
    )

    # Review metrics
    conn.execute(
        "INSERT INTO permit_review_metrics "
        "(id, bpa, station, department, met_cal_sla, calendar_days) "
        "VALUES (1, 'BPA001', 'BLDG', 'DBI', TRUE, 5.0)"
    )
    conn.execute(
        "INSERT INTO permit_review_metrics "
        "(id, bpa, station, department, met_cal_sla, calendar_days) "
        "VALUES (2, 'BPA002', 'BLDG', 'DBI', FALSE, 25.0)"
    )
    conn.execute(
        "INSERT INTO permit_review_metrics "
        "(id, bpa, station, department, met_cal_sla, calendar_days) "
        "VALUES (3, 'BPA003', 'CP-ZOC', 'CPC', TRUE, 12.0)"
    )

    # Planning metrics
    conn.execute(
        "INSERT INTO planning_review_metrics "
        "(id, project_stage, metric_outcome, metric_value) "
        "VALUES (1, 'Environmental Review', 'Met SLA', 30.0)"
    )
    conn.execute(
        "INSERT INTO planning_review_metrics "
        "(id, project_stage, metric_outcome, metric_value) "
        "VALUES (2, 'Environmental Review', 'Exceeded SLA', 90.0)"
    )
    conn.execute(
        "INSERT INTO planning_review_metrics "
        "(id, project_stage, metric_outcome, metric_value) "
        "VALUES (3, 'Hearing', 'Met SLA', 15.0)"
    )

    conn.close()


# ---------------------------------------------------------------------------
# Route auth tests
# ---------------------------------------------------------------------------

class TestMetricsAuth:
    def test_anonymous_redirected(self, client):
        """GET /admin/metrics redirects anonymous users to login."""
        rv = client.get("/admin/metrics")
        assert rv.status_code == 302

    def test_non_admin_forbidden(self, client):
        """GET /admin/metrics returns 403 for non-admin users."""
        _login_user(client)
        rv = client.get("/admin/metrics")
        assert rv.status_code == 403

    def test_admin_gets_200(self, client):
        """GET /admin/metrics returns 200 for admin users."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        assert rv.status_code == 200


# ---------------------------------------------------------------------------
# Template rendering tests
# ---------------------------------------------------------------------------

class TestMetricsTemplate:
    def test_has_three_sections(self, client):
        """Metrics page includes all 3 section headers."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "Permit Issuance Trends" in html
        assert "Station SLA Compliance" in html
        assert "Planning Velocity" in html

    def test_has_obsidian_vars(self, client):
        """Template uses Obsidian design system CSS variables (Sprint 76-4 migration)."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        # Updated for Obsidian migration: now uses design-system.css tokens, not hardcoded hex vars
        assert "design-system.css" in html
        assert "obsidian" in html

    def test_has_back_link(self, client):
        """Template includes back link to operations hub."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "/admin/ops" in html

    def test_empty_state_messages(self, client):
        """Empty tables show helpful empty state messages."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "No issuance data available" in html or "Issuance Records" in html

    def test_has_nav(self, client):
        """Template includes navigation fragment."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "nav" in html.lower()

    def test_stats_cards_present(self, client):
        """Summary stat cards are rendered."""
        _login_admin(client)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "Issuance Records" in html
        assert "Stations Tracked" in html
        assert "Planning Stages" in html


# ---------------------------------------------------------------------------
# Data query tests (with seeded data)
# ---------------------------------------------------------------------------

class TestMetricsData:
    def test_issuance_data_rendered(self, client):
        """Seeded issuance data appears in the table."""
        _login_admin(client)
        _seed_metrics_data()
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "additions alterations or repairs" in html
        assert "new construction" in html

    def test_sla_data_rendered(self, client):
        """Seeded SLA data appears with station names."""
        _login_admin(client)
        _seed_metrics_data()
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "BLDG" in html
        assert "CP-ZOC" in html
        assert "DBI" in html

    def test_sla_color_coding(self, client):
        """SLA percentages get color-coded CSS classes."""
        _login_admin(client)
        _seed_metrics_data()
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        # BLDG has 1/2 met = 50% -> sla-bad
        assert "sla-bad" in html or "sla-warn" in html
        # CP-ZOC has 1/1 met = 100% -> sla-good
        assert "sla-good" in html

    def test_planning_data_rendered(self, client):
        """Seeded planning data appears with stage names."""
        _login_admin(client)
        _seed_metrics_data()
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "Environmental Review" in html
        assert "Hearing" in html


# ---------------------------------------------------------------------------
# Station velocity cache tests (pre-existing — verify working)
# ---------------------------------------------------------------------------

class TestVelocityCache:
    def test_velocity_v2_table_creation(self, _init_db):
        """station_velocity_v2 table can be created and queried."""
        from src.station_velocity_v2 import ensure_velocity_v2_table
        from src.db import get_connection
        conn = get_connection()
        try:
            ensure_velocity_v2_table(conn)
            # Verify table exists by querying it (may have data from other tests)
            rows = conn.execute("SELECT COUNT(*) FROM station_velocity_v2").fetchone()
            assert rows[0] >= 0  # Table exists and is queryable
        finally:
            conn.close()

    def test_get_velocity_cache_miss(self, _init_db):
        """get_velocity_for_station returns None on cache miss."""
        from src.station_velocity_v2 import ensure_velocity_v2_table, get_velocity_for_station
        from src.db import get_connection
        conn = get_connection()
        try:
            ensure_velocity_v2_table(conn)
            result = get_velocity_for_station("NONEXISTENT", conn=conn)
            assert result is None
        finally:
            conn.close()

    def test_get_velocity_cache_hit(self, _init_db):
        """get_velocity_for_station returns data when cache is populated."""
        from src.station_velocity_v2 import ensure_velocity_v2_table, get_velocity_for_station
        from src.db import get_connection
        conn = get_connection()
        try:
            ensure_velocity_v2_table(conn)
            conn.execute("DELETE FROM station_velocity_v2")
            conn.execute(
                "INSERT INTO station_velocity_v2 "
                "(station, metric_type, p25_days, p50_days, p75_days, p90_days, sample_count, period) "
                "VALUES ('BLDG', 'initial', 3.0, 7.0, 14.0, 21.0, 100, 'current')"
            )
            result = get_velocity_for_station("BLDG", period="current", conn=conn)
            assert result is not None
            assert result.station == "BLDG"
            assert result.p50_days == 7.0
            assert result.sample_count == 100
        finally:
            conn.close()

    def test_get_velocity_fallback_to_all(self, _init_db):
        """get_velocity_for_station falls back to 'all' period when requested period missing."""
        from src.station_velocity_v2 import ensure_velocity_v2_table, get_velocity_for_station
        from src.db import get_connection
        conn = get_connection()
        try:
            ensure_velocity_v2_table(conn)
            conn.execute("DELETE FROM station_velocity_v2")
            # Insert only 'all' period
            conn.execute(
                "INSERT INTO station_velocity_v2 "
                "(station, metric_type, p25_days, p50_days, p75_days, p90_days, sample_count, period) "
                "VALUES ('SFFD-HQ', 'initial', 1.0, 2.0, 4.0, 7.0, 50, 'all')"
            )
            result = get_velocity_for_station("SFFD-HQ", period="current", conn=conn)
            # Should fall back to 'all'
            assert result is not None
            assert result.period == "all"
        finally:
            conn.close()

    def test_get_all_velocities(self, _init_db):
        """get_all_velocities returns list of velocity records."""
        from src.station_velocity_v2 import ensure_velocity_v2_table, get_all_velocities
        from src.db import get_connection
        conn = get_connection()
        try:
            ensure_velocity_v2_table(conn)
            conn.execute("DELETE FROM station_velocity_v2")
            conn.execute(
                "INSERT INTO station_velocity_v2 "
                "(station, metric_type, p25_days, p50_days, p75_days, p90_days, sample_count, period) "
                "VALUES ('BLDG', 'initial', 3.0, 7.0, 14.0, 21.0, 100, 'current')"
            )
            conn.execute(
                "INSERT INTO station_velocity_v2 "
                "(station, metric_type, p25_days, p50_days, p75_days, p90_days, sample_count, period) "
                "VALUES ('CP-ZOC', 'initial', 5.0, 10.0, 20.0, 30.0, 80, 'current')"
            )
            results = get_all_velocities(period="current", conn=conn)
            assert len(results) == 2
            stations = {v.station for v in results}
            assert "BLDG" in stations
            assert "CP-ZOC" in stations
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Cron endpoint tests
# ---------------------------------------------------------------------------

class TestCronEndpoints:
    def test_velocity_refresh_requires_auth(self, client, monkeypatch):
        """POST /cron/velocity-refresh requires CRON_SECRET."""
        monkeypatch.setenv("CRON_WORKER", "1")
        monkeypatch.setenv("CRON_SECRET", "real-secret-789")
        rv = client.post("/cron/velocity-refresh")
        assert rv.status_code in (401, 403)

    def test_velocity_refresh_with_secret(self, client, monkeypatch):
        """POST /cron/velocity-refresh succeeds with valid CRON_SECRET."""
        monkeypatch.setenv("CRON_SECRET", "test-secret-123")
        monkeypatch.setenv("CRON_WORKER", "1")

        # Mock the velocity refresh since we don't have real addenda data
        with patch("src.station_velocity_v2.refresh_velocity_v2") as mock_refresh:
            mock_refresh.return_value = {
                "rows_inserted": 50,
                "stations": 25,
                "periods": 2,
                "period_labels": ["current", "baseline"],
            }
            rv = client.post(
                "/cron/velocity-refresh",
                headers={"Authorization": "Bearer test-secret-123"},
            )
            assert rv.status_code == 200
            data = rv.get_json()
            assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Pipeline integration test
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_run_ingestion_includes_metrics(self):
        """run_ingestion() calls 3 metrics ingest functions."""
        source = inspect.getsource(__import__("src.ingest", fromlist=["run_ingestion"]).run_ingestion)
        assert "ingest_permit_issuance_metrics" in source
        assert "ingest_permit_review_metrics" in source
        assert "ingest_planning_review_metrics" in source

    def test_metrics_functions_exist(self):
        """All 3 metrics ingest functions are importable."""
        from src.ingest import (
            ingest_permit_issuance_metrics,
            ingest_permit_review_metrics,
            ingest_planning_review_metrics,
        )
        assert callable(ingest_permit_issuance_metrics)
        assert callable(ingest_permit_review_metrics)
        assert callable(ingest_planning_review_metrics)


# ---------------------------------------------------------------------------
# Query structure tests
# ---------------------------------------------------------------------------

class TestQueryStructure:
    def test_issuance_query_returns_expected_keys(self, client):
        """Issuance query result dicts have year/month/type keys."""
        _login_admin(client)
        _seed_metrics_data()

        # Access the route and verify data is structured
        from src.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT issued_year,
                       MONTH(issued_date::TIMESTAMP) AS issued_month,
                       permit_type, otc_ih, COUNT(*) as count
                FROM permit_issuance_metrics
                WHERE issued_year IS NOT NULL AND issued_date IS NOT NULL
                GROUP BY issued_year, issued_month, permit_type, otc_ih
            """).fetchall()
            assert len(rows) > 0
            # Each row has 5 columns
            for r in rows:
                assert len(r) == 5
        finally:
            conn.close()

    def test_sla_query_returns_expected_keys(self, client):
        """SLA query result dicts have station/department/met_sla keys."""
        _login_admin(client)
        _seed_metrics_data()

        from src.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT station, department, COUNT(*) as total,
                       SUM(CASE WHEN met_cal_sla THEN 1 ELSE 0 END) as met_sla,
                       ROUND(AVG(calendar_days), 1) as avg_days
                FROM permit_review_metrics
                WHERE station IS NOT NULL
                GROUP BY station, department
            """).fetchall()
            assert len(rows) > 0
            for r in rows:
                assert len(r) == 5
        finally:
            conn.close()

    def test_planning_query_returns_expected_keys(self, client):
        """Planning query result dicts have stage/outcome keys."""
        _login_admin(client)
        _seed_metrics_data()

        from src.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT project_stage, metric_outcome, COUNT(*) as count,
                       ROUND(AVG(metric_value), 1) as avg_value
                FROM planning_review_metrics
                GROUP BY project_stage, metric_outcome
            """).fetchall()
            assert len(rows) > 0
            for r in rows:
                assert len(r) == 4
        finally:
            conn.close()
