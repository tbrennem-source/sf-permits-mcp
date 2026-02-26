"""Tests for station_velocity_v2 — data scrub, computation, persistence, and query helpers.

Uses an in-memory DuckDB with synthetic addenda data to test all velocity
computation logic without requiring a real database or production data.
"""

import pytest
from datetime import date, timedelta

import duckdb


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def duck_conn():
    """In-memory DuckDB connection with addenda + station_velocity_v2 tables."""
    conn = duckdb.connect(":memory:")

    # Create addenda table matching production schema
    conn.execute("""
        CREATE TABLE addenda (
            id INTEGER PRIMARY KEY,
            primary_key TEXT,
            application_number TEXT NOT NULL,
            addenda_number INTEGER,
            step INTEGER,
            station TEXT,
            arrive TEXT,
            assign_date TEXT,
            start_date TEXT,
            finish_date TEXT,
            approved_date TEXT,
            plan_checked_by TEXT,
            review_results TEXT,
            hold_description TEXT,
            addenda_status TEXT,
            department TEXT,
            title TEXT,
            data_as_of TEXT
        )
    """)

    # Create station_velocity_v2 table using the same function as production
    from src.station_velocity_v2 import ensure_velocity_v2_table
    ensure_velocity_v2_table(conn)

    yield conn
    conn.close()


