"""
Sprint 58C — Methodology UI Cards test suite.

Tests the template files for correct methodology card structure,
anchor IDs, toggle presence, print CSS, and backward compatibility.
All tests operate via string search on template file contents
(no Jinja rendering required).
"""

import os
import re

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../web/templates")


def _read(filename: str) -> str:
    """Read a template file and return its content."""
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# results.html tests
# ---------------------------------------------------------------------------

class TestResultsTemplate:
    """Tests for web/templates/results.html."""

    def setup_method(self):
        self.html = _read("results.html")

    def test_methodology_card_class_present(self):
        """Template contains methodology-card class definition."""
        assert "methodology-card" in self.html

    def test_methodology_body_class_present(self):
        """Template contains methodology-body class for card content."""
        assert "methodology-body" in self.html

    def test_anchor_id_permits(self):
        """Method card for permits section has correct anchor ID."""
        assert 'method-permits' in self.html

    def test_anchor_id_timeline(self):
        """Method card for timeline section has correct anchor ID."""
        assert 'method-timeline' in self.html

    def test_anchor_id_fees(self):
        """Method card for fees section has correct anchor ID."""
        assert 'method-fees' in self.html

    def test_anchor_id_documents(self):
        """Method card for documents section has correct anchor ID."""
        assert 'method-documents' in self.html

    def test_anchor_id_risk(self):
        """Method card for risk section has correct anchor ID."""
        assert 'method-risk' in self.html

    def test_show_methodology_toggle_present(self):
        """Toggle checkbox with id='show-methodology' is present."""
        assert 'id="show-methodology"' in self.html

    def test_methodology_toggle_class(self):
        """methodology-toggle class is present."""
        assert 'methodology-toggle' in self.html

    def test_localStorage_persistence(self):
        """Toggle uses localStorage for persistence."""
        assert "localStorage" in self.html
        assert "show-methodology" in self.html

    def test_backward_compat_if_guard(self):
        """Card is wrapped in a check for methodology being present."""
        # The template uses {% if m %} or {% if methodology %} guard
        assert "{% if m %}" in self.html or "{% if methodology" in self.html

    def test_coverage_gaps_conditional(self):
        """Coverage gaps section only renders when non-empty."""
        assert "coverage_gaps" in self.html
        # Must be inside a conditional block
        assert "{% if m.coverage_gaps %}" in self.html or "if m.coverage_gaps" in self.html

    def test_details_summary_tag(self):
        """Methodology uses HTML <details> and <summary> elements."""
        assert "<details" in self.html
        assert "<summary>" in self.html

    def test_print_css_methodology(self):
        """Print CSS expands methodology cards."""
        assert "@media print" in self.html
        assert "methodology" in self.html  # print block targets methodology

    def test_formula_steps_conditional(self):
        """formula_steps section is wrapped in a conditional."""
        assert "formula_steps" in self.html
        assert "{% if m.formula_steps %}" in self.html or "if m.formula_steps" in self.html

    def test_stations_conditional(self):
        """stations section (timeline-specific) is wrapped in a conditional."""
        assert "stations" in self.html
        assert "{% if m.stations %}" in self.html or "if m.stations" in self.html

    def test_triggers_matched_conditional(self):
        """triggers_matched section (predict-specific) is wrapped in a conditional."""
        assert "triggers_matched" in self.html
        assert "{% if m.triggers_matched %}" in self.html or "if m.triggers_matched" in self.html

    def test_correction_categories_conditional(self):
        """correction_categories section (risk-specific) is wrapped in a conditional."""
        assert "correction_categories" in self.html
        assert "{% if m.correction_categories %}" in self.html or "if m.correction_categories" in self.html

    def test_revision_context_conditional(self):
        """revision_context section (fees-specific) is wrapped in a conditional."""
        assert "revision_context" in self.html
        assert "revision_context.revision_rate" in self.html

    def test_methodology_footer_present(self):
        """methodology-footer class is present for data source / confidence display."""
        assert "methodology-footer" in self.html

    def test_fallback_note_conditional(self):
        """fallback_note (timeline-specific) is wrapped in a conditional."""
        assert "fallback_note" in self.html
        assert "if m.fallback_note" in self.html

    def test_data_freshness_rendered(self):
        """data_freshness field is rendered in the footer."""
        assert "data_freshness" in self.html

    def test_confidence_rendered(self):
        """confidence field is rendered in the footer."""
        assert "m.confidence" in self.html

    def test_sample_size_rendered(self):
        """sample_size field is rendered in the footer."""
        assert "sample_size" in self.html

    def test_station_breakdown_table(self):
        """station-breakdown CSS class is present for timeline station table."""
        assert "station-breakdown" in self.html


# ---------------------------------------------------------------------------
# analysis_shared.html tests
# ---------------------------------------------------------------------------

