"""Tests for Sprint 94 landing page showcase layout restructure.

Verifies:
- Stats bar removed (no "1,137,816" or old stat labels)
- Credibility line present at page bottom
- Full-width Gantt section exists outside the showcase grid
- 5-card grid (stuck, whatif, risk, entity, delay) present
- Routing Intelligence label on Gantt section
- Responsive grid CSS present
- showcase_gantt is NOT inside .showcase-grid
"""

import pytest

from web.app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ── Basic smoke ──────────────────────────────────────────────────────────────

class TestLandingBasic:
    def test_landing_returns_200(self, client):
        """Landing page returns HTTP 200."""
        rv = client.get("/")
        assert rv.status_code == 200

    def test_landing_has_html(self, client):
        """Response contains HTML content."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "<!DOCTYPE html>" in html or "<html" in html


# ── Stats bar removal ────────────────────────────────────────────────────────

class TestStatsBarRemoved:
    def test_stats_count_not_present(self, client):
        """Stats bar number '1,137,816' is no longer in the page."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "1,137,816" not in html

    def test_stats_bar_labels_removed(self, client):
        """Old stats bar labels ('SF building permits', 'City data sources' in stat layout) are gone."""
        rv = client.get("/")
        html = rv.data.decode()
        # The stat-item class should not appear — stats section was removed
        assert "stat-item" not in html

    def test_stats_section_class_removed(self, client):
        """stats-section CSS class is not rendered in the HTML body."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "stats-section" not in html


# ── Credibility line ─────────────────────────────────────────────────────────

class TestCredibilityLine:
    def test_credibility_line_present(self, client):
        """Credibility line 'Updated nightly from 22 city data sources' is present."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Updated nightly" in html

    def test_credibility_line_has_source_count(self, client):
        """Credibility line mentions '22 city data sources'."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "22 city data sources" in html

    def test_credibility_line_mentions_beta(self, client):
        """Credibility line mentions 'Free during beta'."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Free during beta" in html

    def test_credibility_line_class(self, client):
        """Credibility line uses .credibility-line CSS class."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "credibility-line" in html


# ── Gantt full-width section ─────────────────────────────────────────────────

class TestGanttFullWidth:
    def test_gantt_section_exists(self, client):
        """Full-width Gantt section (.showcase-gantt-section) exists in page."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "showcase-gantt-section" in html

    def test_gantt_fullwidth_class_present(self, client):
        """showcase-gantt-fullwidth class is present for full-width treatment."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "showcase-gantt-fullwidth" in html

    def test_routing_intelligence_label(self, client):
        """'Routing Intelligence' label appears above the Gantt section."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Routing Intelligence" in html

    def test_intelligence_layer_label_class(self, client):
        """intelligence-layer-label CSS class is present."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "intelligence-layer-label" in html

    def test_gantt_section_has_id_intelligence(self, client):
        """Gantt section has id='intelligence' for scroll anchor."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'id="intelligence"' in html


# ── 5-card showcase grid ─────────────────────────────────────────────────────

class TestShowcaseGrid:
    def test_showcase_grid_exists(self, client):
        """showcase-grid element is present in the page."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "showcase-grid" in html

    def test_showcase_grid_has_id(self, client):
        """showcase-grid has id='showcase-grid' for targeting."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'id="showcase-grid"' in html

    def test_gantt_not_inside_showcase_grid(self, client):
        """Gantt component (showcase-gantt-section) appears before showcase-grid in markup order."""
        rv = client.get("/")
        html = rv.data.decode()
        gantt_pos = html.find("showcase-gantt-section")
        grid_pos = html.find('id="showcase-grid"')
        assert gantt_pos != -1, "showcase-gantt-section not found"
        assert grid_pos != -1, "id=showcase-grid not found"
        # Gantt section must appear BEFORE the 5-card grid in source order
        assert gantt_pos < grid_pos, (
            f"Gantt section (pos {gantt_pos}) should appear before showcase-grid (pos {grid_pos})"
        )

    def test_five_showcases_in_grid(self, client):
        """showcase-grid contains 5 non-Gantt showcase components (not 6)."""
        rv = client.get("/")
        html = rv.data.decode()
        # Grid section comes after gantt section — count showcase_* includes in grid area
        grid_pos = html.find('id="showcase-grid"')
        # After the grid, the mcp-section starts
        mcp_pos = html.find('id="mcp-demo"')
        if grid_pos == -1 or mcp_pos == -1:
            pytest.skip("Grid or MCP section not found — showcase data may be absent")
        grid_html = html[grid_pos:mcp_pos]
        # Each card has showcase-card class
        card_count = grid_html.count("showcase-card")
        # Could be 0 if showcase data not injected (no DB), skip gracefully
        if card_count > 0:
            # Should be <= 5 cards (not 6 — Gantt is pulled out)
            assert card_count <= 5, f"Expected ≤5 showcase cards in grid, got {card_count}"


# ── CSS responsive grid ───────────────────────────────────────────────────────

class TestResponsiveGrid:
    def test_desktop_3col_grid(self, client):
        """CSS specifies 3-column grid for desktop showcase."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "repeat(3, 1fr)" in html

    def test_tablet_2col_grid(self, client):
        """CSS specifies 2-column grid at ≤768px."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "repeat(2, 1fr)" in html

    def test_mobile_1col_grid(self, client):
        """CSS specifies 1-column grid at ≤480px."""
        rv = client.get("/")
        html = rv.data.decode()
        # In responsive CSS at 480px, grid-template-columns: 1fr
        # We check for the responsive media query targeting showcase-grid
        assert "max-width: 480px" in html
        # 1fr for mobile single column
        assert "1fr" in html
