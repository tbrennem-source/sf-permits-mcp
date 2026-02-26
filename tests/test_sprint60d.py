"""Tests for Sprint 60D — Station Congestion Signal."""
import pytest
from unittest.mock import patch, MagicMock


class TestCongestionLabel:
    def test_low_queue_always_normal(self):
        """Stations with < 3 pending are always 'normal'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(2.0, 2) == "normal"
        assert _congestion_label(3.0, 1) == "normal"

    def test_congested_threshold(self):
        """ratio > 1.5 → 'congested'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(1.6, 10) == "congested"
        assert _congestion_label(2.0, 5) == "congested"

    def test_busy_threshold(self):
        """ratio > 1.15 and <= 1.5 → 'busy'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(1.3, 10) == "busy"
        assert _congestion_label(1.16, 5) == "busy"
        # Exactly 1.15 is NOT > 1.15, so it falls through to 'normal'
        assert _congestion_label(1.15, 5) == "normal"

    def test_clearing_threshold(self):
        """ratio < 0.7 → 'clearing'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(0.5, 5) == "clearing"
        assert _congestion_label(0.1, 10) == "clearing"

    def test_normal_in_range(self):
        """0.7 <= ratio <= 1.15 → 'normal'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(1.0, 10) == "normal"
        assert _congestion_label(0.9, 5) == "normal"
        assert _congestion_label(0.7, 8) == "normal"

    def test_none_ratio_is_normal(self):
        """None ratio with sufficient queue → 'normal'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(None, 10) == "normal"
        assert _congestion_label(None, 100) == "normal"

    def test_boundary_at_exactly_1_5(self):
        """ratio == 1.5 is NOT > 1.5, so it is 'busy'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(1.5, 10) == "busy"

    def test_boundary_at_exactly_0_7(self):
        """ratio == 0.7 is NOT < 0.7, so it is 'normal'."""
        from web.station_velocity import _congestion_label
        assert _congestion_label(0.7, 10) == "normal"


class TestCongestionRefresh:
    @patch("web.station_velocity.BACKEND", "duckdb")
    def test_skips_on_duckdb(self):
        """Refresh skips on DuckDB (returns 0)."""
        from web.station_velocity import refresh_station_congestion
        result = refresh_station_congestion()
        assert result["congestion_stations"] == 0

    @patch("web.station_velocity.execute_write")
    @patch("web.station_velocity.query")
    @patch("web.station_velocity.BACKEND", "postgres")
    def test_refresh_returns_empty_when_no_current_queue(self, mock_query, mock_write):
        """Returns 0 stations when current queue is empty."""
        # First call = ensure_station_congestion_table (execute_write for DDL)
        # Subsequent calls = _compute_current_queue and _compute_baseline_queue
        mock_query.return_value = []  # empty current queue
        from web.station_velocity import refresh_station_congestion
        result = refresh_station_congestion()
        assert result["congestion_stations"] == 0

    @patch("web.station_velocity.execute_write")
    @patch("web.station_velocity.query")
    @patch("web.station_velocity.BACKEND", "postgres")
    def test_refresh_upserts_stations(self, mock_query, mock_write):
        """Refresh upserts one row per station and returns correct count."""
        # _compute_current_queue returns 2 stations
        # _compute_baseline_queue returns empty (no baseline)
        mock_query.side_effect = [
            [("BLDG", 45), ("SFFD", 20)],  # current queue
            [],  # baseline queue (empty)
        ]
        from web.station_velocity import refresh_station_congestion
        result = refresh_station_congestion()
        # Should have upserted 2 stations
        assert result["congestion_stations"] == 2
        # execute_write should have been called: once for table create + twice for upserts
        assert mock_write.call_count >= 2


class TestGetStationCongestion:
    @patch("web.station_velocity.query")
    @patch("web.station_velocity.BACKEND", "postgres")
    def test_returns_dict_keyed_by_station(self, mock_query):
        """Returns dict keyed by station with correct fields."""
        mock_query.return_value = [
            ("BLDG", 45, 30.0, 1.5, "busy"),
            ("SFFD", 20, 15.0, 1.33, "busy"),
        ]
        from web.station_velocity import get_station_congestion
        result = get_station_congestion()
        assert "BLDG" in result
        assert result["BLDG"]["current_queue"] == 45
        assert result["BLDG"]["baseline_avg"] == 30.0
        assert result["BLDG"]["ratio"] == 1.5
        assert result["BLDG"]["label"] == "busy"
        assert "SFFD" in result

    @patch("web.station_velocity.query")
    @patch("web.station_velocity.BACKEND", "postgres")
    def test_handles_none_values(self, mock_query):
        """None ratio/baseline_avg are preserved as None."""
        mock_query.return_value = [
            ("BLDG", 5, None, None, "normal"),
        ]
        from web.station_velocity import get_station_congestion
        result = get_station_congestion()
        assert result["BLDG"]["baseline_avg"] is None
        assert result["BLDG"]["ratio"] is None
        assert result["BLDG"]["label"] == "normal"

    @patch("web.station_velocity.query")
    @patch("web.station_velocity.BACKEND", "postgres")
    def test_query_exception_returns_empty(self, mock_query):
        """Exception during query returns empty dict (not a crash)."""
        mock_query.side_effect = Exception("DB unavailable")
        from web.station_velocity import get_station_congestion
        result = get_station_congestion()
        assert result == {}

    @patch("web.station_velocity._compute_current_queue")
    @patch("web.station_velocity.BACKEND", "duckdb")
    def test_duckdb_computes_live(self, mock_current):
        """DuckDB mode computes live queue (no table read)."""
        mock_current.return_value = {"BLDG": 10, "SFFD": 5}
        from web.station_velocity import get_station_congestion
        result = get_station_congestion()
        assert "BLDG" in result
        assert result["BLDG"]["current_queue"] == 10
        assert result["BLDG"]["label"] == "normal"  # DuckDB always normal
        assert result["BLDG"]["ratio"] is None


class TestComputeCurrentQueue:
    @patch("web.station_velocity.query")
    def test_returns_station_count_dict(self, mock_query):
        """_compute_current_queue returns {station: count} mapping."""
        mock_query.return_value = [("BLDG", 100), ("SFFD", 50)]
        from web.station_velocity import _compute_current_queue
        result = _compute_current_queue()
        assert result == {"BLDG": 100, "SFFD": 50}

    @patch("web.station_velocity.query")
    def test_returns_empty_on_exception(self, mock_query):
        """Exception returns empty dict."""
        mock_query.side_effect = Exception("connection error")
        from web.station_velocity import _compute_current_queue
        result = _compute_current_queue()
        assert result == {}
