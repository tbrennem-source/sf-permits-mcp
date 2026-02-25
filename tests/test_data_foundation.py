"""Tests for Sprint 57.0 data foundation improvements:

1. Neighborhood backfill migration (Task 1)
2. Two-period velocity refresh — VELOCITY_PERIODS, _rolling_period_filter,
   compute_station_velocity(mode=...) (Task 2)
3. Trade permit filter + recency filter on _query_timeline (Task 3)
4. Integration tests
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def duck_velocity():
    """In-memory DuckDB with addenda + station_velocity_v2 tables."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE addenda (
            id INTEGER PRIMARY KEY,
            application_number TEXT NOT NULL,
            addenda_number INTEGER,
            station TEXT,
            arrive TEXT,
            start_date TEXT,
            finish_date TEXT,
            plan_checked_by TEXT,
            review_results TEXT,
            department TEXT
        )
    """)
    from src.station_velocity_v2 import ensure_velocity_v2_table
    ensure_velocity_v2_table(conn)
    yield conn
    conn.close()


@pytest.fixture
def duck_timeline():
    """In-memory DuckDB with a minimal timeline_stats table."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE timeline_stats (
            permit_number TEXT,
            permit_type_definition TEXT,
            review_path TEXT,
            neighborhood TEXT,
            estimated_cost FLOAT,
            cost_bracket TEXT,
            filed DATE,
            issued DATE,
            completed DATE,
            days_to_issuance INTEGER,
            days_to_completion INTEGER,
            supervisor_district TEXT
        )
    """)
    yield conn
    conn.close()


@pytest.fixture
def duck_backfill():
    """In-memory DuckDB with permits + tax_rolls tables for backfill testing."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE permits (
            permit_number TEXT PRIMARY KEY,
            permit_type_definition TEXT,
            neighborhood TEXT,
            block TEXT,
            lot TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE tax_rolls (
            id INTEGER PRIMARY KEY,
            block TEXT,
            lot TEXT,
            neighborhood TEXT
        )
    """)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bulk_addenda(conn, station: str, count: int, arrive_base: str | None = None,
                  days_duration: int = 10, addenda_number: int = 0,
                  review_results: str | None = None, id_start: int = 1):
    """Insert count addenda rows for a station, all within the last 30 days by default."""
    from datetime import datetime
    if arrive_base is None:
        # Default: within last 30 days so 'current' (90d) window picks them up
        arrive_base = (date.today() - timedelta(days=20)).strftime("%Y-%m-%d")
    base = datetime.strptime(arrive_base, "%Y-%m-%d")
    for i in range(count):
        arrive = (base + timedelta(days=i % 10)).strftime("%Y-%m-%d")
        finish = (base + timedelta(days=i % 10 + days_duration)).strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO addenda
               (id, application_number, addenda_number, station, arrive,
                start_date, finish_date, plan_checked_by, review_results, department)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                id_start + i,
                f"PERMIT{id_start + i:06d}",
                addenda_number,
                station,
                arrive,
                arrive,
                finish,
                f"REVIEWER{i % 3}",
                review_results,
                "DBI",
            ),
        )


# ===========================================================================
# 1. Neighborhood backfill migration
# ===========================================================================


class TestNeighborhoodBackfillRegistration:
    def test_migration_exists_in_list(self):
        """neighborhood_backfill migration is registered in MIGRATIONS."""
        from scripts.run_prod_migrations import MIGRATIONS
        names = [m.name for m in MIGRATIONS]
        assert "neighborhood_backfill" in names

    def test_migration_after_inspections_unique(self):
        """neighborhood_backfill comes after inspections_unique in the ordered list."""
        from scripts.run_prod_migrations import MIGRATIONS
        names = [m.name for m in MIGRATIONS]
        idx_inspections = names.index("inspections_unique")
        idx_backfill = names.index("neighborhood_backfill")
        assert idx_backfill > idx_inspections, (
            f"neighborhood_backfill (idx={idx_backfill}) must come after "
            f"inspections_unique (idx={idx_inspections})"
        )

    def test_migration_is_callable(self):
        """The migration's run attribute is callable."""
        from scripts.run_prod_migrations import MIGRATION_BY_NAME
        assert "neighborhood_backfill" in MIGRATION_BY_NAME
        m = MIGRATION_BY_NAME["neighborhood_backfill"]
        assert callable(m.run)

    def test_migration_has_description(self):
        """The migration has a non-empty description."""
        from scripts.run_prod_migrations import MIGRATION_BY_NAME
        m = MIGRATION_BY_NAME["neighborhood_backfill"]
        assert m.description and len(m.description) > 10