def _insert_addenda(conn, rows: list[dict]):
    """Insert addenda rows from list of dicts with sensible defaults."""
    for i, row in enumerate(rows):
        conn.execute(
            """INSERT INTO addenda
               (id, application_number, addenda_number, station, arrive,
                start_date, finish_date, plan_checked_by, review_results, department)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.get("id", i + 1),
                row.get("application_number", f"PERMIT{i:04d}"),
                row.get("addenda_number", 0),
                row.get("station", "BLDG"),
                row.get("arrive", "2024-06-01"),
                row.get("start_date", "2024-06-01"),
                row.get("finish_date", "2024-06-10"),
                row.get("plan_checked_by", "SMITH JOHN"),
                row.get("review_results", None),
                row.get("department", "DBI"),
            ),
        )


def _bulk_addenda(conn, station: str, count: int, arrive_base: str = "2024-06-01",
                  days_range: tuple[int, int] = (1, 30), addenda_number: int = 0,
                  review_results: str | None = None, id_start: int = 1):
    """Insert `count` addenda rows for a station with sequential durations."""
    from datetime import datetime
    base = datetime.strptime(arrive_base, "%Y-%m-%d")
    low, high = days_range
    for i in range(count):
        days = low + (i % (high - low + 1)) if high > low else low
        arrive = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        finish = (base + timedelta(days=i + days)).strftime("%Y-%m-%d")
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


# ── Module import tests ─────────────────────────────────────────────


def test_import_station_velocity_v2():
    """Module imports cleanly."""
    from src.station_velocity_v2 import (
        StationVelocity,
        compute_station_velocity,
        ensure_velocity_v2_table,
        refresh_velocity_v2,
        get_velocity_for_station,
        get_all_velocities,
        MIN_SAMPLES,
        PERIODS,
    )
    assert MIN_SAMPLES == 10
    assert "all" in PERIODS
    assert "recent_6mo" in PERIODS


def test_station_velocity_dataclass():
    """StationVelocity dataclass works as expected."""
    from src.station_velocity_v2 import StationVelocity
    sv = StationVelocity(
        station="BLDG", metric_type="initial",
        p25_days=1.0, p50_days=3.0, p75_days=7.0, p90_days=14.0,
        sample_count=100, period="all",
    )
    assert sv.station == "BLDG"
    assert sv.p50_days == 3.0
    assert sv.sample_count == 100


# ── Period filter tests ──────────────────────────────────────────────


def test_period_filter_all():
    from src.station_velocity_v2 import _period_filter
    clause, params = _period_filter("all")
    assert "2018-01-01" in params
    assert "arrive" in clause


def test_period_filter_recent_6mo():
    from src.station_velocity_v2 import _period_filter
    clause, params = _period_filter("recent_6mo")
    assert len(params) == 1
    # The cutoff should be a date string ~183 days ago
    cutoff = date.fromisoformat(params[0])
    assert (date.today() - cutoff).days >= 180
    assert (date.today() - cutoff).days <= 190


def test_period_filter_year():
    from src.station_velocity_v2 import _period_filter
    clause, params = _period_filter("2024")
    assert params == ["2024-01-01", "2025-01-01"]
    assert "arrive" in clause


def test_period_filter_unknown_defaults_to_all():
    from src.station_velocity_v2 import _period_filter
    clause, params = _period_filter("bogus")
    assert "2018-01-01" in params


# ── Compute tests (synthetic DuckDB data) ────────────────────────────


def test_compute_empty_table(duck_conn):
    """Empty addenda table returns empty results."""
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert results == []


def test_compute_below_min_samples(duck_conn):
    """Stations with fewer than MIN_SAMPLES records are excluded."""
    _bulk_addenda(duck_conn, "BLDG", count=5, arrive_base="2024-01-01")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


def test_compute_at_min_samples(duck_conn):
    """Stations with exactly MIN_SAMPLES records are included."""
    _bulk_addenda(duck_conn, "BLDG", count=10, arrive_base="2024-01-01",
                  days_range=(5, 15))
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    # Should have 1 result (initial, all)
    initial = [r for r in results if r.metric_type == "initial"]
    assert len(initial) == 1
    assert initial[0].station == "BLDG"
    assert initial[0].sample_count == 10


def test_compute_excludes_administrative(duck_conn):
    """Administrative review results are excluded from computation."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  review_results="Administrative")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


def test_compute_excludes_not_applicable(duck_conn):
    """Not Applicable review results are excluded."""
    _bulk_addenda(duck_conn, "SFFD", count=15, arrive_base="2024-01-01",
                  review_results="Not Applicable")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


def test_compute_includes_null_review_results(duck_conn):
    """NULL review results (the majority) ARE included."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  review_results=None)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    initial = [r for r in results if r.metric_type == "initial"]
    assert len(initial) == 1


def test_compute_includes_approved(duck_conn):
    """Approved review results ARE included."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  review_results="Approved")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    initial = [r for r in results if r.metric_type == "initial"]
    assert len(initial) == 1


def test_compute_includes_issued_comments(duck_conn):
    """Issued Comments review results ARE included."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  review_results="Issued Comments")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    initial = [r for r in results if r.metric_type == "initial"]
    assert len(initial) == 1


def test_compute_excludes_pre_2018(duck_conn):
    """Pre-2018 data is excluded."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2017-06-01")
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


def test_compute_separates_initial_and_revision(duck_conn):
    """Initial (addenda_number=0) and revision (addenda_number>=1) are separate."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  addenda_number=0, id_start=1)
    _bulk_addenda(duck_conn, "BLDG", count=12, arrive_base="2024-01-01",
                  addenda_number=1, days_range=(10, 40), id_start=100)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    initial = [r for r in results if r.metric_type == "initial" and r.station == "BLDG"]
    revision = [r for r in results if r.metric_type == "revision" and r.station == "BLDG"]
    assert len(initial) == 1
    assert len(revision) == 1
    assert initial[0].sample_count == 15
    assert revision[0].sample_count == 12


def test_compute_deduplicates_reassignment(duck_conn):
    """Reassignment dupes (same permit+station+addenda) are deduped to latest finish."""
    # Same permit, same station, same addenda_number, different reviewers
    for i in range(3):
        conn = duck_conn
        conn.execute(
            """INSERT INTO addenda
               (id, application_number, addenda_number, station, arrive,
                start_date, finish_date, plan_checked_by, review_results, department)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                200 + i,
                "PERMIT_DEDUP",
                0,
                "BLDG",
                "2024-03-01",
                "2024-03-01",
                f"2024-03-{10 + i * 5:02d}",
                f"REVIEWER_{i}",
                None,
                "DBI",
            ),
        )
    # Add enough other permits to meet MIN_SAMPLES
    _bulk_addenda(duck_conn, "BLDG", count=12, arrive_base="2024-04-01",
                  days_range=(5, 15), id_start=300)

    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    initial = [r for r in results if r.metric_type == "initial" and r.station == "BLDG"]
    assert len(initial) == 1
    # Should be 12 unique permits + 1 deduped = 13, not 14
    assert initial[0].sample_count == 13


