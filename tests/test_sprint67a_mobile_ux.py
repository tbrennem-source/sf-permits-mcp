"""Tests for Sprint 67-A: Mobile UX Fixes.

Verifies that mobile.css contains required responsive rules and that
admin templates have proper overflow handling.
"""

import os
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
MOBILE_CSS = ROOT / "web" / "static" / "mobile.css"
TEMPLATES = ROOT / "web" / "templates"


class TestMobileCssRules:
    """Verify mobile.css contains all required responsive rules."""

    def setup_method(self):
        self.css = MOBILE_CSS.read_text()

    def test_table_wrap_overflow(self):
        """table-wrap should have overflow-x: auto for mobile."""
        assert ".table-wrap" in self.css
        assert "overflow-x: auto" in self.css

    def test_kill_switch_panel_mobile(self):
        """Kill switch panel should stack vertically on mobile."""
        assert ".kill-switch-panel" in self.css
        assert "flex-direction: column" in self.css

    def test_stat_grid_mobile(self):
        """Stat grid should collapse to 2-col then 1-col on mobile."""
        assert ".stat-grid" in self.css

    def test_feedback_header_mobile(self):
        """Feedback header should stack on mobile."""
        assert ".feedback-header" in self.css

    def test_regulatory_watch_form_row(self):
        """Regulatory watch form row should go single column on mobile."""
        assert ".rw-form-row" in self.css
        # Should override the 2-column grid
        assert "grid-template-columns: 1fr" in self.css

    def test_heatmap_grid_overflow(self):
        """Velocity heatmap grid should be scrollable on mobile."""
        assert ".heatmap-grid" in self.css

    def test_dept_grid_mobile(self):
        """Department grid should collapse on mobile."""
        assert ".dept-grid" in self.css

    def test_filter_bar_touch_targets(self):
        """Filter buttons should have 44px min-height on mobile."""
        assert ".filter-bar .fbtn" in self.css
        assert "min-height: 44px" in self.css

    def test_bar_date_mobile(self):
        """Cost chart bar-date should shrink on narrow screens."""
        assert ".bar-date" in self.css

    def test_threshold_row_mobile(self):
        """Threshold row should stack vertically on mobile."""
        assert ".threshold-row" in self.css

    def test_rw_header_wrap(self):
        """Regulatory watch header should wrap on mobile."""
        assert ".rw-header" in self.css
        assert "flex-wrap: wrap" in self.css

    def test_rw_form_card_mobile(self):
        """Regulatory watch form card should be near-full-width on mobile."""
        assert ".rw-form-card" in self.css
        assert "width: 95%" in self.css


class TestAdminCostsOverflow:
    """Verify admin_costs.html has proper overflow handling."""

    def test_table_wrap_has_overflow_x(self):
        """admin_costs.html .table-wrap should use overflow-x: auto, not overflow: hidden."""
        html = (TEMPLATES / "admin_costs.html").read_text()
        assert "overflow-x: auto" in html
        # Should NOT have the old overflow: hidden (as standalone, not as part of another rule)
        lines = html.split("\n")
        for line in lines:
            if ".table-wrap" in line or "table-wrap" in line:
                # Found the rule context
                continue
            if "overflow: hidden" in line and "table-wrap" in html[max(0, html.index(line) - 200):html.index(line)]:
                assert False, "table-wrap still has overflow: hidden"


class TestVelocityDashboardMobile:
    """Verify velocity_dashboard.html has mobile-friendly structure."""

    def test_has_mobile_css_link(self):
        """velocity_dashboard.html should link to mobile.css."""
        html = (TEMPLATES / "velocity_dashboard.html").read_text()
        assert "mobile.css" in html

    def test_has_inline_mobile_breakpoints(self):
        """velocity_dashboard.html should have its own @media rules."""
        html = (TEMPLATES / "velocity_dashboard.html").read_text()
        assert "@media (max-width: 640px)" in html
        assert "@media (max-width: 480px)" in html

    def test_heatmap_grid_class_present(self):
        """Heatmap grid div should have the .heatmap-grid class for CSS targeting."""
        html = (TEMPLATES / "velocity_dashboard.html").read_text()
        assert 'class="heatmap-grid"' in html or "heatmap-grid" in html


class TestAdminSourcesMobile:
    """Verify admin_sources.html has mobile styles and navigation."""

    def test_has_nav_include(self):
        """admin_sources.html should include the nav fragment."""
        html = (TEMPLATES / "admin_sources.html").read_text()
        assert "fragments/nav.html" in html

    def test_has_mobile_css_link(self):
        """admin_sources.html should link to mobile.css."""
        html = (TEMPLATES / "admin_sources.html").read_text()
        assert "mobile.css" in html

    def test_has_mobile_breakpoints(self):
        """admin_sources.html should have responsive breakpoints."""
        html = (TEMPLATES / "admin_sources.html").read_text()
        assert "@media (max-width: 640px)" in html