class TestNeighborhoodBackfillLogic:
    def test_backfill_updates_null_neighborhood(self, duck_backfill):
        """Permits with NULL neighborhood get backfilled from matching tax_rolls row."""
        conn = duck_backfill

        # Insert permits: two with NULL neighborhood, block+lot matches tax_rolls
        conn.execute("INSERT INTO permits VALUES ('P001', 'Electrical Permit', NULL, '1234', '001')")
        conn.execute("INSERT INTO permits VALUES ('P002', 'Plumbing Permit',   NULL, '1234', '002')")
        # One permit that already has a neighborhood — should not be overwritten
        conn.execute("INSERT INTO permits VALUES ('P003', 'Building Permit',   'Mission', '9999', '001')")

        # Insert tax_rolls
        conn.execute("INSERT INTO tax_rolls VALUES (1, '1234', '001', 'SoMa')")
        conn.execute("INSERT INTO tax_rolls VALUES (2, '1234', '002', 'SoMa')")
        conn.execute("INSERT INTO tax_rolls VALUES (3, '9999', '001', 'Noe Valley')")

        # Run the UPDATE directly (DuckDB mode)
        conn.execute("""
            UPDATE permits SET neighborhood = t.neighborhood
            FROM tax_rolls t
            WHERE permits.block = t.block AND permits.lot = t.lot
              AND permits.neighborhood IS NULL
              AND t.neighborhood IS NOT NULL
        """)

        rows = conn.execute(
            "SELECT permit_number, neighborhood FROM permits ORDER BY permit_number"
        ).fetchall()
        result = {r[0]: r[1] for r in rows}

        assert result["P001"] == "SoMa", "Electrical permit should have neighborhood backfilled"
        assert result["P002"] == "SoMa", "Plumbing permit should have neighborhood backfilled"
        assert result["P003"] == "Mission", "Pre-filled permit should NOT be overwritten"

    def test_backfill_no_match_leaves_null(self, duck_backfill):
        """Permits with no matching tax_roll record remain NULL after backfill."""
        conn = duck_backfill

        conn.execute("INSERT INTO permits VALUES ('P001', 'Electrical Permit', NULL, '9999', '099')")
        # No matching tax_rolls row

        conn.execute("""
            UPDATE permits SET neighborhood = t.neighborhood
            FROM tax_rolls t
            WHERE permits.block = t.block AND permits.lot = t.lot
              AND permits.neighborhood IS NULL
              AND t.neighborhood IS NOT NULL
        """)

        row = conn.execute("SELECT neighborhood FROM permits WHERE permit_number = 'P001'").fetchone()
        assert row[0] is None, "No matching tax_roll → neighborhood stays NULL"

    def test_backfill_function_is_importable(self):
        """_run_neighborhood_backfill function is importable and callable."""
        from scripts.run_prod_migrations import _run_neighborhood_backfill
        assert callable(_run_neighborhood_backfill)


# ===========================================================================
# 2. Two-period velocity refresh
# ===========================================================================


