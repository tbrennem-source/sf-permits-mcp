"""Tests for Sprint 65-B: _query_dbi_metrics helper in estimate_timeline."""

import pytest
import duckdb

import src.db as db_mod
from src.db import init_schema


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_65b.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    conn = db_mod.get_connection()
    try:
        init_schema(conn)
    finally:
        conn.close()


def _get_conn():
    return db_mod.get_connection()


def _seed_issuance_metrics(conn, n=20, otc_ih="OTC"):
    """Insert n fake permit issuance metrics."""
    for i in range(n):
        conn.execute(
            "INSERT INTO permit_issuance_metrics "
            "(id, bpa, otc_ih, status, issued_year, calendar_days, business_days) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [i + 1, f"BPA-{i:04d}", otc_ih, "issued", "2024", 5 + i, 3 + i],
        )


def _seed_review_metrics(conn, n=10, station="BLDG"):
    """Insert n fake permit review metrics."""
    for i in range(n):
        conn.execute(
            "INSERT INTO permit_review_metrics "
            "(id, bpa, station, department, calendar_days, met_cal_sla) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [i + 1, f"BPA-{i:04d}", station, "DBI", 10.0 + i, i % 2 == 0],
        )


def _seed_planning_metrics(conn, n=10, stage="completeness check"):
    """Insert n fake planning review metrics."""
    for i in range(n):
        conn.execute(
            "INSERT INTO planning_review_metrics "
            "(id, b1_alt_id, project_stage, metric_value, sla_value, metric_outcome) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [i + 1, f"PRJ-{i:04d}", stage, 15.0 + i, 21.0,
             "Under Deadline" if (15 + i) <= 21 else "Over Deadline"],
        )


# ── Tests ─────────────────────────────────────────────────────────


class TestQueryDbiMetrics:
    def test_returns_none_on_empty_tables(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            result = _query_dbi_metrics(conn)
            assert result is None
        finally:
            conn.close()

    def test_issuance_metrics_included(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_issuance_metrics(conn, n=20)
            result = _query_dbi_metrics(conn)
            assert result is not None
            assert "DBI Processing Metrics" in result
            assert "Permit Issuance" in result
            assert "cal days" in result
        finally:
            conn.close()

    def test_review_metrics_included(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_review_metrics(conn, n=10)
            result = _query_dbi_metrics(conn)
            assert result is not None
            assert "Review Times by Station" in result
            assert "BLDG" in result
        finally:
            conn.close()

    def test_planning_metrics_included(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_planning_metrics(conn, n=10)
            result = _query_dbi_metrics(conn)
            assert result is not None
            assert "Planning Review Times" in result
            assert "completeness check" in result
        finally:
            conn.close()

    def test_all_three_sections(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_issuance_metrics(conn, n=20)
            _seed_review_metrics(conn, n=10)
            _seed_planning_metrics(conn, n=10)
            result = _query_dbi_metrics(conn)
            assert "Permit Issuance" in result
            assert "Review Times by Station" in result
            assert "Planning Review Times" in result
        finally:
            conn.close()

    def test_otc_filter(self):
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_issuance_metrics(conn, n=10, otc_ih="OTC")
            # Add some IH records with different id range
            for i in range(10):
                conn.execute(
                    "INSERT INTO permit_issuance_metrics "
                    "(id, bpa, otc_ih, status, issued_year, calendar_days, business_days) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [100 + i, f"IH-{i:04d}", "IH", "issued", "2024", 50 + i, 30 + i],
                )

            result_otc = _query_dbi_metrics(conn, permit_type="otc")
            result_ih = _query_dbi_metrics(conn, permit_type="alterations")

            # Both should return data
            assert result_otc is not None
            assert result_ih is not None
            assert "Permit Issuance" in result_otc
            assert "Permit Issuance" in result_ih
        finally:
            conn.close()

    def test_insufficient_data_skips_section(self):
        """Tables with < 5 records are skipped."""
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            # Only 3 records — below threshold
            _seed_issuance_metrics(conn, n=3)
            result = _query_dbi_metrics(conn)
            # With only issuance and < 5 records, should be None
            assert result is None
        finally:
            conn.close()

    def test_review_sla_percentage(self):
        """Review metrics include SLA met percentage."""
        from src.tools.estimate_timeline import _query_dbi_metrics
        conn = _get_conn()
        try:
            _seed_review_metrics(conn, n=10)
            result = _query_dbi_metrics(conn)
            assert "SLA Met %" in result
            assert "%" in result
        finally:
            conn.close()


class TestDbiMetricsIntegration:
    """Test that _query_dbi_metrics output appears in estimate_timeline."""

    @pytest.fixture(autouse=True)
    def _patch_connection(self, monkeypatch):
        """Patch get_connection in the timeline module."""
        import src.tools.estimate_timeline as timeline_mod

        original_get_connection = timeline_mod.get_connection

        def patched_get_connection(db_path=None):
            return original_get_connection()

        monkeypatch.setattr(timeline_mod, "get_connection", patched_get_connection)

    def _seed_permits_and_metrics(self):
        """Seed enough data for both timeline + DBI metrics."""
        from datetime import date, timedelta
        conn = _get_conn()
        try:
            # Seed permits for timeline_stats
            for i in range(30):
                filed = date(2024, 6, 1) + timedelta(days=i)
                issued = filed + timedelta(days=20 + i % 50)
                completed = issued + timedelta(days=30)
                conn.execute(
                    "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"TL65-{i:04d}", "1", "additions alterations or repairs",
                        "complete", str(completed), f"Test #{i}",
                        str(filed), str(issued), str(filed + timedelta(days=18)),
                        str(completed), 80000 + i * 1000, None,
                        "office", "office", None, None,
                        str(100 + i), "MARKET", "ST", "94110",
                        "Mission", "9", "3512", str(i).zfill(3), None, str(filed),
                    ),
                )

            # Seed DBI metrics
            _seed_issuance_metrics(conn, n=20)
            _seed_review_metrics(conn, n=10)
            _seed_planning_metrics(conn, n=10)
        finally:
            conn.close()

    @pytest.mark.asyncio
    async def test_dbi_metrics_appear_in_output(self):
        """DBI metrics section appears in estimate_timeline output."""
        self._seed_permits_and_metrics()
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(permit_type="alterations")
        assert "DBI Processing Metrics" in result

    @pytest.mark.asyncio
    async def test_dbi_metrics_below_station_velocity(self):
        """DBI metrics section appears after main timeline sections."""
        self._seed_permits_and_metrics()
        from src.tools.estimate_timeline import estimate_timeline
        result = await estimate_timeline(permit_type="alterations")
        # DBI section should come after the timeline/coverage sections
        timeline_idx = result.find("Timeline Estimate")
        dbi_idx = result.find("DBI Processing Metrics")
        if dbi_idx > -1:
            assert dbi_idx > timeline_idx
