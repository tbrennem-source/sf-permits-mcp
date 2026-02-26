"""Tests for Sprint 64 brief enhancements: pipeline stats + change velocity."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest


class TestGetLastRefreshPipelineStats:
    """_get_last_refresh now returns pipeline stats (changes_detected, inspections_updated)."""

    def test_includes_changes_detected(self):
        from web.brief import _get_last_refresh
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S+00:00")

        with patch("web.brief.query_one") as mock_qone:
            # First call: cron_log row (started_at, completed_at, was_catchup)
            # Second call: permit_changes count
            # Third call: inspections_updated
            mock_qone.side_effect = [
                (ts_str, ts_str, False),  # cron_log row
                (42,),                     # changes_detected
                (7,),                      # inspections_updated
            ]
            result = _get_last_refresh()

        assert result is not None
        assert result["changes_detected"] == 42
        assert result["inspections_updated"] == 7
        assert result["hours_ago"] < 3

    def test_pipeline_stats_non_fatal(self):
        """If pipeline stats query fails, basic last_refresh still returned."""
        from web.brief import _get_last_refresh
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc) - timedelta(hours=1)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S+00:00")

        with patch("web.brief.query_one") as mock_qone:
            # First call succeeds (cron_log), second raises
            mock_qone.side_effect = [
                (ts_str, ts_str, False),
                Exception("permit_changes not found"),
            ]
            result = _get_last_refresh()

        assert result is not None
        assert "last_success" in result
        # Pipeline stats should be absent, not error
        assert "changes_detected" not in result or result.get("changes_detected", 0) >= 0

    def test_returns_none_when_no_cron_log(self):
        from web.brief import _get_last_refresh

        with patch("web.brief.query_one", return_value=None):
            result = _get_last_refresh()
        assert result is None


class TestGetChangeVelocity:
    """_get_change_velocity groups change_type counts."""

    def test_returns_grouped_counts(self):
        from web.brief import _get_change_velocity

        since = date.today() - timedelta(days=1)
        with patch("web.brief.query", return_value=[
            ("status_change", 5),
            ("new_permit", 3),
            ("cost_revision", 1),
        ]):
            result = _get_change_velocity(since)
        assert result == {"status_change": 5, "new_permit": 3, "cost_revision": 1}

    def test_returns_empty_dict_on_error(self):
        from web.brief import _get_change_velocity

        since = date.today()
        with patch("web.brief.query", side_effect=Exception("table missing")):
            result = _get_change_velocity(since)
        assert result == {}

    def test_returns_empty_dict_when_no_changes(self):
        from web.brief import _get_change_velocity

        since = date.today()
        with patch("web.brief.query", return_value=[]):
            result = _get_change_velocity(since)
        assert result == {}


class TestBriefIncludesChangeVelocity:
    """get_morning_brief return dict includes change_velocity."""

    def test_change_velocity_in_brief_return(self):
        from web.brief import get_morning_brief

        # Mock everything to avoid DB calls
        with patch("web.brief.query", return_value=[]), \
             patch("web.brief.query_one", return_value=None), \
             patch("web.auth.get_watches", return_value=[]), \
             patch("web.brief._get_regulatory_alerts", return_value=[]), \
             patch("web.brief.get_pipeline_health_for_brief", return_value={}), \
             patch("web.brief._get_planning_context", return_value=[]), \
             patch("web.brief._get_compliance_calendar", return_value=[]), \
             patch("web.brief._get_data_quality", return_value={}), \
             patch("web.brief.get_street_use_activity_for_user", return_value=[]), \
             patch("web.brief.get_nearby_development_for_user", return_value=[]):
            result = get_morning_brief(user_id=1)

        assert "change_velocity" in result
        assert isinstance(result["change_velocity"], dict)