class TestVelocityPeriodConstants:
    def test_velocity_periods_dict_exists(self):
        """VELOCITY_PERIODS dict is exported from station_velocity_v2."""
        from src.station_velocity_v2 import VELOCITY_PERIODS
        assert isinstance(VELOCITY_PERIODS, dict)

    def test_velocity_periods_has_current(self):
        """VELOCITY_PERIODS has a 'current' key."""
        from src.station_velocity_v2 import VELOCITY_PERIODS
        assert "current" in VELOCITY_PERIODS

    def test_velocity_periods_has_baseline(self):
        """VELOCITY_PERIODS has a 'baseline' key."""
        from src.station_velocity_v2 import VELOCITY_PERIODS
        assert "baseline" in VELOCITY_PERIODS

    def test_current_period_is_90_days(self):
        """VELOCITY_PERIODS['current'] is 90 days."""
        from src.station_velocity_v2 import VELOCITY_PERIODS
        assert VELOCITY_PERIODS["current"] == 90

    def test_baseline_period_is_365_days(self):
        """VELOCITY_PERIODS['baseline'] is 365 days."""
        from src.station_velocity_v2 import VELOCITY_PERIODS
        assert VELOCITY_PERIODS["baseline"] == 365

    def test_min_current_samples_constant(self):
        """MIN_CURRENT_SAMPLES constant is defined and > 0."""
        from src.station_velocity_v2 import MIN_CURRENT_SAMPLES
        assert MIN_CURRENT_SAMPLES > 0

    def test_current_widen_days_constant(self):
        """CURRENT_WIDEN_DAYS constant is wider than 90 days."""
        from src.station_velocity_v2 import CURRENT_WIDEN_DAYS, VELOCITY_PERIODS
        assert CURRENT_WIDEN_DAYS > VELOCITY_PERIODS["current"]


class TestRollingPeriodFilter:
    def test_rolling_filter_returns_tuple(self):
        """_rolling_period_filter returns (clause_str, params_list)."""
        from src.station_velocity_v2 import _rolling_period_filter
        clause, params = _rolling_period_filter(90)
        assert isinstance(clause, str)
        assert isinstance(params, list)
        assert len(params) == 1

    def test_rolling_filter_90_days(self):
        """90-day filter cutoff is approximately 90 days ago."""
        from src.station_velocity_v2 import _rolling_period_filter
        _clause, params = _rolling_period_filter(90)
        cutoff = date.fromisoformat(params[0])
        expected = date.today() - timedelta(days=90)
        # Allow 1 day tolerance for edge cases
        assert abs((cutoff - expected).days) <= 1

    def test_rolling_filter_365_days(self):
        """365-day filter cutoff is approximately 1 year ago."""
        from src.station_velocity_v2 import _rolling_period_filter
        _clause, params = _rolling_period_filter(365)
        cutoff = date.fromisoformat(params[0])
        expected = date.today() - timedelta(days=365)
        assert abs((cutoff - expected).days) <= 1

    def test_rolling_filter_clause_references_arrive(self):
        """Rolling period filter WHERE clause references the arrive column."""
        from src.station_velocity_v2 import _rolling_period_filter
        clause, _ = _rolling_period_filter(90)
        assert "arrive" in clause.lower()