def test_compute_excludes_over_365_days(duck_conn):
    """Duration > 365 days is excluded as an outlier."""
    rows = []
    for i in range(15):
        rows.append({
            "id": 400 + i,
            "application_number": f"PERMIT_LONG{i:04d}",
            "addenda_number": 0,
            "station": "SLOW",
            "arrive": "2024-01-01",
            "start_date": "2024-01-01",
            "finish_date": "2025-06-01",  # > 365 days
        })
    _insert_addenda(duck_conn, rows)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    slow = [r for r in results if r.station == "SLOW"]
    assert len(slow) == 0


def test_compute_excludes_negative_durations(duck_conn):
    """Negative durations (finish < arrive) are excluded."""
    rows = []
    for i in range(15):
        rows.append({
            "id": 500 + i,
            "application_number": f"PERMIT_NEG{i:04d}",
            "addenda_number": 0,
            "station": "NEG",
            "arrive": "2024-06-10",
            "start_date": "2024-06-10",
            "finish_date": "2024-06-01",  # finish before arrive
        })
    _insert_addenda(duck_conn, rows)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    neg = [r for r in results if r.station == "NEG"]
    assert len(neg) == 0


def test_compute_multiple_stations(duck_conn):
    """Multiple stations computed simultaneously."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-01-01",
                  days_range=(3, 7), id_start=1)
    _bulk_addenda(duck_conn, "SFFD", count=20, arrive_base="2024-01-01",
                  days_range=(20, 35), id_start=100)
    _bulk_addenda(duck_conn, "CPB", count=12, arrive_base="2024-01-01",
                  days_range=(1, 3), id_start=200)

    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    stations = {r.station for r in results if r.metric_type == "initial"}
    assert "BLDG" in stations
    assert "SFFD" in stations
    assert "CPB" in stations


def test_compute_percentile_ordering(duck_conn):
    """p25 <= p50 <= p75 <= p90."""
    _bulk_addenda(duck_conn, "BLDG", count=50, arrive_base="2024-01-01",
                  days_range=(1, 50))
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    for r in results:
        if r.p25_days is not None and r.p90_days is not None:
            assert r.p25_days <= r.p50_days <= r.p75_days <= r.p90_days


def test_compute_period_2024(duck_conn):
    """Period '2024' only includes 2024 data."""
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2024-06-01",
                  days_range=(3, 10), id_start=1)
    _bulk_addenda(duck_conn, "BLDG", count=15, arrive_base="2025-06-01",
                  days_range=(20, 30), id_start=100)

    from src.station_velocity_v2 import compute_station_velocity
    results_2024 = compute_station_velocity(duck_conn, periods=["2024"])
    results_2025 = compute_station_velocity(duck_conn, periods=["2025"])

    bldg_2024 = [r for r in results_2024 if r.station == "BLDG" and r.metric_type == "initial"]
    bldg_2025 = [r for r in results_2025 if r.station == "BLDG" and r.metric_type == "initial"]

    assert len(bldg_2024) == 1
    assert len(bldg_2025) == 1
    # 2024 should be faster (3-10 days) than 2025 (20-30 days)
    assert bldg_2024[0].p50_days < bldg_2025[0].p50_days


def test_compute_null_arrive_excluded(duck_conn):
    """Rows with NULL arrive are excluded."""
    rows = []
    for i in range(15):
        rows.append({
            "id": 600 + i,
            "application_number": f"PERMIT_NOARR{i:04d}",
            "station": "BLDG",
            "arrive": None,
            "start_date": "2024-01-01",
            "finish_date": "2024-01-10",
        })
    _insert_addenda(duck_conn, rows)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


def test_compute_null_finish_excluded(duck_conn):
    """Rows with NULL finish_date are excluded (pending reviews)."""
    rows = []
    for i in range(15):
        rows.append({
            "id": 700 + i,
            "application_number": f"PERMIT_NOFIN{i:04d}",
            "station": "BLDG",
            "arrive": "2024-01-01",
            "start_date": "2024-01-01",
            "finish_date": None,
        })
    _insert_addenda(duck_conn, rows)
    from src.station_velocity_v2 import compute_station_velocity
    results = compute_station_velocity(duck_conn, periods=["all"])
    assert len(results) == 0


# ── Persistence tests ────────────────────────────────────────────────


def test_ensure_velocity_v2_table(duck_conn):
    """Table creation is idempotent."""
    from src.station_velocity_v2 import ensure_velocity_v2_table
    # Drop table first to test creation
    duck_conn.execute("DROP TABLE IF EXISTS station_velocity_v2")
    ensure_velocity_v2_table(duck_conn)
    # Should not error on second call
    ensure_velocity_v2_table(duck_conn)
    # Table should exist
    result = duck_conn.execute(
        "SELECT COUNT(*) FROM station_velocity_v2"
    ).fetchone()
    assert result[0] == 0


def test_refresh_velocity_v2_empty(duck_conn):
    """Refresh with empty addenda returns zero stats."""
    from src.station_velocity_v2 import refresh_velocity_v2
    stats = refresh_velocity_v2(duck_conn)
    assert stats["rows_inserted"] == 0
    assert stats["stations"] == 0


def test_refresh_velocity_v2_with_data(duck_conn):
    """Refresh inserts rows into station_velocity_v2.

    Uses recent dates so the cron-mode rolling windows (90d + 365d) capture the data.
    """
    # Insert data within last 30 days so both 'current' (90d) and 'baseline' (365d) pick it up
    recent_base = (date.today() - timedelta(days=20)).strftime("%Y-%m-%d")
    _bulk_addenda(duck_conn, "BLDG", count=20, arrive_base=recent_base,
                  days_range=(3, 10), id_start=1)
    _bulk_addenda(duck_conn, "SFFD", count=15, arrive_base=recent_base,
                  days_range=(15, 30), id_start=100)

    from src.station_velocity_v2 import refresh_velocity_v2
    stats = refresh_velocity_v2(duck_conn)
    assert stats["rows_inserted"] > 0
    assert stats["stations"] >= 2

    # Verify data in table
    rows = duck_conn.execute(
        "SELECT COUNT(*) FROM station_velocity_v2"
    ).fetchone()
    assert rows[0] == stats["rows_inserted"]


def test_refresh_velocity_v2_idempotent(duck_conn):
    """Calling refresh twice produces the same result (truncate + reinsert)."""
    _bulk_addenda(duck_conn, "BLDG", count=20, arrive_base="2024-01-01",
                  days_range=(3, 10))

    from src.station_velocity_v2 import refresh_velocity_v2
    stats1 = refresh_velocity_v2(duck_conn)
    stats2 = refresh_velocity_v2(duck_conn)
    assert stats1["rows_inserted"] == stats2["rows_inserted"]

    # Table should not have doubled rows
    rows = duck_conn.execute(
        "SELECT COUNT(*) FROM station_velocity_v2"
    ).fetchone()
    assert rows[0] == stats2["rows_inserted"]


# ── Query helper tests ───────────────────────────────────────────────


def test_get_velocity_for_station_found(duck_conn):
    """Look up a station that exists."""
    duck_conn.execute(
        """INSERT INTO station_velocity_v2
           (id, station, metric_type, p25_days, p50_days, p75_days,
            p90_days, sample_count, period)
           VALUES (1, 'BLDG', 'initial', 1.0, 3.0, 7.0, 14.0, 100, 'recent_6mo')"""
    )

    from src.station_velocity_v2 import get_velocity_for_station
    result = get_velocity_for_station("BLDG", "initial", "recent_6mo", conn=duck_conn)
    assert result is not None
    assert result.station == "BLDG"
    assert result.p50_days == 3.0
    assert result.sample_count == 100


def test_get_velocity_for_station_not_found(duck_conn):
    """Look up a station that doesn't exist returns None."""
    from src.station_velocity_v2 import get_velocity_for_station
    result = get_velocity_for_station("ZZNONEXISTENT", conn=duck_conn)
    assert result is None


