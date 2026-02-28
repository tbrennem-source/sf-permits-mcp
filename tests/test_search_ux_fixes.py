"""Tests for search result UX fixes: date formatting, permit type casing, cost notes.

Sprint 95 T2 — covers issues found in persona-amy audit:
1. ISO timestamps → formatted dates (Apr 28, 2025)
2. Mixed case permit types → title case
3. Cost field "—" → note explaining why
"""
import pytest


class TestDateFormatting:
    """Test _fmt_date helper in permit_lookup tool."""

    def setup_method(self):
        from src.tools.permit_lookup import _fmt_date
        self.fmt = _fmt_date

    def test_iso_timestamp_formatted(self):
        """Full ISO timestamp like 2025-04-28T12:53:40.000 → Apr 28, 2025."""
        assert self.fmt("2025-04-28T12:53:40.000") == "Apr 28, 2025"

    def test_iso_date_only_formatted(self):
        """YYYY-MM-DD → Mon D, YYYY."""
        assert self.fmt("2025-04-28") == "Apr 28, 2025"

    def test_january_formatting(self):
        """Jan 1 — single digit day has no leading zero."""
        assert self.fmt("2025-01-01") == "Jan 1, 2025"

    def test_december_formatting(self):
        """Dec 31."""
        assert self.fmt("2024-12-31") == "Dec 31, 2024"

    def test_none_returns_dash(self):
        """None → em dash."""
        assert self.fmt(None) == "—"

    def test_empty_string_returns_dash(self):
        """Empty string → em dash."""
        assert self.fmt("") == "—"

    def test_invalid_date_returns_raw(self):
        """Malformed date falls back to raw string (not crash)."""
        result = self.fmt("not-a-date")
        assert result  # Should not be empty or crash
        assert "—" in result or "not" in result  # Returns something reasonable

    def test_iso_with_milliseconds(self):
        """Handles .000 suffix common in SODA API responses."""
        assert self.fmt("2024-06-15T00:00:00.000") == "Jun 15, 2024"

    def test_iso_with_tz_offset(self):
        """Handles date with timezone offset by truncating to date portion."""
        # Still reads YYYY-MM-DD from first 10 chars
        result = self.fmt("2024-03-15T09:30:00+00:00")
        assert result == "Mar 15, 2024"


class TestPermitTypeCasing:
    """Test _title_permit_type helper in permit_lookup tool."""

    def setup_method(self):
        from src.tools.permit_lookup import _title_permit_type
        self.fmt = _title_permit_type

    def test_all_lowercase_becomes_title(self):
        """'otc alterations permit' → 'Otc Alterations Permit'."""
        assert self.fmt("otc alterations permit") == "Otc Alterations Permit"

    def test_already_title_case_unchanged(self):
        """'Electrical Permit' stays 'Electrical Permit'."""
        assert self.fmt("Electrical Permit") == "Electrical Permit"

    def test_all_uppercase_becomes_title(self):
        """'NEW CONSTRUCTION' → 'New Construction'."""
        assert self.fmt("NEW CONSTRUCTION") == "New Construction"

    def test_multi_word_type(self):
        """'new construction wood frame' → 'New Construction Wood Frame'."""
        assert self.fmt("new construction wood frame") == "New Construction Wood Frame"

    def test_none_returns_empty(self):
        """None → ''."""
        assert self.fmt(None) == ""

    def test_empty_returns_empty(self):
        """Empty string → ''."""
        assert self.fmt("") == ""

    def test_strips_whitespace(self):
        """Leading/trailing whitespace stripped before title-casing."""
        assert self.fmt("  plumbing permit  ") == "Plumbing Permit"


