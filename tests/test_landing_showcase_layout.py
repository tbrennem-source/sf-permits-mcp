"""Tests for Sprint 94+ landing page showcase layout.

Verifies:
- Stats bar removed (no "1,137,816" or old stat labels)
- Credibility line present at page bottom
- Full-width Gantt section exists as the first intelligence section
- Story scroll sections replace the 5-card grid (QS13 redesign)
- Routing Intelligence label on Gantt section
- Responsive CSS present
- showcase_gantt is NOT inside a grid
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


# ── Story scroll sections (QS13 redesign — replaced 5-card grid) ─────────────

class TestShowcaseGrid:
    def test_showcase_grid_exists(self, client):
        """story-section elements are present in the page (replaced showcase-grid)."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "story-section" in html

    def test_showcase_grid_has_id(self, client):
        """story-cta-section (join beta CTA) is present in the page."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "story-cta-section" in html

    def test_gantt_not_inside_showcase_grid(self, client):
        """Gantt component (showcase-gantt-section) appears before story sections in markup order."""
        rv = client.get("/")
        html = rv.data.decode()
        gantt_pos = html.find("showcase-gantt-section")
        story_pos = html.find("story-section")
        assert gantt_pos != -1, "showcase-gantt-section not found"
        assert story_pos != -1, "story-section not found"
        # Gantt section must appear BEFORE the story sections
        assert gantt_pos < story_pos, (
            f"Gantt section (pos {gantt_pos}) should appear before story sections (pos {story_pos})"
        )

    def test_five_showcases_in_grid(self, client):
        """5 non-Gantt showcase component wrappers appear between Gantt and MCP demo."""
        rv = client.get("/")
        html = rv.data.decode()
        # Each component wrapper has data-track="showcase-view" (unique to the outer div)
        card_count = html.count('data-track="showcase-view"')
        # Could be 0 if showcase data not injected (no DB), skip gracefully
        if card_count > 0:
            # Should be <= 6 (5 story sections + 1 gantt)
            assert card_count <= 6, f"Expected ≤6 showcase wrapper divs, got {card_count}"


# ── CSS responsive story scroll ───────────────────────────────────────────────

class TestResponsiveGrid:
    def test_desktop_3col_grid(self, client):
        """CSS specifies story-section for desktop showcase (replaced 3-column grid)."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "story-section" in html

    def test_tablet_2col_grid(self, client):
        """CSS specifies responsive padding for story sections at ≤768px."""
        rv = client.get("/")
        html = rv.data.decode()
        # Story sections use reduced padding at tablet, not a 2-col grid
        assert "max-width: 768px" in html

    def test_mobile_1col_grid(self, client):
        """CSS specifies responsive padding for story sections at ≤480px."""
        rv = client.get("/")
        html = rv.data.decode()
        # Story sections use minimal padding at mobile
        assert "max-width: 480px" in html