def test_get_velocity_for_station_fallback_to_all(duck_conn):
    """Falls back to 'all' period when requested period has no data."""
    duck_conn.execute(
        """INSERT INTO station_velocity_v2
           (id, station, metric_type, p25_days, p50_days, p75_days,
            p90_days, sample_count, period)
           VALUES (1, 'BLDG', 'initial', 2.0, 5.0, 10.0, 20.0, 500, 'all')"""
    )

    from src.station_velocity_v2 import get_velocity_for_station
    # Request recent_6mo which doesn't exist — should fall back to all
    result = get_velocity_for_station("BLDG", "initial", "recent_6mo", conn=duck_conn)
    assert result is not None
    assert result.period == "all"
    assert result.p50_days == 5.0


def test_get_all_velocities(duck_conn):
    """Returns all rows for a given period."""
    duck_conn.execute(
        """INSERT INTO station_velocity_v2
           (id, station, metric_type, p25_days, p50_days, p75_days,
            p90_days, sample_count, period) VALUES
           (1, 'BLDG', 'initial', 1.0, 3.0, 7.0, 14.0, 100, 'recent_6mo'),
           (2, 'SFFD', 'initial', 10.0, 20.0, 35.0, 60.0, 80, 'recent_6mo'),
           (3, 'CPB', 'initial', 0.0, 1.0, 3.0, 5.0, 200, 'recent_6mo'),
           (4, 'BLDG', 'revision', 5.0, 10.0, 20.0, 30.0, 50, 'recent_6mo')"""
    )

    from src.station_velocity_v2 import get_all_velocities
    results = get_all_velocities("recent_6mo", conn=duck_conn)
    assert len(results) == 4

    # Filter by metric_type
    initial_only = get_all_velocities("recent_6mo", metric_type="initial", conn=duck_conn)
    assert len(initial_only) == 3
    assert all(r.metric_type == "initial" for r in initial_only)


