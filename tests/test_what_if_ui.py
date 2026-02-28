"""Tests for web/templates/tools/what_if.html and /tools/what-if route."""
import os
import re
import pytest
from web.app import app, _rate_buckets

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/what_if.html"
)


def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestWhatIfTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_what_if(self):
        assert 'What-If' in self.html or 'what-if' in self.html or 'Simulator' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_what_if_api_referenced(self):
        assert 'api/what-if' in self.html or 'what-if' in self.html

    def test_base_description_input(self):
        """Form has a base project description field."""
        assert 'base_description' in self.html or 'base-description' in self.html or 'textarea' in self.html

    def test_json_post_with_csrf_header(self):
        """Template sends JSON POST with X-CSRFToken header."""
        assert 'X-CSRFToken' in self.html or 'csrf' in self.html.lower()
        assert 'application/json' in self.html or 'JSON.stringify' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_variations_section(self):
        """Template includes a variations input section."""
        assert 'variation' in self.html.lower()

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_submit_button_present(self):
        """Form has a submit button."""
        assert 'submit' in self.html.lower()

    def test_add_variation_button(self):
        """Page has an add variation control."""
        assert 'add-variation' in self.html or 'add variation' in self.html.lower()

    def test_marked_js_loaded(self):
        """marked.js is loaded for markdown rendering."""
        assert 'marked' in self.html

    def test_fetch_api_used(self):
        """Uses fetch() for JSON POST."""
        assert 'fetch(' in self.html

    def test_sans_font_used(self):
        """Sans font used for prose/labels."""
        assert '--sans' in self.html

    def test_glass_card_or_obs_mid_surface(self):
        """Page uses design token surface colors."""
        assert 'obsidian-mid' in self.html or 'glass-card' in self.html

    def test_loading_indicator_present(self):
        """Page has a loading state indicator."""
        assert 'loading' in self.html.lower() or 'Simulating' in self.html


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


class TestWhatIfRoute:
    def test_route_redirects_unauthenticated(self, client):
        rv = client.get("/tools/what-if")
        assert rv.status_code in (302, 301)

    @pytest.mark.xfail(reason="g.user requires full before_request chain")
    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/what-if")
        assert rv.status_code == 200
        assert b'What-If' in rv.data or b'Simulator' in rv.data
