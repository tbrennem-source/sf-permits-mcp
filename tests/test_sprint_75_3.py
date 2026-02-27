"""Tests for Sprint 75-3: Obsidian migration — 5 user templates.

Covers:
  - account.html (full page — authenticated)
  - search_results.html (HTMX fragment — Obsidian CSS classes added)
  - analyze_plans_complete.html (HTMX fragment)
  - analyze_plans_results.html (HTMX fragment)
  - analyze_plans_polling.html (HTMX fragment)

All template checks use static file reads since fragments render within
authenticated contexts that are expensive to mock end-to-end.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_s75_3.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Helper — read template file directly
# ---------------------------------------------------------------------------

def read_template(name):
    """Read a template file from the templates directory."""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "templates")
    with open(os.path.join(base, name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. account.html
# ---------------------------------------------------------------------------

class TestAccountTemplate:
    """account.html Obsidian migration checks."""

    def test_account_has_doctype(self):
        """account.html is a full page with DOCTYPE."""
        html = read_template("account.html")
        assert "<!DOCTYPE html>" in html

    def test_account_has_obsidian_body_class(self):
        """account.html body tag has class='obsidian'."""
        html = read_template("account.html")
        assert 'class="obsidian"' in html

    def test_account_includes_head_obsidian(self):
        """account.html includes head_obsidian fragment."""
        html = read_template("account.html")
        assert 'include "fragments/head_obsidian.html"' in html

    def test_account_uses_obs_container(self):
        """account.html wraps content in .obs-container."""
        html = read_template("account.html")
        assert 'obs-container' in html

    def test_account_no_hardcoded_bg_color(self):
        """account.html does not hardcode --bg: #0f1117."""
        html = read_template("account.html")
        assert "--bg: #0f1117" not in html

    def test_account_no_hardcoded_font_stack(self):
        """account.html does not use -apple-system font stack."""
        html = read_template("account.html")
        assert "-apple-system" not in html

    def test_account_card_alias_defined(self):
        """account.html defines .card as glass-card alias for fragments."""
        html = read_template("account.html")
        assert ".card {" in html or ".card{" in html

    def test_account_uses_obsidian_token_vars(self):
        """account.html uses Obsidian design token variables."""
        html = read_template("account.html")
        assert "var(--signal-cyan)" in html or "var(--bg-surface)" in html or "var(--text-secondary)" in html

    def test_account_tab_btn_uses_obsidian_vars(self):
        """account.html tab buttons use Obsidian signal-cyan for active state."""
        html = read_template("account.html")
        assert "var(--signal-cyan)" in html

    def test_account_htmx_script_preserved(self):
        """account.html still loads htmx."""
        html = read_template("account.html")
        assert "htmx.min.js" in html

    def test_account_nav_include_preserved(self):
        """account.html includes nav fragment."""
        html = read_template("account.html")
        assert "fragments/nav.html" in html

    def test_account_feedback_widget_preserved(self):
        """account.html includes feedback_widget fragment."""
        html = read_template("account.html")
        assert "fragments/feedback_widget.html" in html


# ---------------------------------------------------------------------------
# 2. search_results.html
# ---------------------------------------------------------------------------

class TestSearchResultsTemplate:
    """search_results.html Obsidian migration checks."""

    def test_search_results_is_fragment(self):
        """search_results.html is an HTMX fragment (no DOCTYPE)."""
        html = read_template("search_results.html")
        assert "<!DOCTYPE" not in html

    def test_search_results_has_glass_card_on_root(self):
        """search_results.html root wrapper has glass-card class."""
        html = read_template("search_results.html")
        assert 'class="result-card search-result-card glass-card"' in html

    def test_search_results_quick_actions_uses_glass_card(self):
        """Quick Actions section uses glass-card class."""
        html = read_template("search_results.html")
        assert 'glass-card' in html
        # Should appear more than once (root + quick actions)
        assert html.count('glass-card') >= 2

    def test_search_results_primary_btn_uses_obsidian_class(self):
        """View Property Report button uses obsidian-btn-primary."""
        html = read_template("search_results.html")
        assert 'obsidian-btn-primary' in html

    def test_search_results_outline_btns_used(self):
        """Analyze Project and Who's Here buttons use obsidian-btn-outline."""
        html = read_template("search_results.html")
        assert 'obsidian-btn-outline' in html

    def test_search_results_no_results_uses_glass_card(self):
        """No-results block uses glass-card class."""
        html = read_template("search_results.html")
        # The no-results div should have glass-card
        assert 'class="glass-card"' in html or "glass-card" in html

    def test_search_results_jinja_logic_preserved(self):
        """Critical Jinja logic variables still present."""
        html = read_template("search_results.html")
        assert "show_quick_actions" in html
        assert "report_url" in html
        assert "violation_counts" in html
        assert "active_businesses" in html
        assert "no_results" in html

    def test_search_results_htmx_attributes_preserved(self):
        """HTMX attributes are preserved in search_results."""
        html = read_template("search_results.html")
        assert "hx-post" in html
        assert "hx-target" in html
        assert "hx-swap" in html


# ---------------------------------------------------------------------------
# 3. analyze_plans_complete.html
# ---------------------------------------------------------------------------

