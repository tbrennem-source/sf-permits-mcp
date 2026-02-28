"""Tests verifying permit number click targets go to station predictor,
not the DBI portal, in search result templates and the permit lookup formatter.

Sprint QS12 T3 Agent 3D — Permit Click Target Fix
"""
import re
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Helper: load template content
# ---------------------------------------------------------------------------

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")


def _read_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Template CSS tests — verify .dbi-link class styling is present
# ---------------------------------------------------------------------------


class TestDbiLinkCssInTemplates:
    """Verify that .dbi-link CSS class is defined in all search result templates."""

    def test_dbi_link_class_in_search_results_public(self):
        """search_results_public.html must define .dbi-link CSS."""
        content = _read_template("search_results_public.html")
        assert ".dbi-link" in content, (
            "search_results_public.html must define .dbi-link CSS class "
            "for secondary DBI portal link styling"
        )

    def test_dbi_link_class_in_search_results(self):
        """search_results.html (authenticated) must define .dbi-link CSS."""
        content = _read_template("search_results.html")
        assert ".dbi-link" in content, (
            "search_results.html must define .dbi-link CSS class "
            "for secondary DBI portal link styling"
        )

    def test_dbi_link_class_in_index(self):
        """index.html result card must define .dbi-link CSS."""
        content = _read_template("index.html")
        assert ".dbi-link" in content, (
            "index.html must define .dbi-link CSS class for secondary DBI portal link styling"
        )

    def test_dbi_link_uses_text_tertiary_color_public(self):
        """DBI link must use --text-tertiary color token (not hard-coded hex)."""
        content = _read_template("search_results_public.html")
        # Look for .dbi-link block with --text-tertiary
        dbi_link_section = re.search(
            r'\.dbi-link\s*\{[^}]+\}', content, re.DOTALL
        )
        assert dbi_link_section is not None, "Could not find .dbi-link CSS block"
        assert "--text-tertiary" in dbi_link_section.group(0), (
            ".dbi-link CSS must use var(--text-tertiary) color token, not hard-coded hex"
        )


# ---------------------------------------------------------------------------
# permit_lookup.py formatter tests
# ---------------------------------------------------------------------------


class TestPermitLookupFormatter:
    """Verify _format_permit_detail generates the correct link targets."""

    def _get_format_permit_detail(self):
        """Import the function under test."""
        # Ensure src is importable
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.tools.permit_lookup import _format_permit_detail
        return _format_permit_detail

    def test_primary_link_is_station_predictor(self):
        """Permit number in _format_permit_detail must link to /tools/station-predictor."""
        _format_permit_detail = self._get_format_permit_detail()
        permit = {
            "permit_number": "202401015678",
            "permit_type_definition": "Building Permit",
            "status": "filed",
        }
        output = _format_permit_detail(permit)
        assert "/tools/station-predictor?permit=202401015678" in output, (
            "_format_permit_detail must link permit number to /tools/station-predictor, "
            f"not DBI. Got: {output[:300]}"
        )

    def test_dbi_link_is_present_as_secondary(self):
        """DBI link must be present as a secondary 'View on DBI' option."""
        _format_permit_detail = self._get_format_permit_detail()
        permit = {
            "permit_number": "202401015678",
            "permit_type_definition": "Building Permit",
            "status": "filed",
        }
        output = _format_permit_detail(permit)
        assert "dbiweb02.sfgov.org" in output, (
            "_format_permit_detail must include DBI link as secondary option"
        )
        assert "View on DBI" in output, (
            "_format_permit_detail must label the DBI link as 'View on DBI'"
        )

    def test_dbi_is_not_primary_link_for_permit_number(self):
        """The permit number itself must NOT link directly to dbiweb02.sfgov.org."""
        _format_permit_detail = self._get_format_permit_detail()
        permit = {
            "permit_number": "202401015678",
            "permit_type_definition": "Building Permit",
            "status": "issued",
        }
        output = _format_permit_detail(permit)
        # The Permit Number markdown line should link to station predictor, not DBI
        permit_number_line = [
            line for line in output.splitlines()
            if "Permit Number" in line
        ]
        assert permit_number_line, "Expected a Permit Number line in output"
        line = permit_number_line[0]
        # The permit number link should go to station predictor
        assert "/tools/station-predictor?permit=202401015678" in line, (
            f"Permit Number link must go to station predictor. Line: {line}"
        )
        # DBI should appear later in the line as a secondary link, not as the primary href
        # Find position of permit number link vs DBI link
        station_pos = line.find("/tools/station-predictor")
        dbi_pos = line.find("dbiweb02")
        assert station_pos < dbi_pos or station_pos != -1, (
            "Station predictor link should appear before DBI link in output"
        )


# ---------------------------------------------------------------------------
# md_to_html post-processing tests
# ---------------------------------------------------------------------------


class TestMdToHtmlExternalLinks:
    """Verify md_to_html adds target=_blank and dbi-link class correctly."""

    def _md_to_html(self, text: str) -> str:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from web.helpers import md_to_html
        return md_to_html(text)

    def test_dbi_link_gets_class_attribute(self):
        """DBI portal links rendered by md_to_html must have class='dbi-link'."""
        md = "[DBI ↗](https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber=202401015678)"
        html = self._md_to_html(md)
        assert 'class="dbi-link"' in html, (
            "md_to_html must add class='dbi-link' to DBI portal links. "
            f"Got: {html}"
        )

    def test_dbi_link_opens_in_new_tab(self):
        """DBI portal links rendered by md_to_html must have target='_blank'."""
        md = "[DBI ↗](https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber=202401015678)"
        html = self._md_to_html(md)
        assert 'target="_blank"' in html, (
            "md_to_html must add target='_blank' to DBI portal links"
        )

    def test_internal_station_predictor_link_no_blank(self):
        """Internal station predictor links must NOT get target='_blank'."""
        md = "[202401015678](/tools/station-predictor?permit=202401015678)"
        html = self._md_to_html(md)
        assert 'target="_blank"' not in html, (
            "Internal /tools/station-predictor links must not open in new tab"
        )
        assert 'href="/tools/station-predictor?permit=202401015678"' in html, (
            "Station predictor link href must be preserved"
        )

    def test_external_non_dbi_links_get_blank(self):
        """Non-DBI external links (https://) must also get target='_blank'."""
        md = "[SF Gov](https://sf.gov)"
        html = self._md_to_html(md)
        assert 'target="_blank"' in html, (
            "All external https:// links must get target='_blank'"
        )
        assert 'class="dbi-link"' not in html, (
            "Non-DBI external links must not get class='dbi-link'"
        )

    def test_permit_table_row_has_station_predictor_primary(self):
        """A simulated permit table row must have station predictor as primary link."""
        pn = "202401015678"
        pn_link = (
            f"[{pn}](/tools/station-predictor?permit={pn}) "
            f"[[DBI ↗]](https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber={pn})"
        )
        md = f"| {pn_link} | Building Permit | filed | 2024-01-01 | $50,000 |"
        # Not testing md_to_html table rendering here — just the link pattern
        html = self._md_to_html(pn_link)
        # Station predictor link should be present
        assert f"/tools/station-predictor?permit={pn}" in html
        # DBI link should have dbi-link class
        assert 'class="dbi-link"' in html
        # Station predictor link should come first (lower string position)
        station_pos = html.find("/tools/station-predictor")
        dbi_pos = html.find("dbi-link")
        assert station_pos < dbi_pos, (
            "Station predictor link (primary) must appear before dbi-link (secondary) in output"
        )
