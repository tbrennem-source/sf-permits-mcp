"""Tests for predict_next_stations tool (QS8-T2-A).

Tests are written against src.tools.predict_next_stations, which provides the
async MCP-facing predict_next_stations() function.

All tests mock the DB connection so no live database is required.
"""
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from src.tools.predict_next_stations import (
    _compute_dwell_days,
    _compute_top_predictions,
    _find_current_station,
    _format_days,
    _format_output,
    _get_permit_info,
    _get_station_history,
    _label,
    predict_next_stations,
    STALL_THRESHOLD_DAYS,
    MIN_TRANSITION_SAMPLES,
)


# ── Unit tests: pure functions ──────────────────────────────────────


class TestFormatDays:
    def test_none(self):
        assert _format_days(None) == "—"

    def test_zero(self):
        result = _format_days(0)
        assert "day" in result or result == "<1 day"

    def test_less_than_1(self):
        assert _format_days(0.5) == "<1 day"

    def test_single_digit_days(self):
        assert _format_days(3) == "3 days"

    def test_one_week(self):
        assert "wk" in _format_days(7)

    def test_one_month(self):
        result = _format_days(30)
        assert "mo" in result

    def test_large_value(self):
        result = _format_days(90)
        assert "mo" in result


class TestLabel:
    def test_known_station(self):
        assert "Planning" in _label("CP-ZOC")
        assert "Fire" in _label("SFFD")
        assert "Building" in _label("BLDG")

    def test_unknown_station(self):
        # Unknown stations return the code itself
        assert _label("ZZZUNK") == "ZZZUNK"


class TestFindCurrentStation:
    def test_empty_history(self):
        assert _find_current_station([]) is None

    def test_all_finished(self):
        history = [
            {"station": "BLDG", "arrive": "2024-01-01", "finish_date": "2024-02-01"},
            {"station": "SFFD", "arrive": "2024-02-01", "finish_date": "2024-03-01"},
        ]
        assert _find_current_station(history) is None

    def test_one_unfinished(self):
        history = [
            {"station": "BLDG", "arrive": "2024-01-01", "finish_date": "2024-02-01"},
            {"station": "SFFD", "arrive": "2024-02-01", "finish_date": None},
        ]
        result = _find_current_station(history)
        assert result is not None
        assert result["station"] == "SFFD"

    def test_multiple_unfinished_returns_latest(self):
        history = [
            {"station": "BLDG", "arrive": "2024-01-01", "finish_date": None},
            {"station": "SFFD", "arrive": "2024-03-01", "finish_date": None},
        ]
        result = _find_current_station(history)
        # Should return the one with later arrive date
        assert result["station"] == "SFFD"

    def test_no_arrive_date_skipped(self):
        history = [
            {"station": "BLDG", "arrive": None, "finish_date": None},
            {"station": "SFFD", "arrive": "2024-03-01", "finish_date": None},
        ]
        result = _find_current_station(history)
        assert result["station"] == "SFFD"


class TestComputeDwellDays:
    def test_no_arrive(self):
        assert _compute_dwell_days({"arrive": None}) is None

    def test_recent_arrive(self):
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = _compute_dwell_days({"arrive": yesterday})
        assert result == 1

    def test_old_arrive(self):
        from datetime import date, timedelta
        old_date = (date.today() - timedelta(days=90)).isoformat()
        result = _compute_dwell_days({"arrive": old_date})
        assert result == 90

    def test_arrive_with_timestamp(self):
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=5)).isoformat()
        # Timestamp format with time component
        result = _compute_dwell_days({"arrive": f"{yesterday} 12:00:00"})
        assert result == 5