class TestAnalyzePlansCompleteTemplate:
    """analyze_plans_complete.html Obsidian migration checks."""

    def test_complete_is_fragment(self):
        """analyze_plans_complete.html is an HTMX fragment (no DOCTYPE)."""
        html = read_template("analyze_plans_complete.html")
        assert "<!DOCTYPE" not in html

    def test_complete_has_glass_card(self):
        """Completion card uses glass-card class."""
        html = read_template("analyze_plans_complete.html")
        assert "glass-card" in html

    def test_complete_view_results_uses_obsidian_btn(self):
        """View Results link uses obsidian-btn-primary class."""
        html = read_template("analyze_plans_complete.html")
        assert "obsidian-btn-primary" in html

    def test_complete_success_color_uses_token(self):
        """Success text uses var(--signal-green) token."""
        html = read_template("analyze_plans_complete.html")
        assert "var(--signal-green)" in html

    def test_complete_job_id_preserved(self):
        """Job ID template variable is preserved."""
        html = read_template("analyze_plans_complete.html")
        assert "job.job_id" in html
        assert "job.filename" in html

    def test_complete_auto_redirect_preserved(self):
        """Auto-redirect script is preserved."""
        html = read_template("analyze_plans_complete.html")
        assert "setTimeout" in html
        assert "window.location.href" in html


# ---------------------------------------------------------------------------
# 4. analyze_plans_results.html
# ---------------------------------------------------------------------------

class TestAnalyzePlansResultsTemplate:
    """analyze_plans_results.html Obsidian migration checks."""

    def test_results_is_fragment(self):
        """analyze_plans_results.html is an HTMX fragment (no DOCTYPE)."""
        html = read_template("analyze_plans_results.html")
        assert "<!DOCTYPE" not in html

    def test_results_root_has_glass_card(self):
        """Root .result-card has glass-card class."""
        html = read_template("analyze_plans_results.html")
        assert 'class="result-card glass-card"' in html

    def test_results_action_btns_use_obsidian(self):
        """Bulk action buttons use obsidian-btn-outline class."""
        html = read_template("analyze_plans_results.html")
        assert "obsidian-btn obsidian-btn-outline" in html

    def test_results_primary_action_btn_exists(self):
        """Email Send button uses obsidian-btn-primary."""
        html = read_template("analyze_plans_results.html")
        assert "obsidian-btn-primary" in html

    def test_results_input_uses_obsidian_class(self):
        """Email inputs use obsidian-input class."""
        html = read_template("analyze_plans_results.html")
        assert "obsidian-input" in html

    def test_results_watch_crossell_uses_glass_card(self):
        """Watch cross-sell prompt uses glass-card."""
        html = read_template("analyze_plans_results.html")
        assert "glass-card" in html

    def test_results_jinja_logic_preserved(self):
        """Critical Jinja variables preserved."""
        html = read_template("analyze_plans_results.html")
        assert "filename" in html
        assert "session_id" in html
        assert "page_count" in html
        assert "result" in html

    def test_results_annotation_js_preserved(self):
        """Annotation JavaScript is preserved."""
        html = read_template("analyze_plans_results.html")
        assert "ANNOTATION_COLORS" in html
        assert "renderAnnotations" in html


# ---------------------------------------------------------------------------
# 5. analyze_plans_polling.html
# ---------------------------------------------------------------------------

class TestAnalyzePlansPollingTemplate:
    """analyze_plans_polling.html Obsidian migration checks."""

    def test_polling_is_fragment(self):
        """analyze_plans_polling.html is an HTMX fragment (no DOCTYPE)."""
        html = read_template("analyze_plans_polling.html")
        assert "<!DOCTYPE" not in html

    def test_polling_cancel_uses_obsidian_btn(self):
        """Cancel Analysis button uses obsidian-btn class."""
        html = read_template("analyze_plans_polling.html")
        assert "obsidian-btn" in html

    def test_polling_htmx_polling_preserved(self):
        """HTMX polling trigger is preserved."""
        html = read_template("analyze_plans_polling.html")
        assert 'hx-trigger="every 3s"' in html
        assert "hx-get" in html

    def test_polling_step_indicator_preserved(self):
        """Progress step indicator structure preserved."""
        html = read_template("analyze_plans_polling.html")
        assert "step-indicator" in html
        assert "step-dot" in html

    def test_polling_elapsed_time_preserved(self):
        """Elapsed time display Jinja logic preserved."""
        html = read_template("analyze_plans_polling.html")
        assert "elapsed_s" in html


# ---------------------------------------------------------------------------
# Route smoke tests (unauthenticated = 302 redirect to login, not 500)
# ---------------------------------------------------------------------------

class TestRouteSmoke:
    """Smoke tests: routes render without 500 errors."""

    def test_account_route_redirects_anon(self, client):
        """GET /account redirects anonymous users (302) not 500."""
        resp = client.get("/account", follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_static_design_system_css(self, client):
        """design-system.css is served successfully."""
        resp = client.get("/static/design-system.css")
        assert resp.status_code == 200

    def test_static_design_system_contains_glass_card(self, client):
        """design-system.css defines .glass-card."""
        resp = client.get("/static/design-system.css")
        assert b"glass-card" in resp.data

    def test_static_design_system_contains_obsidian_btn(self, client):
        """design-system.css defines obsidian-btn classes."""
        resp = client.get("/static/design-system.css")
        assert b"obsidian-btn-primary" in resp.data
        assert b"obsidian-btn-outline" in resp.data