def test_get_all_velocities_sorted_by_p50(duck_conn):
    """Results are sorted by p50_days descending."""
    duck_conn.execute(
        """INSERT INTO station_velocity_v2
           (id, station, metric_type, p25_days, p50_days, p75_days,
            p90_days, sample_count, period) VALUES
           (1, 'FAST', 'initial', 0.0, 1.0, 3.0, 5.0, 100, 'all'),
           (2, 'SLOW', 'initial', 10.0, 30.0, 50.0, 90.0, 80, 'all'),
           (3, 'MED', 'initial', 3.0, 7.0, 15.0, 25.0, 120, 'all')"""
    )

    from src.station_velocity_v2 import get_all_velocities
    results = get_all_velocities("all", metric_type="initial", conn=duck_conn)
    p50s = [r.p50_days for r in results]
    assert p50s == sorted(p50s, reverse=True)


def test_get_all_velocities_empty(duck_conn):
    """Returns empty list when no data for period."""
    from src.station_velocity_v2 import get_all_velocities
    results = get_all_velocities("2026", conn=duck_conn)
    assert results == []


# ── estimate_timeline v2 integration tests ───────────────────────────


@pytest.mark.asyncio
async def test_estimate_timeline_imports():
    """estimate_timeline still imports and runs without v2 table."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline("alterations")
    assert isinstance(result, str)
    assert "Timeline Estimate" in result


@pytest.mark.asyncio
async def test_estimate_timeline_with_triggers():
    """Triggers produce delay factor output."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline(
        "alterations",
        triggers=["fire_review", "historic"],
    )
    assert "Fire Department" in result or "fire_review" in result
    assert "Historic" in result or "historic" in result