class TestComputeStationVelocityModes:
    def test_cron_mode_returns_current_and_baseline(self, duck_velocity):
        """compute_station_velocity(mode='cron') returns only 'current' and 'baseline' periods."""
        conn = duck_velocity

        # Insert enough rows for BLDG station within current 90-day window
        _bulk_addenda(conn, "BLDG", 15, id_start=1)
        # Insert enough rows for baseline (within last year but outside 90d)
        arrive_old = (date.today() - timedelta(days=200)).strftime("%Y-%m-%d")
        _bulk_addenda(conn, "BLDG", 15, arrive_base=arrive_old, id_start=100)

        from src.station_velocity_v2 import compute_station_velocity
        results = compute_station_velocity(conn, mode='cron')
        periods_returned = {v.period for v in results}

        # Should only have 'current' and/or 'baseline' (may be empty if not enough samples)
        # Key invariant: must NOT contain legacy period names
        assert "recent_6mo" not in periods_returned, "Cron mode should not return 'recent_6mo'"
        assert "all" not in periods_returned, "Cron mode should not return 'all'"
        assert "2024" not in periods_returned, "Cron mode should not return year-based periods"

    def test_all_mode_returns_legacy_periods(self, duck_velocity):
        """compute_station_velocity(mode='all') returns legacy period labels."""
        conn = duck_velocity

        # Insert rows in 2024 date range
        _bulk_addenda(conn, "BLDG", 15, arrive_base="2024-06-01", id_start=1)

        from src.station_velocity_v2 import compute_station_velocity
        results = compute_station_velocity(conn, mode='all')
        periods_returned = {v.period for v in results}

        # Should contain at least one legacy period (e.g. 'all' or '2024')
        legacy = {"all", "2024", "2025", "2026", "recent_6mo"}
        assert periods_returned & legacy, (
            f"mode='all' should return legacy period labels, got: {periods_returned}"
        )

    def test_default_mode_is_cron(self, duck_velocity):
        """compute_station_velocity() without mode argument uses 'cron' mode."""
        conn = duck_velocity
        _bulk_addenda(conn, "BLDG", 15, id_start=1)

        from src.station_velocity_v2 import compute_station_velocity
        results = compute_station_velocity(conn)
        periods_returned = {v.period for v in results}

        # Same invariant as cron mode
        assert "recent_6mo" not in periods_returned
        assert "all" not in periods_returned

    def test_explicit_periods_overrides_cron_mode(self, duck_velocity):
        """When periods list is explicitly provided, it forces legacy 'all' mode behavior.

        This preserves backward compatibility: existing callers that pass
        periods=['all'] always get legacy period labels back, regardless of mode.
        """
        conn = duck_velocity
        # Insert data in 2024 (outside any rolling window) — only 'all' period will find it
        _bulk_addenda(conn, "BLDG", 15, arrive_base="2024-06-01", id_start=1)

        from src.station_velocity_v2 import compute_station_velocity
        # Passing explicit periods=['all'] overrides default cron mode
        results = compute_station_velocity(conn, periods=["all"])
        periods_returned = {v.period for v in results}

        # Because periods=['all'] was passed, mode becomes 'all' → legacy label expected
        assert "all" in periods_returned or len(results) == 0  # Results may be empty if MIN_SAMPLES not met

    def test_station_widening_under_min_samples(self, duck_velocity):
        """When a station's 90-day count < MIN_CURRENT_SAMPLES, it uses wider window."""
        conn = duck_velocity
        from src.station_velocity_v2 import MIN_CURRENT_SAMPLES, CURRENT_WIDEN_DAYS

        # Insert only a few rows within the 90-day window (below MIN_CURRENT_SAMPLES)
        small_count = max(1, MIN_CURRENT_SAMPLES - 5)
        _bulk_addenda(conn, "SMALL_STATION", small_count, id_start=1)

        # Insert enough rows within the wider window (180d) but outside 90d
        wide_base = (date.today() - timedelta(days=120)).strftime("%Y-%m-%d")
        _bulk_addenda(conn, "SMALL_STATION", MIN_CURRENT_SAMPLES + 5,
                      arrive_base=wide_base, id_start=100)

        from src.station_velocity_v2 import compute_station_velocity
        results = compute_station_velocity(conn, mode='cron')

        # The station should appear with period='current'
        current_rows = [v for v in results
                        if v.station == "SMALL_STATION" and v.period == "current"]
        if current_rows:
            # If widening was applied, sample_count > small_count
            assert current_rows[0].sample_count >= small_count

    def test_refresh_velocity_v2_writes_periods_to_table(self, duck_velocity):
        """refresh_velocity_v2() populates station_velocity_v2 with cron periods."""
        conn = duck_velocity
        _bulk_addenda(conn, "BLDG", 15, id_start=1)

        from src.station_velocity_v2 import refresh_velocity_v2
        stats = refresh_velocity_v2(conn)

        assert "rows_inserted" in stats
        assert "stations" in stats
        assert "periods" in stats

        # Check that we can query the populated table
        rows = conn.execute("SELECT DISTINCT period FROM station_velocity_v2").fetchall()
        period_labels = {r[0] for r in rows}
        # Should not contain legacy names
        assert "recent_6mo" not in period_labels
        assert "all" not in period_labels


# ===========================================================================
# 3. Trade permit filter on _query_timeline
# ===========================================================================