class TestComputeTopPredictions:
    def _make_conn_with_no_velocity(self):
        """Return a mock connection that returns no velocity data."""
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        return conn

    def test_no_current_station_in_transitions(self):
        conn = self._make_conn_with_no_velocity()
        result = _compute_top_predictions("BLDG", {}, conn)
        assert result == []

    def test_all_below_min_samples(self):
        conn = self._make_conn_with_no_velocity()
        transitions = {"BLDG": {"SFFD": MIN_TRANSITION_SAMPLES - 1, "CP-ZOC": 1}}
        result = _compute_top_predictions("BLDG", transitions, conn)
        assert result == []

    def test_returns_top_n(self):
        conn = self._make_conn_with_no_velocity()
        transitions = {
            "BLDG": {
                "SFFD": 50,
                "CP-ZOC": 30,
                "HEALTH": 20,
                "HIS": 10,
            }
        }
        result = _compute_top_predictions("BLDG", transitions, conn, top_n=3)
        assert len(result) <= 3

    def test_probabilities_sum_to_approx_one(self):
        conn = self._make_conn_with_no_velocity()
        transitions = {
            "BLDG": {
                "SFFD": 60,
                "CP-ZOC": 40,
            }
        }
        result = _compute_top_predictions("BLDG", transitions, conn)
        total_prob = sum(p["probability"] for p in result)
        # All transitions qualify, so they should sum to ~1.0
        assert abs(total_prob - 1.0) < 0.01

    def test_sorted_by_probability_descending(self):
        conn = self._make_conn_with_no_velocity()
        transitions = {
            "BLDG": {
                "SFFD": 70,
                "CP-ZOC": 30,
            }
        }
        result = _compute_top_predictions("BLDG", transitions, conn)
        if len(result) >= 2:
            assert result[0]["probability"] >= result[1]["probability"]

    def test_prediction_includes_label(self):
        conn = self._make_conn_with_no_velocity()
        transitions = {"BLDG": {"SFFD": 50}}
        result = _compute_top_predictions("BLDG", transitions, conn)
        if result:
            assert "label" in result[0]
            assert "Fire" in result[0]["label"]


class TestFormatOutput:
    """Test the markdown formatter for various states."""

    def _base_permit_info(self):
        return {
            "permit_number": "202201234567",
            "permit_type": "Alterations",
            "neighborhood": "Mission",
            "status": "active",
            "filed_date": "2022-01-01",
            "issued_date": None,
            "completed_date": None,
        }

    def test_no_history(self):
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=[],
            current=None,
            predictions=[],
            transitions={},
            neighborhood_filtered=False,
        )
        assert "No routing data" in output

    def test_all_finished_stations(self):
        history = [
            {"station": "BLDG", "arrive": "2024-01-01", "finish_date": "2024-02-01"},
        ]
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=None,
            predictions=[],
            transitions={},
            neighborhood_filtered=False,
        )
        assert "All tracked review stations have finished" in output

    def test_current_station_shown(self):
        from datetime import date, timedelta
        arrive = (date.today() - timedelta(days=10)).isoformat()
        history = [
            {"station": "SFFD", "arrive": arrive, "finish_date": None},
        ]
        current = {"station": "SFFD", "arrive": arrive, "finish_date": None}
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=current,
            predictions=[],
            transitions={"SFFD": {}},
            neighborhood_filtered=False,
        )
        assert "SFFD" in output
        assert "Fire" in output

    def test_stall_warning_shown(self):
        from datetime import date, timedelta
        old_arrive = (date.today() - timedelta(days=STALL_THRESHOLD_DAYS + 10)).isoformat()
        history = [
            {"station": "SFFD", "arrive": old_arrive, "finish_date": None},
        ]
        current = {"station": "SFFD", "arrive": old_arrive, "finish_date": None}
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=current,
            predictions=[],
            transitions={},
            neighborhood_filtered=False,
        )
        assert "STALLED" in output

    def test_predictions_shown_in_table(self):
        from datetime import date, timedelta
        arrive = (date.today() - timedelta(days=5)).isoformat()
        history = [{"station": "BLDG", "arrive": arrive, "finish_date": None}]
        current = {"station": "BLDG", "arrive": arrive, "finish_date": None}
        predictions = [
            {
                "station": "SFFD",
                "label": "Fire Department",
                "probability": 0.70,
                "sample_count": 70,
                "total_outbound": 100,
                "p25_days": 3.0,
                "p50_days": 5.0,
                "p75_days": 10.0,
                "p90_days": 14.0,
                "velocity_period": "current",
            }
        ]
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=current,
            predictions=predictions,
            transitions={"BLDG": {"SFFD": 70}},
            neighborhood_filtered=False,
        )
        assert "SFFD" in output
        assert "70%" in output
        assert "All-Clear" in output

    def test_all_clear_estimate_shown(self):
        from datetime import date, timedelta
        arrive = (date.today() - timedelta(days=5)).isoformat()
        history = [{"station": "BLDG", "arrive": arrive, "finish_date": None}]
        current = {"station": "BLDG", "arrive": arrive, "finish_date": None}
        predictions = [
            {
                "station": "SFFD",
                "label": "Fire Department",
                "probability": 0.80,
                "sample_count": 80,
                "total_outbound": 100,
                "p25_days": 3.0,
                "p50_days": 14.0,
                "p75_days": 21.0,
                "p90_days": 30.0,
                "velocity_period": "current",
            }
        ]
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=current,
            predictions=predictions,
            transitions={"BLDG": {"SFFD": 80}},
            neighborhood_filtered=False,
        )
        assert "All-Clear Estimate" in output
        assert "Estimated remaining time" in output

    def test_confidence_shown(self):
        from datetime import date, timedelta
        arrive = (date.today() - timedelta(days=5)).isoformat()
        history = [{"station": "BLDG", "arrive": arrive, "finish_date": None}]
        current = {"station": "BLDG", "arrive": arrive, "finish_date": None}
        predictions = [
            {
                "station": "SFFD",
                "label": "Fire Department",
                "probability": 0.50,
                "sample_count": 5,
                "total_outbound": 10,  # Low confidence
                "p25_days": None,
                "p50_days": None,
                "p75_days": None,
                "p90_days": None,
                "velocity_period": None,
            }
        ]
        output = _format_output(
            permit_number="202201234567",
            permit_info=self._base_permit_info(),
            history=history,
            current=current,
            predictions=predictions,
            transitions={"BLDG": {"SFFD": 10}},
            neighborhood_filtered=False,
        )
        assert "confidence" in output.lower()