@pytest.mark.asyncio
async def test_estimate_timeline_otc_path():
    """OTC review path produces OTC-specific output."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline("otc", review_path="otc")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_estimate_timeline_with_cost():
    """Cost bracket is shown when estimated_cost is provided."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline("alterations", estimated_cost=200000.0)
    assert "150k_500k" in result or "Cost Bracket" in result


@pytest.mark.asyncio
async def test_estimate_timeline_with_neighborhood():
    """Neighborhood is shown in output."""
    from src.tools.estimate_timeline import estimate_timeline
    result = await estimate_timeline("alterations", neighborhood="Mission")
    assert "Mission" in result


def test_format_days():
    """_format_days produces human-readable strings."""
    from src.tools.estimate_timeline import _format_days
    assert _format_days(None) == "—"
    assert _format_days(0.5) == "<1 day"
    assert _format_days(3) == "3 days"
    assert _format_days(14) == "2 wk"
    assert "mo" in _format_days(45)


def test_format_station_velocity_empty():
    """Empty station data produces empty list."""
    from src.tools.estimate_timeline import _format_station_table
    assert _format_station_table([], {}) == []


def test_format_station_velocity_with_data():
    """Station velocity data produces markdown table."""
    from src.tools.estimate_timeline import _format_station_table
    data = [{
        "station": "BLDG",
        "p25_days": 1.0,
        "p50_days": 3.0,
        "p75_days": 7.0,
        "p90_days": 14.0,
        "sample_count": 100,
        "period": "current",
    }]
    lines = _format_station_table(data, {})
    text = "\n".join(lines)
    assert "BLDG" in text
    assert "Station" in text
    assert "Median" in text


def test_trigger_station_map():
    """TRIGGER_STATION_MAP has expected entries."""
    from src.tools.estimate_timeline import TRIGGER_STATION_MAP
    assert "planning_review" in TRIGGER_STATION_MAP
    assert "CP-ZOC" in TRIGGER_STATION_MAP["planning_review"]
    assert "fire_review" in TRIGGER_STATION_MAP
    assert "SFFD" in TRIGGER_STATION_MAP["fire_review"]


def test_cost_bracket():
    """_cost_bracket correctly maps costs to brackets."""
    from src.tools.estimate_timeline import _cost_bracket
    assert _cost_bracket(None) is None
    assert _cost_bracket(0) is None
    assert _cost_bracket(10000) == "under_50k"
    assert _cost_bracket(49999) == "under_50k"
    assert _cost_bracket(50000) == "50k_150k"
    assert _cost_bracket(149999) == "50k_150k"
    assert _cost_bracket(150000) == "150k_500k"
    assert _cost_bracket(499999) == "150k_500k"
    assert _cost_bracket(500000) == "over_500k"


# ── Cron endpoint test ───────────────────────────────────────────────


def test_cron_velocity_refresh_blocked_on_web_worker():
    """Cron endpoint blocked on web workers by cron guard."""
    from web.app import app
    with app.test_client() as client:
        rv = client.post("/cron/velocity-refresh")
        assert rv.status_code == 404  # Cron guard blocks POST /cron/* on web workers


def test_cron_velocity_refresh_route_exists():
    """Cron endpoint is registered."""
    from web.app import app
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert "/cron/velocity-refresh" in rules