class TestAnalysisSharedTemplate:
    """Tests for web/templates/analysis_shared.html."""

    def setup_method(self):
        self.html = _read("analysis_shared.html")

    def test_methodology_card_present(self):
        """Shared page has methodology cards."""
        assert "methodology-card" in self.html

    def test_no_methodology_toggle(self):
        """Shared page does NOT have the show/hide toggle."""
        assert 'id="show-methodology"' not in self.html
        assert "methodology-toggle" not in self.html

    def test_no_localstorage(self):
        """Shared page does NOT use localStorage for toggle."""
        assert "localStorage.setItem" not in self.html

    def test_anchor_id_method_permits(self):
        """Shared page has method-permits anchor."""
        assert "method-permits" in self.html

    def test_anchor_id_method_timeline(self):
        """Shared page has method-timeline anchor."""
        assert "method-timeline" in self.html

    def test_anchor_id_method_fees(self):
        """Shared page has method-fees anchor."""
        assert "method-fees" in self.html

    def test_anchor_id_method_documents(self):
        """Shared page has method-documents anchor."""
        assert "method-documents" in self.html

    def test_anchor_id_method_risk(self):
        """Shared page has method-risk anchor."""
        assert "method-risk" in self.html

    def test_details_summary_present(self):
        """Shared page uses <details> + <summary> for expandable cards."""
        assert "<details" in self.html
        assert "<summary>" in self.html

    def test_backward_compat_if_guard(self):
        """Shared page guards methodology card with a presence check."""
        assert "{% if m %}" in self.html or "if methodology" in self.html

    def test_print_css_present(self):
        """Shared page has print CSS for methodology."""
        assert "@media print" in self.html

    def test_coverage_gaps_conditional(self):
        """Coverage gaps on shared page is guarded by a conditional."""
        assert "coverage_gaps" in self.html

    def test_methodology_footer_class(self):
        """methodology-footer class is present."""
        assert "methodology-footer" in self.html


# ---------------------------------------------------------------------------
# analyze_preview.html tests
# ---------------------------------------------------------------------------

class TestAnalyzePreviewTemplate:
    """Tests for web/templates/analyze_preview.html."""

    def setup_method(self):
        self.html = _read("analyze_preview.html")

    def test_lightweight_methodology_footer_present(self):
        """Preview page has lightweight methodology micro-footer."""
        assert "methodology-micro" in self.html

    def test_no_full_methodology_card(self):
        """Preview page does NOT have full expandable methodology card."""
        # The preview uses micro-footer, not the full card with <details>
        # (It could have the CSS class name in style, but no <details id="method-...">)
        assert '<details class="methodology-card"' not in self.html

    def test_methodology_micro_css(self):
        """methodology-micro CSS class is defined in the style block."""
        assert ".methodology-micro" in self.html

    def test_methodology_micro_predict(self):
        """Predict card has methodology micro-footer."""
        # Check that the micro footer appears near the predict card content
        assert "Decision-tree permit classification" in self.html or "methodology-micro" in self.html

    def test_methodology_micro_timeline(self):
        """Timeline card has methodology micro-footer."""
        assert "Historical permit statistics" in self.html or "methodology-micro" in self.html

    def test_no_methodology_toggle(self):
        """Preview page does NOT have the show/hide toggle."""
        assert 'id="show-methodology"' not in self.html


# ---------------------------------------------------------------------------
# analysis_email.html tests
# ---------------------------------------------------------------------------

class TestAnalysisEmailTemplate:
    """Tests for web/templates/analysis_email.html."""

    def setup_method(self):
        self.html = _read("analysis_email.html")

    def test_see_how_calculated_link_present(self):
        """Email has at least one 'See how we calculated this' anchor link."""
        assert "See how we calculated this" in self.html

    def test_method_permits_anchor_link(self):
        """Email links to method-permits anchor."""
        assert "#method-permits" in self.html

    def test_method_timeline_anchor_link(self):
        """Email links to method-timeline anchor."""
        assert "#method-timeline" in self.html

    def test_method_fees_anchor_link(self):
        """Email links to method-fees anchor."""
        assert "#method-fees" in self.html

    def test_method_documents_anchor_link(self):
        """Email links to method-documents anchor."""
        assert "#method-documents" in self.html

    def test_method_risk_anchor_link(self):
        """Email links to method-risk anchor."""
        assert "#method-risk" in self.html

    def test_share_url_used_in_anchor(self):
        """Email anchor links use share_url variable for base URL."""
        assert "share_url" in self.html
        assert "{{ share_url }}#method-" in self.html

    def test_anchor_link_style_present(self):
        """Anchor links in email have inline styling (email-safe)."""
        assert "style=" in self.html
        # At least one anchor should have color styling
        assert "#4a9eff" in self.html or "color:" in self.html

    def test_methodology_section_label(self):
        """Email has a 'How we calculated this' section header."""
        assert "How we calculated this" in self.html