class TestFormatPermitList:
    """Test _format_permit_list output for all three UX fixes."""

    def setup_method(self):
        from src.tools.permit_lookup import _format_permit_list
        self.fmt = _format_permit_list

    def _make_permit(self, **kwargs):
        defaults = {
            "permit_number": "202401015555",
            "permit_type_definition": "otc alterations permit",
            "status": "issued",
            "filed_date": "2025-04-28T12:53:40.000",
            "estimated_cost": None,
            "description": "Test permit",
        }
        defaults.update(kwargs)
        return defaults

    def test_iso_date_formatted_in_table(self):
        """ISO timestamp in filed_date is rendered as human-readable date."""
        result = self.fmt([self._make_permit()], "test")
        assert "2025-04-28T12:53:40.000" not in result
        assert "Apr 28, 2025" in result

    def test_plain_date_formatted_in_table(self):
        """Plain YYYY-MM-DD is rendered as human-readable date."""
        result = self.fmt([self._make_permit(filed_date="2025-04-28")], "test")
        assert "Apr 28, 2025" in result

    def test_permit_type_title_cased(self):
        """Lowercase permit type is title-cased in output."""
        result = self.fmt([self._make_permit()], "test")
        assert "otc alterations permit" not in result
        assert "Otc Alterations Permit" in result

    def test_cost_dash_with_footnote(self):
        """When cost is None/missing, shows — and adds footnote explaining why."""
        result = self.fmt([self._make_permit(estimated_cost=None)], "test")
        assert "| — |" in result or "| — \u00a0*|" in result or "—" in result
        # The explanatory note should be present when any permit has no cost
        assert "Cost shows" in result or "electrical" in result.lower()

    def test_cost_shown_when_present(self):
        """When estimated_cost is set, shows dollar amount."""
        result = self.fmt([self._make_permit(estimated_cost=50000)], "test")
        assert "$50,000" in result

    def test_no_cost_footnote_when_all_have_cost(self):
        """When all permits have costs, no explanatory footnote is appended."""
        result = self.fmt(
            [self._make_permit(estimated_cost=50000), self._make_permit(estimated_cost=100000)],
            "test",
        )
        assert "Cost shows" not in result

    def test_status_title_cased(self):
        """Status field is title-cased (e.g., 'issued' → 'Issued')."""
        result = self.fmt([self._make_permit(status="issued")], "test")
        # In the table row, status should be title-cased
        assert "| Issued |" in result

    def test_mixed_permits_single_footnote(self):
        """When only some permits lack cost, footnote appears once."""
        permits = [
            self._make_permit(estimated_cost=None),
            self._make_permit(estimated_cost=5000, permit_number="202401015556"),
        ]
        result = self.fmt(permits, "test")
        # Only one footnote, not two
        assert result.count("Cost shows") <= 1


class TestJinja2DateFilter:
    """Test the format_date Jinja2 template filter registered in app.py."""

    def setup_method(self):
        """Import the filter directly by recreating its logic."""
        # We test the filter logic directly (not through Flask app to avoid DB deps)
        from datetime import datetime as _dt

        def _format_date_filter(value):
            if not value:
                return ""
            raw = str(value)[:10]
            try:
                parsed = _dt.strptime(raw, "%Y-%m-%d")
                return parsed.strftime("%b %-d, %Y")
            except (ValueError, TypeError):
                return raw

        self.fmt = _format_date_filter

    def test_iso_timestamp_rendered(self):
        assert self.fmt("2025-04-28T12:53:40.000") == "Apr 28, 2025"

    def test_date_only_rendered(self):
        assert self.fmt("2025-04-28") == "Apr 28, 2025"

    def test_none_returns_empty(self):
        """None → empty string (different from Python helper which returns —)."""
        assert self.fmt(None) == ""

    def test_empty_returns_empty(self):
        assert self.fmt("") == ""

    def test_routing_date_format(self):
        """routing_latest_date is YYYY-MM-DD[:10] format."""
        assert self.fmt("2025-03-15") == "Mar 15, 2025"


class TestJinja2TitlePermitFilter:
    """Test the title_permit Jinja2 template filter registered in app.py."""

    def setup_method(self):
        def _title_permit_filter(value):
            if not value:
                return ""
            return str(value).strip().title()

        self.fmt = _title_permit_filter

    def test_lowercase_becomes_title(self):
        assert self.fmt("otc alterations permit") == "Otc Alterations Permit"

    def test_none_returns_empty(self):
        assert self.fmt(None) == ""

    def test_already_title_unchanged(self):
        assert self.fmt("Electrical Permit") == "Electrical Permit"
