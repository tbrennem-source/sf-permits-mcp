"""Tests for QS5-A: Materialized parcels table (parcel_summary).

Covers: DDL creation, cron endpoint auth, column schema, canonical_address
UPPER-casing, report.py integration with cache and SODA fallback.
"""

import os
import pytest

# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    """Create a Flask test app with DuckDB backend."""
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CRON_WORKER", "1")
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_conn():
    """Provide a DuckDB connection with full schema initialized."""
    from src.db import get_connection, init_schema, init_user_schema
    conn = get_connection()
    init_schema(conn)
    init_user_schema(conn)
    yield conn
    conn.close()


# ── Task A-1/A-2: DDL tests ──────────────────────────────────────

class TestParcelSummaryDDL:
    """Verify parcel_summary table creation."""

    def test_table_created_in_duckdb(self, db_conn):
        """parcel_summary table exists after init_user_schema."""
        result = db_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'parcel_summary'"
        ).fetchone()
        assert result[0] == 1, "parcel_summary table should exist"

    def test_correct_columns(self, db_conn):
        """parcel_summary has all expected columns."""
        result = db_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'parcel_summary' "
            "ORDER BY ordinal_position"
        ).fetchall()
        columns = [r[0] for r in result]
        expected = [
            "block", "lot", "canonical_address", "neighborhood",
            "supervisor_district", "permit_count", "open_permit_count",
            "complaint_count", "violation_count", "boiler_permit_count",
            "inspection_count", "tax_value", "zoning_code", "use_definition",
            "number_of_units", "health_tier", "last_permit_date", "refreshed_at",
        ]
        for col in expected:
            assert col in columns, f"Missing column: {col}"

    def test_primary_key_block_lot(self, db_conn):
        """block + lot form the primary key — no duplicates allowed."""
        db_conn.execute("DELETE FROM parcel_summary WHERE block = '1234' AND lot = '001'")
        db_conn.execute(
            "INSERT INTO parcel_summary (block, lot) VALUES ('1234', '001')"
        )
        with pytest.raises(Exception):
            db_conn.execute(
                "INSERT INTO parcel_summary (block, lot) VALUES ('1234', '001')"
            )
        # cleanup
        db_conn.execute("DELETE FROM parcel_summary WHERE block = '1234' AND lot = '001'")

    def test_expected_tables_includes_parcel_summary(self):
        """EXPECTED_TABLES in web/app.py includes parcel_summary."""
        from web.app import EXPECTED_TABLES
        assert "parcel_summary" in EXPECTED_TABLES


# ── Task A-3: Cron endpoint tests ────────────────────────────────

