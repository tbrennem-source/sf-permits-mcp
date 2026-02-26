"""Tests for Sprint 60B — Station Path Predictor.

Covers:
- ensure_station_transitions_table creates table on postgres
- predict_remaining_path returns list of predicted stations
- predict stops at terminal stations (PERMIT-CTR)
- predict stops when probability < min_probability
- predict does not revisit stations (no cycles)
- predict_total_remaining_days sums p50 across path
- predict returns None when no transition data
- refresh_station_transitions returns stats dict
- brief enrichment adds predicted_next field
- brief enrichment sets predicted_next=None when no data
- cron velocity refresh includes transitions key
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_template(name: str) -> str:
    path = REPO_ROOT / "web" / "templates" / name
    return path.read_text(encoding="utf-8")


def read_source(rel: str) -> str:
    path = REPO_ROOT / rel
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Class TestStationPredictor
# ---------------------------------------------------------------------------

class TestStationPredictor:

    def test_ensure_table_postgres_executes_create(self):
        """ensure_station_transitions_table calls execute_write with CREATE TABLE SQL on postgres backend."""
        with patch("src.tools.station_predictor.BACKEND", "postgres"), \
             patch("src.tools.station_predictor.execute_write") as mock_ew:
            from src.tools.station_predictor import ensure_station_transitions_table
            ensure_station_transitions_table()
            assert mock_ew.called, "execute_write should be called on postgres backend"
            sql_arg = mock_ew.call_args[0][0]
            assert "CREATE TABLE IF NOT EXISTS station_transitions" in sql_arg

    def test_ensure_table_duckdb_skips(self):
        """ensure_station_transitions_table does nothing on DuckDB backend."""
        with patch("src.tools.station_predictor.BACKEND", "duckdb"), \
             patch("src.tools.station_predictor.execute_write") as mock_ew:
            from src.tools.station_predictor import ensure_station_transitions_table
            ensure_station_transitions_table()
            assert not mock_ew.called, "execute_write should NOT be called on duckdb backend"

    def test_predict_remaining_path_basic(self):
        """predict_remaining_path returns a list of predicted station dicts."""
        mock_transition_rows = [("SFFD", 0.85)]
        mock_velocity_rows = [(4.0, 8.0)]

        # Sequence: first call returns transition, second call returns velocity, third empty to stop
        query_side_effects = [
            mock_transition_rows,  # station=BLDG -> SFFD
            mock_velocity_rows,    # velocity for SFFD
            [],                    # no more transitions from SFFD
        ]

        with patch("src.tools.station_predictor.query", side_effect=query_side_effects):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG")

        assert isinstance(path, list)
        assert len(path) == 1
        assert path[0]["station"] == "SFFD"
        assert path[0]["probability"] == 0.85
        assert path[0]["p50_days"] == 4.0
        assert path[0]["p75_days"] == 8.0

    def test_predict_stops_at_terminal(self):
        """Prediction stops when a terminal station (PERMIT-CTR) is reached."""
        # Return PERMIT-CTR as the next station
        mock_transition_rows = [("PERMIT-CTR", 0.95)]
        mock_velocity_rows = [(1.0, 2.0)]

        query_side_effects = [
            mock_transition_rows,  # next = PERMIT-CTR
            mock_velocity_rows,    # velocity for PERMIT-CTR
        ]

        with patch("src.tools.station_predictor.query", side_effect=query_side_effects):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG")

        assert len(path) == 1
        assert path[0]["station"] == "PERMIT-CTR"
        # Should have stopped — no further stations after terminal

    def test_predict_stops_at_low_probability(self):
        """Prediction stops when probability falls below min_probability threshold."""
        # Return a low-probability transition
        mock_transition_rows = [("SFFD", 0.05)]  # 0.05 < 0.1 threshold

        query_side_effects = [
            mock_transition_rows,
        ]

        with patch("src.tools.station_predictor.query", side_effect=query_side_effects):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG", min_probability=0.1)

        assert len(path) == 0, "Path should be empty when first transition is below min_probability"

    def test_predict_no_cycle(self):
        """Visited stations are not revisited — prediction terminates instead of looping."""
        # Simulate BLDG -> SFFD -> BLDG cycle scenario
        mock_sffd_transition = [("SFFD", 0.9)]
        mock_sffd_velocity = [(5.0, 10.0)]
        mock_bldg_transition = [("BLDG", 0.85)]  # Would create a cycle back to start

        query_side_effects = [
            mock_sffd_transition,  # BLDG -> SFFD
            mock_sffd_velocity,    # velocity for SFFD
            mock_bldg_transition,  # SFFD -> BLDG (cycle!)
        ]

        with patch("src.tools.station_predictor.query", side_effect=query_side_effects):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG")

        # Should stop at SFFD since BLDG is already visited
        assert len(path) == 1
        assert path[0]["station"] == "SFFD"
        # BLDG not in path (cycle prevented)
        station_names = [s["station"] for s in path]
        assert "BLDG" not in station_names

    def test_predict_total_remaining_days(self):
        """predict_total_remaining_days sums p50 days across all predicted stations."""
        mock_path = [
            {"station": "SFFD", "probability": 0.85, "p50_days": 5.0, "p75_days": 10.0},
            {"station": "DPH", "probability": 0.75, "p50_days": 3.0, "p75_days": 6.0},
            {"station": "PERMIT-CTR", "probability": 0.92, "p50_days": 1.0, "p75_days": 2.0},
        ]

        with patch("src.tools.station_predictor.predict_remaining_path", return_value=mock_path):
            from src.tools.station_predictor import predict_total_remaining_days
            result = predict_total_remaining_days("BLDG")

        assert result is not None
        assert result["p50_remaining_days"] == 9  # 5 + 3 + 1
        assert result["p75_remaining_days"] == 18  # 10 + 6 + 2
        assert result["remaining_stations"] == 3
        assert result["next_station"] == "SFFD"
        assert result["next_p50_days"] == 5.0

    def test_predict_empty_when_no_data(self):
        """predict_total_remaining_days returns None when no transition data exists."""
        with patch("src.tools.station_predictor.query", return_value=[]):
            from src.tools.station_predictor import predict_total_remaining_days
            result = predict_total_remaining_days("UNKNOWN_STATION")

        assert result is None

    def test_refresh_returns_stats_duckdb(self):
        """refresh_station_transitions returns dict with transitions=0 on DuckDB (skip)."""
        with patch("src.tools.station_predictor.BACKEND", "duckdb"):
            from src.tools.station_predictor import refresh_station_transitions
            result = refresh_station_transitions()

        assert isinstance(result, dict)
        assert "transitions" in result
        assert result["transitions"] == 0

    def test_refresh_returns_stats_postgres(self):
        """refresh_station_transitions returns dict with transition count on postgres."""
        with patch("src.tools.station_predictor.BACKEND", "postgres"), \
             patch("src.tools.station_predictor.execute_write") as mock_ew, \
             patch("src.tools.station_predictor.query", return_value=[(42,)]):
            from src.tools.station_predictor import refresh_station_transitions
            result = refresh_station_transitions()

        assert isinstance(result, dict)
        assert result["transitions"] == 42

    def test_predict_handles_query_exception(self):
        """predict_remaining_path handles DB query exceptions gracefully."""
        with patch("src.tools.station_predictor.query", side_effect=Exception("DB error")):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG")

        assert path == []

    def test_predict_path_with_none_velocity(self):
        """predict_remaining_path handles None p50_days from velocity table."""
        mock_transition_rows = [("SFFD", 0.85)]
        mock_velocity_rows = [(None, None)]

        query_side_effects = [
            mock_transition_rows,
            mock_velocity_rows,
            [],
        ]

        with patch("src.tools.station_predictor.query", side_effect=query_side_effects):
            from src.tools.station_predictor import predict_remaining_path
            path = predict_remaining_path("BLDG")

        assert len(path) == 1
        assert path[0]["p50_days"] is None
        assert path[0]["p75_days"] is None


# ---------------------------------------------------------------------------
# Class TestBriefPredictionEnrichment
# ---------------------------------------------------------------------------

class TestBriefPredictionEnrichment:

    def test_plan_review_has_prediction_fields(self):
        """After enrichment, plan review items have predicted_next, predicted_next_days, predicted_remaining_days."""
        # Build a minimal plan review item
        review = {
            "permit_number": "202301010001",
            "station": "BLDG",
            "reviewer": "SMITH J",
            "result": "Issued Comments",
            "notes": "",
            "change_type": "station",
            "department": "DBI",
            "finish_date": "2024-01-15",
            "permit_type": "alterations",
            "street_number": "123",
            "street_name": "MAIN",
            "neighborhood": "SoMa",
            "label": "123 MAIN",
            "change_date": "2024-01-15",
        }

        mock_prediction = {
            "remaining_stations": 2,
            "p50_remaining_days": 12,
            "p75_remaining_days": 20,
            "path": [],
            "next_station": "SFFD",
            "next_p50_days": 7.0,
        }

        with patch("web.routing.get_routing_progress_batch", return_value={}, create=True), \
             patch("web.station_velocity.get_station_baseline", return_value=None, create=True), \
             patch("src.tools.station_predictor.predict_total_remaining_days", return_value=mock_prediction):
            # Import fresh each time to avoid import caching issues
            import importlib
            import web.brief as brief_mod
            importlib.reload(brief_mod)
            brief_mod._enrich_plan_reviews_with_routing([review])

        assert "predicted_next" in review
        assert review["predicted_next"] == "SFFD"
        assert review["predicted_next_days"] == 7
        assert review["predicted_remaining_days"] == 12

    def test_prediction_none_when_no_data(self):
        """predicted_next is None when predict_total_remaining_days returns None."""
        review = {
            "permit_number": "202301010002",
            "station": "BLDG",
            "reviewer": "JONES M",
            "result": "Issued Comments",
            "notes": "",
            "change_type": "station",
            "department": "DBI",
            "finish_date": "2024-01-15",
            "permit_type": "alterations",
            "street_number": "456",
            "street_name": "OAK",
            "neighborhood": "Mission",
            "label": "456 OAK",
            "change_date": "2024-01-15",
        }

        with patch("web.routing.get_routing_progress_batch", return_value={}, create=True), \
             patch("web.station_velocity.get_station_baseline", return_value=None, create=True), \
             patch("src.tools.station_predictor.predict_total_remaining_days", return_value=None):
            import importlib
            import web.brief as brief_mod
            importlib.reload(brief_mod)
            brief_mod._enrich_plan_reviews_with_routing([review])

        assert review["predicted_next"] is None
        assert review["predicted_next_days"] is None
        assert review["predicted_remaining_days"] is None


# ---------------------------------------------------------------------------
# Class TestCronIntegration
# ---------------------------------------------------------------------------

class TestCronIntegration:

    def test_velocity_refresh_includes_transitions_key(self):
        """Cron /cron/velocity-refresh response body includes transitions key."""
        # Read routes_cron.py source and verify SESSION B marker is present
        # (moved from app.py during Blueprint refactor)
        source = read_source("web/routes_cron.py")
        assert "# === SESSION B: Station transitions refresh ===" in source
        assert "# === END SESSION B ===" in source
        assert "refresh_station_transitions" in source
        assert 'stats["transitions"]' in source

    def test_velocity_refresh_transitions_error_key_on_failure(self):
        """Cron function stores transitions_error in stats when refresh_station_transitions raises."""
        source = read_source("web/routes_cron.py")
        assert "transitions_error" in source

    def test_station_predictor_module_importable(self):
        """src.tools.station_predictor can be imported without errors."""
        import importlib
        mod = importlib.import_module("src.tools.station_predictor")
        assert hasattr(mod, "predict_remaining_path")
        assert hasattr(mod, "predict_total_remaining_days")
        assert hasattr(mod, "refresh_station_transitions")
        assert hasattr(mod, "ensure_station_transitions_table")


# ---------------------------------------------------------------------------
# Class TestBriefHtmlTemplate
# ---------------------------------------------------------------------------

class TestBriefHtmlTemplate:

    def test_brief_html_has_predicted_next_block(self):
        """brief.html contains the Sprint 60B predicted next station block."""
        html = read_template("brief.html")
        assert "Sprint 60B" in html
        assert "predicted_next" in html
        assert "Predicted next:" in html

    def test_brief_html_shows_predicted_next_days(self):
        """brief.html renders predicted_next_days when available."""
        html = read_template("brief.html")
        assert "predicted_next_days" in html

    def test_brief_html_shows_estimated_remaining(self):
        """brief.html renders predicted_remaining_days estimate."""
        html = read_template("brief.html")
        assert "predicted_remaining_days" in html
        assert "Est." in html or "days remaining" in html
