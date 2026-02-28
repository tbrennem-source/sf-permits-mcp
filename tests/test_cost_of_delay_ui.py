"""Tests for web/templates/tools/cost_of_delay.html and /tools/cost-of-delay route.

Operates via string search on template file contents (no Jinja rendering required).
Route tests use Flask test client with TESTING mode.
"""
import os
import re
import pytest
from web.app import app, _rate_buckets

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/cost_of_delay.html"
)


def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestCostOfDelayTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_cost_of_delay(self):
        assert 'Cost' in self.html or 'Delay' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_delay_cost_api_referenced(self):
        assert 'delay-cost' in self.html or 'api/delay-cost' in self.html

    def test_permit_type_input(self):
        """Form has a permit type field."""
        assert 'permit_type' in self.html or 'permit-type' in self.html or 'permit type' in self.html.lower()

    def test_monthly_cost_input(self):
        """Form has a monthly carrying cost field."""
        assert 'monthly_carrying_cost' in self.html or 'monthly' in self.html.lower()

    def test_json_post_with_csrf(self):
        """Template sends JSON POST with CSRF token."""
        assert 'X-CSRFToken' in self.html or 'csrf' in self.html.lower()
        assert 'application/json' in self.html or 'JSON.stringify' in self.html

    def test_client_side_validation(self):
        """Template validates monthly cost > 0 before submission."""
        assert 'parseFloat' in self.html or 'validation' in self.html.lower() or '> 0' in self.html or 'must be' in self.html.lower()

    def test_no_hardcoded_hex_in_styles(self):
        """No hardcoded hex values in style blocks (only token vars allowed)."""
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_sans_font_used(self):
        assert '--sans' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        """Template shows a log-in prompt or handles 401 auth errors."""
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_optional_neighborhood_field(self):
        """Form has optional neighborhood input."""
        assert 'neighborhood' in self.html.lower()

    def test_optional_triggers_field(self):
        """Form has optional triggers input."""
        assert 'trigger' in self.html.lower()

    def test_glass_card_class_used(self):
        """Page uses glass-card component for card surfaces."""
        assert 'glass-card' in self.html

    def test_action_btn_class_used(self):
        """Submit button uses action-btn token class."""
        assert 'action-btn' in self.html

    def test_obs_container_layout(self):
        """Page uses obs-container for layout."""
        assert 'obs-container' in self.html

    def test_fetch_with_json_body(self):
        """JavaScript fetch posts JSON with correct content type."""
        assert 'JSON.stringify' in self.html
        assert 'Content-Type' in self.html

    def test_marked_js_loaded(self):
        """marked.js library is loaded for markdown rendering."""
        assert 'marked' in self.html

    def test_loading_state_present(self):
        """A loading indicator is shown while the request is in flight."""
        assert 'loading' in self.html.lower() or 'Calculating' in self.html

    def test_marked_parse_called(self):
        """Result is rendered through marked.parse()."""
        assert 'marked.parse' in self.html

    def test_optional_labels_present(self):
        """Optional fields are visually labeled as optional."""
        assert 'optional' in self.html.lower()

    def test_obsidian_background_token(self):
        """Page uses --obsidian token for body background."""
        assert '--obsidian' in self.html

    def test_text_primary_token_used(self):
        assert '--text-primary' in self.html

    def test_text_secondary_token_used(self):
        assert '--text-secondary' in self.html


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


class TestCostOfDelayRoute:
    def test_route_redirects_unauthenticated(self, client):
        """Unauthenticated request to /tools/cost-of-delay redirects to login."""
        rv = client.get("/tools/cost-of-delay")
        assert rv.status_code in (302, 301)

    def test_route_redirect_target_is_login(self, client):
        """Unauthenticated redirect sends user to /auth/login."""
        rv = client.get("/tools/cost-of-delay")
        location = rv.headers.get('Location', '')
        assert 'login' in location or 'auth' in location

    @pytest.mark.xfail(reason="g.user requires full before_request chain (user lookup from DB) not available in test_client TESTING mode")
    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/cost-of-delay")
        assert rv.status_code == 200
        assert b'Cost' in rv.data or b'Delay' in rv.data