class TestCronRefreshParcelSummary:
    """Verify POST /cron/refresh-parcel-summary."""

    def test_requires_auth(self, client):
        """Endpoint rejects requests without CRON_SECRET."""
        resp = client.post("/cron/refresh-parcel-summary")
        assert resp.status_code == 403

    def test_requires_correct_secret(self, client):
        """Endpoint rejects wrong CRON_SECRET."""
        resp = client.post(
            "/cron/refresh-parcel-summary",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 403

    def test_returns_count(self, client, db_conn):
        """Endpoint returns parcel count on success."""
        # Seed minimal permit data for the refresh to process
        db_conn.execute(
            "INSERT OR IGNORE INTO permits (permit_number, block, lot, status, "
            "street_number, street_name, filed_date, neighborhood) "
            "VALUES ('TEST001', '9999', '001', 'issued', '123', 'TEST ST', "
            "'2024-01-15', 'Mission')"
        )

        secret = os.environ.get("CRON_SECRET", "test-secret")
        os.environ["CRON_SECRET"] = secret
        resp = client.post(
            "/cron/refresh-parcel-summary",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "parcels_refreshed" in data
        assert data["parcels_refreshed"] >= 1

        # Verify the row was actually created
        row = db_conn.execute(
            "SELECT canonical_address FROM parcel_summary "
            "WHERE block = '9999' AND lot = '001'"
        ).fetchone()
        assert row is not None

    def test_canonical_address_uppercased(self, client, db_conn):
        """canonical_address is UPPER-cased."""
        db_conn.execute(
            "INSERT OR IGNORE INTO permits (permit_number, block, lot, status, "
            "street_number, street_name, filed_date) "
            "VALUES ('TEST002', '8888', '002', 'filed', '456', 'Oak Street', '2024-06-01')"
        )

        secret = os.environ.get("CRON_SECRET", "test-secret")
        os.environ["CRON_SECRET"] = secret
        resp = client.post(
            "/cron/refresh-parcel-summary",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert resp.status_code == 200

        row = db_conn.execute(
            "SELECT canonical_address FROM parcel_summary "
            "WHERE block = '8888' AND lot = '002'"
        ).fetchone()
        assert row is not None
        addr = row[0]
        assert addr is not None
        assert addr == addr.upper(), f"Address should be UPPER: {addr}"

    def test_counts_populated(self, client, db_conn):
        """Permit counts are correctly computed."""
        # Insert multiple permits for the same parcel
        for i in range(3):
            status = ["filed", "complete", "issued"][i]
            db_conn.execute(
                "INSERT OR IGNORE INTO permits (permit_number, block, lot, status, "
                "street_number, street_name, filed_date) "
                f"VALUES ('CNT{i:03d}', '7777', '003', '{status}', '789', 'Count St', '2024-0{i+1}-01')"
            )

        secret = os.environ.get("CRON_SECRET", "test-secret")
        os.environ["CRON_SECRET"] = secret
        client.post(
            "/cron/refresh-parcel-summary",
            headers={"Authorization": f"Bearer {secret}"},
        )

        row = db_conn.execute(
            "SELECT permit_count, open_permit_count FROM parcel_summary "
            "WHERE block = '7777' AND lot = '003'"
        ).fetchone()
        assert row is not None
        assert row[0] == 3, f"Expected 3 total permits, got {row[0]}"
        # 'filed' and 'issued' are open statuses
        assert row[1] == 2, f"Expected 2 open permits, got {row[1]}"


# ── Task A-4: report.py integration tests ────────────────────────

class TestReportParcelSummaryIntegration:
    """Verify report.py uses parcel_summary when available."""

    def test_get_parcel_summary_returns_cache(self, db_conn):
        """_get_parcel_summary returns cached data when row exists."""
        db_conn.execute(
            "INSERT OR REPLACE INTO parcel_summary "
            "(block, lot, canonical_address, neighborhood, tax_value, "
            "zoning_code, use_definition, number_of_units) "
            "VALUES ('5555', '010', '100 MAIN ST', 'SoMa', 750000.0, "
            "'C-3-O', 'Office', 4)"
        )

        from web.report import _get_parcel_summary
        result = _get_parcel_summary("5555", "010")
        assert result is not None
        assert result["canonical_address"] == "100 MAIN ST"
        assert result["tax_value"] == 750000.0
        assert result["zoning_code"] == "C-3-O"
        assert result["use_definition"] == "Office"

    def test_get_parcel_summary_returns_none_when_missing(self, db_conn):
        """_get_parcel_summary returns None when no row exists."""
        from web.report import _get_parcel_summary
        result = _get_parcel_summary("0000", "999")
        assert result is None

    def test_format_property_profile_from_cache(self):
        """_format_property_profile_from_cache produces correct structure."""
        from web.report import _format_property_profile_from_cache
        cache = {
            "tax_value": 500000.0,
            "zoning_code": "RH-2",
            "use_definition": "Residential",
            "neighborhood_code_definition": "Noe Valley",
        }
        profile = _format_property_profile_from_cache(cache)
        assert profile["assessed_value"] == "$500,000"
        assert profile["assessed_value_raw"] == 500000.0
        assert profile["zoning"] == "RH-2"
        assert profile["use_code"] == "Residential"
        assert profile["neighborhood"] == "Noe Valley"
        assert profile["source"] == "parcel_summary"

    def test_format_property_profile_from_cache_no_tax(self):
        """_format_property_profile_from_cache handles None tax_value."""
        from web.report import _format_property_profile_from_cache
        cache = {
            "tax_value": None,
            "zoning_code": None,
            "use_definition": None,
            "neighborhood_code_definition": None,
        }
        profile = _format_property_profile_from_cache(cache)
        assert profile["assessed_value"] is None
        assert profile["zoning"] is None


# ── DDL in release.py ─────────────────────────────────────────────

class TestReleasePyDDL:
    """Verify release.py includes parcel_summary DDL."""

    def test_release_py_has_parcel_summary(self):
        """scripts/release.py contains CREATE TABLE parcel_summary."""
        import inspect
        from scripts.release import run_release_migrations
        source = inspect.getsource(run_release_migrations)
        assert "parcel_summary" in source
