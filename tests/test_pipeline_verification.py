"""Pipeline verification tests — Sprint 57 Agent C.

Covers three areas:
  C.1 — Trade inspection dataset research (building inspections tool + dataset docs)
  C.2 — Nightly pipeline verification (cron_log infra + cron route registration)
  C.3 — Street-use matching logic (_get_street_use_activity SQL matching)
"""

from __future__ import annotations

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Shared DuckDB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def duckdb_env(tmp_path, monkeypatch):
    """Spin up an isolated DuckDB backend for tests that need real DB access."""
    db_path = str(tmp_path / "test_pipeline.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    # Reset cached connection
    monkeypatch.setattr(db_mod, "_CONN", None, raising=False)

    db_mod.init_user_schema()
    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
    finally:
        conn.close()

    return db_path


# ===========================================================================
# C.1 — Trade Inspection Dataset Research
# ===========================================================================

class TestInspectionDatasetConstants:
    """Verify that the search_inspections tool uses the correct SODA endpoint
    and that the shared inspections table supports the 'source' column that
    distinguishes building vs plumbing inspection rows."""

    def test_building_inspection_endpoint_id(self):
        """search_inspections tool must use dataset vckc-dh2h."""
        from src.tools.search_inspections import ENDPOINT_ID
        assert ENDPOINT_ID == "vckc-dh2h", (
            f"Expected 'vckc-dh2h', got '{ENDPOINT_ID}'. "
            "Building Inspections dataset ID changed."
        )

    def test_plumbing_inspection_endpoint_registered_in_ingest(self):
        """src.ingest must register the plumbing inspections dataset (fuas-yurr)."""
        from src.ingest import DATASETS
        assert "plumbing_inspections" in DATASETS, (
            "Expected 'plumbing_inspections' key in DATASETS dict"
        )
        assert DATASETS["plumbing_inspections"]["endpoint_id"] == "fuas-yurr", (
            "Plumbing inspections endpoint ID should be 'fuas-yurr'"
        )

    def test_building_inspection_endpoint_registered_in_ingest(self):
        """src.ingest must register the building inspections dataset (vckc-dh2h)."""
        from src.ingest import DATASETS
        assert "building_inspections" in DATASETS
        assert DATASETS["building_inspections"]["endpoint_id"] == "vckc-dh2h"

    def test_inspections_table_has_source_column(self, duckdb_env):
        """Shared inspections table must have a 'source' column to distinguish datasets."""
        import src.db as db_mod
        conn = db_mod.get_connection()
        try:
            # Insert a row with source='building' and another with source='plumbing'
            conn.execute(
                "INSERT INTO inspections (id, reference_number, source) VALUES (1, 'P123', 'building')"
            )
            conn.execute(
                "INSERT INTO inspections (id, reference_number, source) VALUES (2, 'P456', 'plumbing')"
            )
            bldg = conn.execute(
                "SELECT COUNT(*) FROM inspections WHERE source = 'building'"
            ).fetchone()[0]
            plmb = conn.execute(
                "SELECT COUNT(*) FROM inspections WHERE source = 'plumbing'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert bldg == 1
        assert plmb == 1

    def test_normalize_plumbing_inspection_sets_source(self):
        """normalize_plumbing_inspection must tag output tuple with source='plumbing'."""
        from src.ingest import normalize_plumbing_inspection
        record = {
            "reference_number": "PL-2024-001",
            "reference_number_type": "permit",
            "inspector": "Smith J",
            "scheduled_date": "2024-01-15",
            "block": "1234",
            "lot": "005",
            "avs_street_name": "MARKET",
            "avs_street_sfx": "ST",
            "analysis_neighborhood": "Mission",
            "supervisor_district": "9",
            "zip_code": "94110",
            "data_as_of": "2024-01-16",
        }
        result = normalize_plumbing_inspection(record, row_id=99)
        # Last element of the tuple is 'source'
        source = result[-1]
        assert source == "plumbing", f"Expected source='plumbing', got '{source}'"

    def test_search_inspections_builds_where_clause_for_permit(self):
        """search_inspections _escape helper must sanitize single quotes."""
        from src.tools.search_inspections import _escape
        dangerous = "abc'def"
        escaped = _escape(dangerous)
        assert "'" not in escaped or "''" in escaped, (
            "Single quotes should be doubled to prevent SoQL injection"
        )
        assert "abc" in escaped


# ===========================================================================
# C.2 — Nightly Pipeline Verification
# ===========================================================================

class TestCronLogInfrastructure:
    """Verify that the cron_log table can be created and that nightly_changes
    exposes the expected public entry points."""

    def test_ensure_cron_log_table_creates_table(self, duckdb_env):
        """ensure_cron_log_table() must create cron_log without raising."""
        from scripts.nightly_changes import ensure_cron_log_table
        # Should not raise
        ensure_cron_log_table()

        import src.db as db_mod
        conn = db_mod.get_connection()
        try:
            rows = conn.execute("SELECT COUNT(*) FROM cron_log").fetchone()
        finally:
            conn.close()
        assert rows[0] == 0, "cron_log should exist and be empty after creation"

    def test_get_last_success_returns_none_on_empty_table(self, duckdb_env):
        """get_last_success() must return None when cron_log is empty."""
        from scripts.nightly_changes import ensure_cron_log_table, get_last_success
        ensure_cron_log_table()
        result = get_last_success("nightly")
        assert result is None

    def test_nightly_changes_exposes_run_nightly(self):
        """scripts.nightly_changes must export the run_nightly async entry point."""
        import scripts.nightly_changes as nc
        assert hasattr(nc, "run_nightly"), "run_nightly function not found"
        import inspect
        assert inspect.iscoroutinefunction(nc.run_nightly), (
            "run_nightly must be an async coroutine function"
        )

    def test_nightly_changes_exposes_main(self):
        """scripts.nightly_changes must export a main() CLI entry point."""
        import scripts.nightly_changes as nc
        assert hasattr(nc, "main"), "main() CLI entry point not found"
        import inspect
        assert callable(nc.main)

    def test_nightly_changes_exposes_sweep_stuck_cron_jobs(self):
        """scripts.nightly_changes must export sweep_stuck_cron_jobs()."""
        import scripts.nightly_changes as nc
        assert hasattr(nc, "sweep_stuck_cron_jobs"), (
            "sweep_stuck_cron_jobs not found in nightly_changes"
        )

    def test_cron_log_columns_match_schema(self, duckdb_env):
        """cron_log table must have the expected columns."""
        from scripts.nightly_changes import ensure_cron_log_table
        ensure_cron_log_table()

        import src.db as db_mod
        conn = db_mod.get_connection()
        try:
            cols_result = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'cron_log'"
            ).fetchall()
        finally:
            conn.close()

        col_names = {r[0] for r in cols_result}
        required = {
            "log_id", "job_type", "started_at", "completed_at",
            "status", "lookback_days", "soda_records",
            "changes_inserted", "inspections_updated", "error_message",
        }
        missing = required - col_names
        assert not missing, f"cron_log is missing columns: {missing}"


class TestCronRouteRegistration:
    """Verify that all expected /cron/* routes are registered in the Flask app."""

    EXPECTED_CRON_ROUTES = [
        "/cron/status",
        "/cron/nightly",
        "/cron/send-briefs",
        "/cron/backup",
        "/cron/migrate",
        "/cron/ingest-electrical",
        "/cron/ingest-plumbing",
        "/cron/ingest-street-use",
        "/cron/ingest-plumbing-inspections",
        "/cron/pipeline-health",
    ]

    @pytest.fixture(autouse=True)
    def _patch_env(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test_routes.duckdb")
        monkeypatch.setenv("SF_PERMITS_DB", db_path)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import src.db as db_mod
        monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
        monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
        monkeypatch.setattr(db_mod, "_CONN", None, raising=False)

    @pytest.mark.parametrize("route", EXPECTED_CRON_ROUTES)
    def test_cron_route_is_registered(self, route):
        """Each expected cron route must appear in the Flask url_map."""
        from web.app import app
        url_rules = {rule.rule for rule in app.url_map.iter_rules()}
        assert route in url_rules, (
            f"Expected route '{route}' not found in Flask url_map. "
            f"Available cron routes: {sorted(r for r in url_rules if '/cron' in r)}"
        )


# ===========================================================================
# C.3 — Street-Use Matching Logic
# ===========================================================================

class TestStreetUseMatching:
    """Validate _get_street_use_activity() SQL matching logic with mocked data."""

    @pytest.fixture()
    def conn_with_street_use(self, duckdb_env):
        """Return a DuckDB connection pre-seeded with street_use_permits rows."""
        import src.db as db_mod

        conn = db_mod.get_connection()

        # Seed test rows
        rows = [
            # Active permit on MARKET ST
            ("SUP-001", "Construction", "Scaffolding", "issued",
             "ACME Co", "MARKET", "MAIN", "1ST",
             "2024-06-01", "2025-06-01", "Financial District/South Beach"),
            # Active permit on VALENCIA ST
            ("SUP-002", "Filming", "Movie shoot", "approved",
             "Big Film", "VALENCIA", "18TH", "19TH",
             "2024-09-01", "2024-09-10", "Mission"),
            # Expired permit on MARKET ST — should be excluded
            ("SUP-003", "Sidewalk", "Repair", "expired",
             "City Crew", "MARKET", "4TH", "5TH",
             "2023-01-01", "2023-03-01", "Financial District/South Beach"),
            # Cancelled permit on MISSION ST — should be excluded
            ("SUP-004", "Banner", "Event", "cancelled",
             "Events Inc", "MISSION", None, None,
             "2024-01-01", "2024-01-15", "Mission"),
            # Active permit on MISSION ST
            ("SUP-005", "Construction", "Crane", "issued",
             "Builder LLC", "MISSION", "7TH", "8TH",
             "2024-07-01", "2025-01-01", "SoMa"),
        ]

        for row in rows:
            conn.execute(
                """INSERT INTO street_use_permits
                   (permit_number, permit_type, permit_purpose, status, agent,
                    street_name, cross_street_1, cross_street_2,
                    approved_date, expiration_date, neighborhood)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row,
            )

        yield conn
        conn.close()

    def test_returns_empty_for_no_addresses(self, conn_with_street_use):
        """_get_street_use_activity must return [] when watched_addresses is empty."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(conn_with_street_use, [])
        assert result == []

    def test_matches_active_permit_by_street_name(self, conn_with_street_use):
        """Function must return active permits matching the watched street name."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET")]
        )
        permit_numbers = [r["permit_number"] for r in result]
        assert "SUP-001" in permit_numbers, (
            "Expected active MARKET ST permit SUP-001 in results"
        )

    def test_excludes_expired_permits(self, conn_with_street_use):
        """Expired permits must NOT appear in the results."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET")]
        )
        permit_numbers = [r["permit_number"] for r in result]
        assert "SUP-003" not in permit_numbers, (
            "Expired permit SUP-003 should be excluded"
        )

    def test_excludes_cancelled_permits(self, conn_with_street_use):
        """Cancelled permits must NOT appear in the results."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MISSION")]
        )
        permit_numbers = [r["permit_number"] for r in result]
        assert "SUP-004" not in permit_numbers, (
            "Cancelled permit SUP-004 should be excluded"
        )

    def test_case_insensitive_match(self, conn_with_street_use):
        """Street name matching must be case-insensitive (UPPER LIKE)."""
        from web.brief import _get_street_use_activity
        result_lower = _get_street_use_activity(
            conn_with_street_use, [("100", "market")]
        )
        result_upper = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET")]
        )
        assert len(result_lower) == len(result_upper), (
            "Results should be the same regardless of input case"
        )

    def test_result_contains_expected_fields(self, conn_with_street_use):
        """Each result dict must contain all required keys."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET")]
        )
        assert len(result) > 0
        required_keys = {
            "permit_number", "permit_type", "permit_purpose", "status",
            "agent", "street_name", "cross_street_1", "cross_street_2",
            "approved_date", "expiration_date", "neighborhood",
            "watched_address",
        }
        for item in result:
            missing = required_keys - set(item.keys())
            assert not missing, f"Result dict missing keys: {missing}"

    def test_watched_address_field_populated(self, conn_with_street_use):
        """watched_address in each result must combine street_number + street_name."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET")]
        )
        assert any("MARKET" in r["watched_address"] for r in result), (
            "watched_address should contain the street name"
        )

    def test_deduplicates_by_permit_number(self, conn_with_street_use):
        """Duplicate permit_number rows (from multiple address matches) must be deduped."""
        from web.brief import _get_street_use_activity
        # Pass two addresses that both match the same SUP-001 permit
        # by using partial match — "MARKET" appears for both ("100", "MARKET") and ("200", "MARKET")
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET"), ("200", "MARKET")]
        )
        permit_numbers = [r["permit_number"] for r in result]
        assert len(permit_numbers) == len(set(permit_numbers)), (
            "Duplicate permit numbers found — deduplication failed"
        )

    def test_multiple_addresses_returns_all_matches(self, conn_with_street_use):
        """When multiple watched addresses are given, results from all streets are included."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("100", "MARKET"), ("500", "VALENCIA")]
        )
        permit_numbers = [r["permit_number"] for r in result]
        assert "SUP-001" in permit_numbers, "Expected MARKET ST permit"
        assert "SUP-002" in permit_numbers, "Expected VALENCIA ST permit"

    def test_returns_empty_on_no_matching_street(self, conn_with_street_use):
        """Querying a street with no data must return an empty list."""
        from web.brief import _get_street_use_activity
        result = _get_street_use_activity(
            conn_with_street_use, [("1", "NONEXISTENT STREET XYZ")]
        )
        assert result == []