# ── Integration-style tests: async predict_next_stations ──────────


def _make_mock_conn():
    """Build a MagicMock connection that simulates DuckDB-style .execute().fetchone/all."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


def _setup_execute(conn, responses: dict):
    """Configure conn.execute() to return different results based on SQL keyword.

    responses: {keyword_in_sql: return_value}
    Default fallback: empty list / None.
    """
    def _execute(sql, params=None):
        mock_result = MagicMock()
        for keyword, value in responses.items():
            if keyword.lower() in sql.lower():
                if isinstance(value, list):
                    mock_result.fetchall.return_value = value
                    mock_result.fetchone.return_value = value[0] if value else None
                else:
                    mock_result.fetchone.return_value = value
                    mock_result.fetchall.return_value = [value] if value else []
                return mock_result
        # Default: empty
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = None
        return mock_result

    conn.execute = MagicMock(side_effect=_execute)
    return conn


class TestPredictNextStationsAsync:
    """Integration-style tests for the async predict_next_stations function."""

    def _run(self, coro):
        """Run an async coroutine synchronously for testing."""
        return asyncio.run(coro)

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_permit_not_found(self, mock_get_conn):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("NOTFOUND123"))
        assert "not found" in result.lower() or "No permit found" in result

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_permit_already_complete(self, mock_get_conn):
        conn = MagicMock()

        def _execute(sql, params=None):
            mock_result = MagicMock()
            if "permits" in sql.lower():
                # Return a complete permit
                mock_result.fetchone.return_value = (
                    "202201234567", "Alterations", "Mission",
                    "complete", "2022-01-01", "2023-01-01", "2023-06-01"
                )
            else:
                mock_result.fetchone.return_value = None
                mock_result.fetchall.return_value = []
            return mock_result

        conn.execute = MagicMock(side_effect=_execute)
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert "completed all review stations" in result.lower() or "complete" in result.lower()

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_no_addenda_data(self, mock_get_conn):
        conn = MagicMock()

        def _execute(sql, params=None):
            mock_result = MagicMock()
            if "permits" in sql.lower() and "permit_number" in sql.lower():
                # Active permit
                mock_result.fetchone.return_value = (
                    "202201234567", "Alterations", "Mission",
                    "active", "2022-01-01", None, None
                )
            else:
                # No addenda data
                mock_result.fetchone.return_value = None
                mock_result.fetchall.return_value = []
            return mock_result

        conn.execute = MagicMock(side_effect=_execute)
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert "No routing data" in result

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_in_progress_permit_shows_current_station(self, mock_get_conn):
        from datetime import date, timedelta
        arrive_date = (date.today() - timedelta(days=15)).isoformat()

        conn = MagicMock()
        call_count = [0]

        def _execute(sql, params=None):
            mock_result = MagicMock()
            call_count[0] += 1

            # Permit info query
            if "permit_number" in sql.lower() and "status" in sql.lower():
                mock_result.fetchone.return_value = (
                    "202201234567", "Alterations", "Mission",
                    "active", "2022-01-01", None, None
                )
            # Addenda history query
            elif "ranked" in sql.lower() and "addenda_number" in sql.lower():
                mock_result.fetchall.return_value = [
                    ("BLDG", "2024-01-01", "2024-02-01", None, 0),
                    ("SFFD", arrive_date, None, None, 0),
                ]
            else:
                mock_result.fetchone.return_value = None
                mock_result.fetchall.return_value = []
            return mock_result

        conn.execute = MagicMock(side_effect=_execute)
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert "202201234567" in result
        assert "SFFD" in result

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_stalled_permit_shows_warning(self, mock_get_conn):
        from datetime import date, timedelta
        old_arrive = (date.today() - timedelta(days=STALL_THRESHOLD_DAYS + 20)).isoformat()

        conn = MagicMock()

        def _execute(sql, params=None):
            mock_result = MagicMock()
            if "permit_number" in sql.lower() and "status" in sql.lower():
                mock_result.fetchone.return_value = (
                    "202201234567", "Alterations", "Mission",
                    "active", "2022-01-01", None, None
                )
            elif "ranked" in sql.lower() and "addenda_number" in sql.lower():
                mock_result.fetchall.return_value = [
                    ("SFFD", old_arrive, None, None, 0),
                ]
            else:
                mock_result.fetchone.return_value = None
                mock_result.fetchall.return_value = []
            return mock_result

        conn.execute = MagicMock(side_effect=_execute)
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert "STALLED" in result or "stalled" in result.lower()

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_error_handling_returns_string(self, mock_get_conn):
        """An unexpected exception should return an error message string, not raise."""
        mock_get_conn.side_effect = RuntimeError("DB unavailable")

        result = self._run(predict_next_stations("202201234567"))
        assert isinstance(result, str)
        assert "Error" in result or "error" in result.lower()

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_returns_markdown_string(self, mock_get_conn):
        """Result should always be a non-empty string (markdown)."""
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.fetchall.return_value = []
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("src.tools.predict_next_stations.get_connection")
    @patch("src.tools.predict_next_stations.BACKEND", "duckdb")
    def test_with_predictions_shows_probability_table(self, mock_get_conn):
        """When transition data exists, output includes probability table."""
        from datetime import date, timedelta
        arrive = (date.today() - timedelta(days=10)).isoformat()

        conn = MagicMock()

        def _execute(sql, params=None):
            mock_result = MagicMock()
            sql_lower = sql.lower()

            if "permit_number" in sql_lower and "status" in sql_lower:
                # Permit info
                mock_result.fetchone.return_value = (
                    "202201234567", "Alterations", "Mission",
                    "active", "2022-01-01", None, None
                )
            elif "ranked" in sql_lower and "addenda_number" in sql_lower:
                # Station history for THIS permit
                mock_result.fetchall.return_value = [
                    ("BLDG", "2024-01-01", "2024-02-01", None, 0),
                    ("SFFD", arrive, None, None, 0),
                ]
            elif "permit_number from permits" in sql_lower or ("permit_type_definition" in sql_lower and "limit 5000" in sql_lower):
                # Similar permits
                mock_result.fetchall.return_value = [
                    ("2021001001",), ("2021001002",), ("2021001003",),
                ]
            elif "application_number" in sql_lower and "in (" in sql_lower:
                # Addenda for similar permits (transition data)
                mock_result.fetchall.return_value = [
                    ("2021001001", "SFFD", "2021-01-01"),
                    ("2021001001", "CP-ZOC", "2021-02-01"),
                    ("2021001002", "SFFD", "2021-01-01"),
                    ("2021001002", "CP-ZOC", "2021-02-01"),
                    ("2021001003", "SFFD", "2021-01-01"),
                    ("2021001003", "CP-ZOC", "2021-02-01"),
                ]
            elif "station_velocity_v2" in sql_lower:
                # Velocity data
                mock_result.fetchone.return_value = (3.0, 7.0, 12.0, 21.0, 150, "current")
            else:
                mock_result.fetchone.return_value = None
                mock_result.fetchall.return_value = []
            return mock_result

        conn.execute = MagicMock(side_effect=_execute)
        mock_get_conn.return_value = conn

        result = self._run(predict_next_stations("202201234567"))
        assert isinstance(result, str)
        # Should contain prediction header
        assert "Next Station" in result or "Predicted" in result or "Probability" in result


# ── Module import sanity check ─────────────────────────────────────


def test_module_importable():
    """Verify the module imports cleanly without side effects."""
    import importlib
    mod = importlib.import_module("src.tools.predict_next_stations")
    assert hasattr(mod, "predict_next_stations")
    assert callable(mod.predict_next_stations)


def test_predict_next_stations_is_async():
    """Verify the main tool function is a coroutine function."""
    import inspect
    assert inspect.iscoroutinefunction(predict_next_stations)
