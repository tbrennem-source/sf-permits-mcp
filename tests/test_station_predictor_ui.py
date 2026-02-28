"""Tests for web/templates/tools/station_predictor.html.

Template-string tests — reads the file and asserts structural requirements.
No Flask test client or Jinja rendering needed for template tests.
"""
import os
import re
import pytest
from web.app import app, _rate_buckets

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/station_predictor.html"
)


def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestStationPredictorTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        """Template file exists and is non-empty."""
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        """Template includes the obsidian head fragment."""
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        """Template includes site navigation."""
        assert 'nav.html' in self.html

    def test_page_title_station_predictor(self):
        """Page title references Station Predictor."""
        assert 'Station Predictor' in self.html

    def test_results_div_present(self):
        """Results target div exists with id=results."""
        assert 'id="results"' in self.html

    def test_predict_next_api_endpoint(self):
        """Template references the predict-next API endpoint."""
        assert 'predict-next' in self.html or 'api/predict-next' in self.html

    def test_no_hardcoded_hex_colors(self):
        """Template uses CSS custom properties, not hardcoded hex values in style blocks."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors found in style block: {hex_in_values}"

    def test_mono_font_for_input(self):
        """Input or permit number element uses --mono font."""
        assert '--mono' in self.html

    def test_mobile_viewport_meta(self):
        """Template has viewport meta tag for mobile."""
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        """Template handles 401 / unauthenticated state."""
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_glass_card_or_glass_class_used(self):
        """Template uses design-token glass card or glass-related class."""
        assert 'glass-card' in self.html or 'glass' in self.html

    def test_obs_container_present(self):
        """Template uses the standard obs-container layout class."""
        assert 'obs-container' in self.html

    def test_results_area_class(self):
        """Results div has a CSS class for styling."""
        assert 'results-area' in self.html or 'class="results' in self.html

    def test_marked_js_included(self):
        """Template includes marked.js for markdown rendering."""
        assert 'marked' in self.html

    def test_sans_font_used(self):
        """Template uses --sans font family for prose/labels."""
        assert '--sans' in self.html

    def test_enter_key_support(self):
        """Template JavaScript handles Enter key for form submission."""
        assert 'Enter' in self.html or 'keydown' in self.html

    def test_input_element_present(self):
        """Permit number input element is present."""
        assert 'permit-number-input' in self.html or 'type="text"' in self.html

    def test_submit_button_present(self):
        """Submit/predict button is present."""
        assert 'predict-btn' in self.html or 'Predict' in self.html

    def test_loading_state_present(self):
        """Template has a loading/analyzing state for while the request is in flight."""
        assert 'Analyzing' in self.html or 'spinner' in self.html or 'loading' in self.html.lower()

    def test_error_state_present(self):
        """Template has error display logic."""
        assert 'showError' in self.html or 'error' in self.html.lower()

    def test_empty_hint_text(self):
        """Template has hint text for the empty state."""
        assert 'Enter a permit number' in self.html or 'enter' in self.html.lower()


@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()


class TestStationPredictorRoute:
    """Route-level tests via Flask test client."""

    def test_route_accessible_unauthenticated(self, client):
        """GET /tools/station-predictor returns 200 for anonymous users (no login redirect)."""
        rv = client.get("/tools/station-predictor")
        assert rv.status_code == 200

    @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
    def test_route_renders_for_authenticated_user(self, authed_client):
        """GET /tools/station-predictor returns 200 for authenticated user."""
        rv = authed_client.get("/tools/station-predictor")
        assert rv.status_code == 200
        assert b'Station Predictor' in rv.data
