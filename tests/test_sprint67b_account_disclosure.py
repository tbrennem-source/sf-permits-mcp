"""Tests for Sprint 67-B: Account Page + Progressive Disclosure.

Verifies progressive disclosure CSS classes, tier visibility classes,
account tab visual hierarchy, and landing page CTA improvements.
"""

import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STYLE_CSS = ROOT / "web" / "static" / "style.css"
TEMPLATES = ROOT / "web" / "templates"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


class TestStyleCssClasses:
    """Verify style.css contains required utility classes."""

    def setup_method(self):
        self.css = STYLE_CSS.read_text()

    def test_disclosure_panel_class(self):
        """disclosure-panel class exists with collapsed default state."""
        assert ".disclosure-panel" in self.css
        assert "max-height: 0" in self.css

    def test_disclosure_open_class(self):
        """disclosure-open modifier expands the panel."""
        assert ".disclosure-panel.disclosure-open" in self.css
        assert "opacity: 1" in self.css

    def test_disclosure_trigger_class(self):
        """disclosure-trigger has cursor and arrow indicator."""
        assert ".disclosure-trigger" in self.css
        assert "cursor: pointer" in self.css

    def test_tier_free_class(self):
        """tier-free class exists."""
        assert ".tier-free" in self.css

    def test_tier_pro_class(self):
        """tier-pro class is hidden by default."""
        assert ".tier-pro" in self.css
        assert "display: none" in self.css

    def test_tier_pro_body_class(self):
        """tier-pro becomes visible when body has user-pro class."""
        assert "body.user-pro .tier-pro" in self.css

    def test_tier_upgrade_nudge(self):
        """tier-upgrade-nudge exists for free user upsell."""
        assert ".tier-upgrade-nudge" in self.css

    def test_tab_divider_class(self):
        """tab-divider separator class exists."""
        assert ".tab-divider" in self.css

    def test_tab_admin_badge(self):
        """tab-admin-badge class for admin tab visual hierarchy."""
        assert ".tab-admin-badge" in self.css

    def test_tab_bar_divided(self):
        """tab-bar-divided class provides divided tab layout."""
        assert ".tab-bar-divided" in self.css


class TestAccountPageTabs:
    """Verify account page uses improved tab navigation."""

    def test_account_has_style_css_link(self):
        """account.html should link to style.css."""
        html = (TEMPLATES / "account.html").read_text()
        assert "style.css" in html

    def test_account_has_tab_divider(self):
        """account.html should use tab-divider between Settings and Admin."""
        html = (TEMPLATES / "account.html").read_text()
        assert "tab-divider" in html

    def test_account_has_admin_badge(self):
        """account.html should show admin badge on the Admin tab."""
        html = (TEMPLATES / "account.html").read_text()
        assert "tab-admin-badge" in html

    def test_account_has_divided_bar(self):
        """account.html should use tab-bar-divided class."""
        html = (TEMPLATES / "account.html").read_text()
        assert "tab-bar-divided" in html


class TestAccountPageRenders:
    """Verify account page renders correctly for authenticated users."""

    @staticmethod
    def _login(client, email="account-test@test.com"):
        """Helper: create a user and log them in."""
        import src.db as db_mod
        if db_mod.BACKEND == "duckdb":
            db_mod.init_user_schema()
        from web.auth import get_or_create_user, create_magic_token
        user = get_or_create_user(email)
        token = create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        return user

    def test_account_page_renders_for_user(self):
        """Account page renders 200 for authenticated user."""
        app.config["TESTING"] = True
        _rate_buckets.clear()
        with app.test_client() as client:
            self._login(client)
            rv = client.get("/account")
            assert rv.status_code == 200
            html = rv.data.decode()
            assert "My Account" in html
            assert "Profile" in html
        _rate_buckets.clear()

    def test_account_includes_settings_fragment(self):
        """Account page includes the settings fragment content."""
        app.config["TESTING"] = True
        _rate_buckets.clear()
        with app.test_client() as client:
            self._login(client)
            rv = client.get("/account")
            html = rv.data.decode()
            assert "Watch List" in html
            assert "Email Preferences" in html
        _rate_buckets.clear()


class TestLandingPageCTA:
    """Verify landing page has improved CTA section."""

    def test_landing_has_cta_section(self):
        """Landing page has a CTA banner for free account creation."""
        html = (TEMPLATES / "landing.html").read_text()
        assert "Create free account" in html

    def test_landing_has_feature_benefits(self):
        """Landing page CTA lists key benefits."""
        html = (TEMPLATES / "landing.html").read_text()
        assert "No credit card" in html
        assert "Watch up to 25 properties" in html
        assert "Daily email briefs" in html

    def test_landing_has_style_css_link(self):
        """Landing page links to style.css."""
        html = (TEMPLATES / "landing.html").read_text()
        assert "style.css" in html

    def test_landing_has_auth_link_in_cta(self):
        """Landing page CTA points to /auth/login."""
        html = (TEMPLATES / "landing.html").read_text()
        # Should have the CTA section with auth link
        assert 'href="/auth/login"' in html
