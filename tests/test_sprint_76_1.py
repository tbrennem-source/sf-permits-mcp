"""Tests for Sprint 76-1: Station Routing Sequence Model.

Tests estimate_sequence_timeline() and GET /api/timeline/<permit_number>.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────


def _make_conn(addenda_rows=None, velocity_rows=None, v2_exists=True):
    """Create a mock DuckDB-style connection.

    addenda_rows: list of (station, first_arrive, last_finish) tuples
    velocity_rows: list of (station, p50_days, p25_days, p75_days, p90_days, sample_count, period)
    v2_exists: whether station_velocity_v2 table exists
    """
    conn = MagicMock()

    call_count = [0]

    def _execute(sql, params=None):
        result = MagicMock()

        # Table existence check
        if "SELECT 1 FROM station_velocity_v2" in sql:
            if not v2_exists:
                raise Exception("table not found")
            result.fetchall.return_value = [(1,)]
            result.fetchone.return_value = (1,)
            return result

        # Addenda query
        if "FROM addenda" in sql:
            result.fetchall.return_value = addenda_rows or []
            return result

        # Velocity query
        if "FROM station_velocity_v2" in sql:
            result.fetchall.return_value = velocity_rows or []
            return result

        result.fetchall.return_value = []
        result.fetchone.return_value = None
        return result

    conn.execute.side_effect = _execute
    return conn


# ── Unit tests for estimate_sequence_timeline ─────────────────────


class TestEstimateSequenceTimeline:
    """Tests for the core estimate_sequence_timeline function."""

    def test_returns_none_when_no_addenda(self):
        """Return None when the permit has no addenda records."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        conn = _make_conn(addenda_rows=[])
        result = estimate_sequence_timeline("202200000001", conn=conn)
        assert result is None

    def test_basic_structure_returned(self):
        """Result dict has required keys."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [("BLDG", "2024-01-10", "2024-02-10")]
        velocity = [("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current")]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000001", conn=conn)

        assert result is not None
        assert result["permit_number"] == "202200000001"
        assert "stations" in result
        assert "total_estimate_days" in result
        assert "confidence" in result

    def test_single_station_with_velocity(self):
        """Single station: total = that station's p50."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [("BLDG", "2024-01-10", "2024-02-10")]
        velocity = [("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current")]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000001", conn=conn)

        assert result["total_estimate_days"] == 30.0
        assert len(result["stations"]) == 1
        assert result["stations"][0]["station"] == "BLDG"
        assert result["stations"][0]["p50_days"] == 30.0

    def test_sequential_stations_summed(self):
        """Sequential stations: total = sum of p50s."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [
            ("BLDG", "2024-01-10", "2024-02-10"),
            ("CP-ZOC", "2024-02-11", "2024-03-11"),
        ]
        velocity = [
            ("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current"),
            ("CP-ZOC", 20.0, 15.0, 30.0, 45.0, 200, "current"),
        ]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000002", conn=conn)

        # 30 + 20 = 50
        assert result["total_estimate_days"] == 50.0

    def test_parallel_stations_use_max(self):
        """Parallel stations (same arrive date): total = max p50."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        # Same arrive date → parallel
        addenda = [
            ("BLDG", "2024-01-10", "2024-02-10"),
            ("SFFD", "2024-01-10", "2024-01-25"),  # parallel with BLDG
        ]
        velocity = [
            ("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current"),
            ("SFFD", 15.0, 10.0, 20.0, 30.0, 100, "current"),
        ]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000003", conn=conn)

        # max(30, 15) = 30 — only one group (both parallel)
        assert result["total_estimate_days"] == 30.0

    def test_missing_velocity_station_skipped(self):
        """Station with no velocity data is skipped with note in result."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [
            ("BLDG", "2024-01-10", "2024-02-10"),
            ("UNKNOWN-AGENCY", "2024-02-11", None),
        ]
        velocity = [
            ("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current"),
            # No velocity for UNKNOWN-AGENCY
        ]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000004", conn=conn)

        assert result is not None
        # Only BLDG contributed
        assert result["total_estimate_days"] == 30.0
        assert "skipped_stations" in result
        assert "UNKNOWN-AGENCY" in result["skipped_stations"]

    def test_station_status_done(self):
        """Station with finish_date gets status='done'."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [("BLDG", "2024-01-10", "2024-02-10")]
        velocity = [("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current")]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000005", conn=conn)

        assert result["stations"][0]["status"] == "done"

    def test_station_status_stalled(self):
        """Station with arrive but no finish_date gets status='stalled'."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [("BLDG", "2024-01-10", None)]
        velocity = [("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current")]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000006", conn=conn)

        assert result["stations"][0]["status"] == "stalled"

    def test_no_velocity_table_still_returns_structure(self):
        """When station_velocity_v2 doesn't exist, returns result with low confidence."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [("BLDG", "2024-01-10", "2024-02-10")]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=[], v2_exists=False)
        result = estimate_sequence_timeline("202200000007", conn=conn)

        # Returns structure even without velocity
        assert result is not None
        assert result["permit_number"] == "202200000007"
        assert result["confidence"] == "low"
        assert result["total_estimate_days"] == 0.0

    def test_high_confidence_all_stations_have_velocity(self):
        """High confidence when all stations have velocity data."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [
            ("BLDG", "2024-01-10", "2024-02-10"),
            ("CP-ZOC", "2024-02-11", "2024-03-11"),
        ]
        velocity = [
            ("BLDG", 30.0, 20.0, 45.0, 60.0, 500, "current"),
            ("CP-ZOC", 20.0, 15.0, 30.0, 45.0, 200, "current"),
        ]

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000008", conn=conn)

        assert result["confidence"] == "high"

    def test_low_confidence_no_velocity_matches(self):
        """Low confidence when no station has velocity data."""
        from src.tools.estimate_timeline import estimate_sequence_timeline

        addenda = [
            ("RARE-STA-1", "2024-01-10", "2024-02-10"),
            ("RARE-STA-2", "2024-02-11", "2024-03-11"),
        ]
        velocity = []  # No matches

        conn = _make_conn(addenda_rows=addenda, velocity_rows=velocity)
        result = estimate_sequence_timeline("202200000009", conn=conn)

        assert result["confidence"] == "low"
        assert result["total_estimate_days"] == 0.0


# ── API endpoint tests ─────────────────────────────────────────────


class TestApiTimelineEndpoint:
    """Tests for GET /api/timeline/<permit_number>."""

    @pytest.fixture
    def client(self):
        from web.app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_returns_404_when_no_addenda(self, client):
        """Returns 404 with error message when permit has no addenda."""
        with patch("src.tools.estimate_timeline.estimate_sequence_timeline", return_value=None):
            resp = client.get("/api/timeline/202200000000")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "no addenda found"
        assert data["permit_number"] == "202200000000"

    def test_returns_200_with_valid_permit(self, client):
        """Returns 200 with structured result for permit with addenda."""
        mock_result = {
            "permit_number": "202200000001",
            "stations": [
                {"station": "BLDG", "p50_days": 30.0, "status": "done",
                 "is_parallel": False, "first_arrive": "2024-01-10", "last_finish": "2024-02-10"}
            ],
            "total_estimate_days": 30.0,
            "confidence": "high",
        }
        with patch("src.tools.estimate_timeline.estimate_sequence_timeline", return_value=mock_result):
            resp = client.get("/api/timeline/202200000001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["permit_number"] == "202200000001"
        assert data["total_estimate_days"] == 30.0
        assert data["confidence"] == "high"
        assert len(data["stations"]) == 1

    def test_returns_json_content_type(self, client):
        """Response is always JSON."""
        mock_result = {
            "permit_number": "202200000002",
            "stations": [],
            "total_estimate_days": 0.0,
            "confidence": "low",
        }
        with patch("src.tools.estimate_timeline.estimate_sequence_timeline", return_value=mock_result):
            resp = client.get("/api/timeline/202200000002")
        assert "application/json" in resp.content_type

    def test_returns_500_on_internal_error(self, client):
        """Returns 500 when estimate_sequence_timeline raises exception."""
        with patch("src.tools.estimate_timeline.estimate_sequence_timeline", side_effect=RuntimeError("db error")):
            resp = client.get("/api/timeline/202200000003")
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error"] == "internal error"