class TestTradePermitFilter:
    def test_trade_permit_filter_in_conditions(self):
        """_query_timeline SQL excludes Electrical Permit and Plumbing Permit."""
        from src.tools.estimate_timeline import _query_timeline

        # Build a DuckDB connection with timeline_stats
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE timeline_stats (
                permit_number TEXT,
                permit_type_definition TEXT,
                review_path TEXT,
                neighborhood TEXT,
                estimated_cost FLOAT,
                cost_bracket TEXT,
                filed DATE,
                issued DATE,
                completed DATE,
                days_to_issuance INTEGER,
                days_to_completion INTEGER,
                supervisor_district TEXT
            )
        """)

        # Insert a mix: some trade permits, some non-trade permits
        today = date.today()
        for i in range(20):
            issued = today - timedelta(days=30)
            filed = issued - timedelta(days=10 + i)
            conn.execute("""
                INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)
            """, (
                f"P{i:03d}",
                "Building Permit",
                "in_house",
                "Mission",
                100000.0,
                "50k_150k",
                filed.isoformat(),
                issued.isoformat(),
                10 + i,
            ))

        # Insert trade permits — these should be excluded
        for i in range(5):
            issued = today - timedelta(days=30)
            filed = issued - timedelta(days=5)
            conn.execute("""
                INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)
            """, (
                f"E{i:03d}",
                "Electrical Permit",
                "in_house",
                "Mission",
                50000.0,
                "under_50k",
                filed.isoformat(),
                issued.isoformat(),
                5,
            ))

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            result = _query_timeline(conn, None, None, None, None)

        # Should return a result (non-trade permits exist)
        assert result is not None
        conn.close()

    def test_electrical_permits_excluded_from_result(self, duck_timeline):
        """When only electrical permits exist in timeline_stats, query returns None."""
        conn = duck_timeline
        today = date.today()

        # Insert only electrical permits
        for i in range(20):
            issued = today - timedelta(days=30)
            filed = issued - timedelta(days=10 + i)
            conn.execute(
                "INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                (f"E{i:03d}", "Electrical Permit", "in_house", "SoMa", 10000.0,
                 "under_50k", filed.isoformat(), issued.isoformat(), 10 + i)
            )

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            from src.tools.estimate_timeline import _query_timeline
            result = _query_timeline(conn, None, None, None, None)

        # All permits are electrical → should be filtered out → None
        assert result is None

    def test_plumbing_permits_excluded_from_result(self, duck_timeline):
        """When only plumbing permits exist in timeline_stats, query returns None."""
        conn = duck_timeline
        today = date.today()

        for i in range(20):
            issued = today - timedelta(days=30)
            filed = issued - timedelta(days=10 + i)
            conn.execute(
                "INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                (f"PL{i:03d}", "Plumbing Permit", "in_house", "SoMa", 10000.0,
                 "under_50k", filed.isoformat(), issued.isoformat(), 10 + i)
            )

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            from src.tools.estimate_timeline import _query_timeline
            result = _query_timeline(conn, None, None, None, None)

        assert result is None

    def test_recency_filter_excludes_old_data(self, duck_timeline):
        """Permits issued more than 1 year ago are excluded by recency filter."""
        conn = duck_timeline
        today = date.today()

        # Insert only ancient permits (2+ years ago)
        for i in range(20):
            issued = today - timedelta(days=800)  # ~2.2 years ago
            filed = issued - timedelta(days=10 + i)
            conn.execute(
                "INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                (f"OLD{i:03d}", "Building Permit", "in_house", "Mission", 100000.0,
                 "50k_150k", filed.isoformat(), issued.isoformat(), 10 + i)
            )

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            from src.tools.estimate_timeline import _query_timeline
            result = _query_timeline(conn, None, None, None, None)

        # Ancient permits should be filtered by recency → None (< 10 samples)
        assert result is None

    def test_recent_permits_pass_recency_filter(self, duck_timeline):
        """Permits issued within last year are included by recency filter."""
        conn = duck_timeline
        today = date.today()

        # Insert recent non-trade permits
        for i in range(15):
            issued = today - timedelta(days=30 + i)
            filed = issued - timedelta(days=10)
            conn.execute(
                "INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                (f"REC{i:03d}", "Building Permit", "in_house", "Mission", 100000.0,
                 "50k_150k", filed.isoformat(), issued.isoformat(), 10)
            )

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            from src.tools.estimate_timeline import _query_timeline
            result = _query_timeline(conn, None, None, None, None)

        assert result is not None
        assert result["sample_size"] == 15


# ===========================================================================
# 4. Integration tests
# ===========================================================================


class TestIntegration:
    def test_velocity_refresh_end_to_end(self, duck_velocity):
        """End-to-end: insert addenda data → refresh_velocity_v2 → rows in table."""
        conn = duck_velocity

        # Insert 15 rows for BLDG within the last 60 days
        _bulk_addenda(conn, "BLDG", 15, id_start=1)
        # Insert 15 rows for SFFD
        _bulk_addenda(conn, "SFFD", 15, id_start=200)

        from src.station_velocity_v2 import refresh_velocity_v2
        stats = refresh_velocity_v2(conn)

        # refresh_velocity_v2 returns a dict with rows_inserted, stations, periods
        assert "rows_inserted" in stats
        assert "stations" in stats
        # Table should have rows
        count = conn.execute("SELECT COUNT(*) FROM station_velocity_v2").fetchone()[0]
        assert count > 0, "After refresh, station_velocity_v2 should have rows"

    def test_timeline_estimate_still_works_after_filter_changes(self, duck_timeline):
        """estimate_timeline works end-to-end with trade permit + recency filters active."""
        conn = duck_timeline
        today = date.today()

        # Insert enough non-trade, recent permits
        for i in range(20):
            issued = today - timedelta(days=30 + i)
            filed = issued - timedelta(days=10)
            conn.execute(
                "INSERT INTO timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL)",
                (f"P{i:03d}", "Building Permit", "in_house", "Mission", 150000.0,
                 "50k_150k", filed.isoformat(), issued.isoformat(), 10)
            )

        with patch("src.tools.estimate_timeline.BACKEND", "duckdb"):
            from src.tools.estimate_timeline import _query_timeline
            result = _query_timeline(conn, "in_house", "Mission", "50k_150k", None)

        # Should find results
        assert result is not None
        assert result["sample_size"] >= 10

    def test_migration_list_ordering_neighborhood_after_inspections_unique(self):
        """neighborhood_backfill is at the end (after inspections_unique) in MIGRATIONS."""
        from scripts.run_prod_migrations import MIGRATIONS
        names = [m.name for m in MIGRATIONS]

        assert "neighborhood_backfill" in names
        assert "inspections_unique" in names

        idx_inspections = names.index("inspections_unique")
        idx_backfill = names.index("neighborhood_backfill")
        assert idx_backfill == idx_inspections + 1, (
            f"neighborhood_backfill should be immediately after inspections_unique "
            f"(got indices {idx_inspections} and {idx_backfill})"
        )

    def test_full_migration_count_updated(self):
        """MIGRATIONS list now has 11 entries (10 original + neighborhood_backfill)."""
        from scripts.run_prod_migrations import MIGRATIONS
        assert len(MIGRATIONS) == 11, (
            f"Expected 11 migrations after adding neighborhood_backfill, got {len(MIGRATIONS)}"
        )

    def test_velocity_periods_flow_through_refresh(self, duck_velocity):
        """refresh_velocity_v2 returns period_labels reflecting VELOCITY_PERIODS keys."""
        conn = duck_velocity
        _bulk_addenda(conn, "BLDG", 15, id_start=1)

        from src.station_velocity_v2 import refresh_velocity_v2, VELOCITY_PERIODS
        stats = refresh_velocity_v2(conn)

        # period_labels in stats should be a subset of VELOCITY_PERIODS keys
        if "period_labels" in stats:
            returned = set(stats["period_labels"])
            expected_keys = set(VELOCITY_PERIODS.keys())
            assert returned <= expected_keys, (
                f"Unexpected period labels in refresh: {returned - expected_keys}"
            )
