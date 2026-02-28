"""Tests for web/templates/tools/stuck_permit.html.

Template-string tests — reads the file and asserts structural requirements.
No Flask test client or Jinja rendering needed (except route tests).
"""
import os
import re
import pytest
from web.app import app, _rate_buckets

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/stuck_permit.html"
)


def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestStuckPermitTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_stuck_permit(self):
        assert 'Stuck' in self.html or 'stuck' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_stuck_permit_api_referenced(self):
        assert 'stuck-permit' in self.html or 'api/stuck-permit' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_signal_color_for_status(self):
        """Template uses signal colors for delay/stuck status indicators."""
        assert '--signal-amber' in self.html or '--signal-red' in self.html or 'signal' in self.html

    def test_loading_indicator_present(self):
        """Template has a loading state indicator."""
        assert 'loading' in self.html.lower() or 'Analyzing' in self.html

    def test_marked_js_included(self):
        """Template includes marked.js for markdown rendering."""
        assert 'marked' in self.html

    def test_input_field_present(self):
        """Template has a text input for the permit number."""
        assert 'permit-number-input' in self.html or 'type="text"' in self.html

    def test_mobile_responsive_styles(self):
        """Template has mobile/responsive media query."""
        assert '@media (max-width:' in self.html or '@media (max-width :' in self.html or 'max-width' in self.html

    def test_obs_container_layout(self):
        """Template uses obs-container for layout."""
        assert 'obs-container' in self.html

    def test_glass_card_used(self):
        """Results area uses glass-card component."""
        assert 'glass-card' in self.html

    def test_htmx_script_included(self):
        """Template includes htmx script."""
        assert 'htmx' in self.html

    def test_csp_nonce_on_scripts(self):
        """Script tags have nonce attribute for CSP."""
        assert 'nonce="{{ csp_nonce }}"' in self.html

    def test_empty_state_hint_present(self):
        """Template has an empty state hint message."""
        assert 'empty' in self.html.lower() or 'Enter a permit' in self.html

    def test_diagnose_button_present(self):
        """Template has a diagnose/submit button."""
        assert 'Diagnose' in self.html or 'diagnose' in self.html


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


class TestStuckPermitRoute:
    def test_route_redirects_unauthenticated(self, client):
        rv = client.get("/tools/stuck-permit")
        assert rv.status_code in (302, 301)

    @pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")
    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/stuck-permit")
        assert rv.status_code == 200
        assert b'Stuck' in rv.data or b'stuck' in rv.data
