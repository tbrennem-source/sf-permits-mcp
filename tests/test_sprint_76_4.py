"""Tests for Sprint 76-4: Obsidian design system migration of 5 admin templates.

Covers:
- admin_ops.html — tab-based ops dashboard
- admin_feedback.html — feedback queue (fragment-aware)
- admin_metrics.html — metrics dashboard with data tables
- admin_costs.html — API cost dashboard with kill switch
- admin_activity.html — activity feed (fragment-aware)

Each template is checked for:
- 200 response with admin auth
- Obsidian design markers (body.obsidian, obs-container, glass-card)
- Preserved functionality (HTMX attributes, tab navigation, Jinja content)
- No 500 errors on render
"""

from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with isolated temp database."""
    db_path = str(tmp_path / "test_sprint764.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client(monkeypatch):
    from web.app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_admin(client, monkeypatch=None, email="admin-sprint764@example.com"):
    """Create admin user and log in."""
    import web.auth as auth_mod
    if monkeypatch:
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    user = auth_mod.get_or_create_user(email)
    # Make admin by setting the admin email env
    import src.db as db_mod
    try:
        db_mod.execute_write(
            "UPDATE users SET is_admin = TRUE WHERE user_id = ?",
            (user["user_id"],),
        )
    except Exception:
        # DuckDB uses ? placeholder; try %s for compatibility
        try:
            db_mod.execute_write(
                "UPDATE users SET is_admin = TRUE WHERE user_id = %s",
                (user["user_id"],),
            )
        except Exception:
            pass
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# 1. admin_ops.html
# ---------------------------------------------------------------------------

class TestAdminOps:
    def test_returns_200_for_admin(self, client, monkeypatch):
        """GET /admin/ops returns 200 for admin user."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        assert rv.status_code == 200

    def test_has_obsidian_class(self, client, monkeypatch):
        """admin_ops template includes body.obsidian class."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "obsidian" in html

    def test_has_obs_container(self, client, monkeypatch):
        """admin_ops template includes obs-container layout wrapper."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "obs-container" in html

    def test_has_glass_card(self, client, monkeypatch):
        """admin_ops template includes glass-card component."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "glass-card" in html

    def test_tab_navigation_preserved(self, client, monkeypatch):
        """admin_ops template preserves tab navigation buttons."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "Pipeline Health" in html
        assert "Data Quality" in html
        assert "User Activity" in html
        assert "Feedback" in html

    def test_htmx_attributes_preserved(self, client, monkeypatch):
        """admin_ops template preserves HTMX tab-loading attributes."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "hx-get" in html
        assert "hx-target" in html

    def test_hash_routing_preserved(self, client, monkeypatch):
        """admin_ops template preserves hash-based tab routing."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "location.hash" in html
        assert "hashAliases" in html

    def test_design_system_css_linked(self, client, monkeypatch):
        """admin_ops template links to design-system.css."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/ops")
        html = rv.data.decode()
        assert "design-system.css" in html


# ---------------------------------------------------------------------------
# 2. admin_feedback.html
# ---------------------------------------------------------------------------

class TestAdminFeedback:
    def test_returns_200_for_admin(self, client, monkeypatch):
        """GET /admin/feedback returns 200 for admin user."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/feedback")
        assert rv.status_code == 200

    def test_has_obsidian_class(self, client, monkeypatch):
        """admin_feedback template includes obsidian class."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/feedback")
        html = rv.data.decode()
        assert "obsidian" in html

    def test_has_glass_card(self, client, monkeypatch):
        """admin_feedback template includes glass-card component."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/feedback")
        html = rv.data.decode()
        assert "glass-card" in html

    def test_filter_buttons_preserved(self, client, monkeypatch):
        """admin_feedback template preserves status filter buttons."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/feedback")
        html = rv.data.decode()
        assert "filter-btn" in html
        assert "All" in html
        assert "Resolved" in html

    def test_empty_state_shown(self, client, monkeypatch):
        """admin_feedback template shows empty state when no feedback."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/feedback")
        html = rv.data.decode()
        # Either empty state or feedback items (both are valid)
        assert "No feedback items" in html or "feedback-item" in html


# ---------------------------------------------------------------------------
# 3. admin_metrics.html
# ---------------------------------------------------------------------------

class TestAdminMetrics:
    def test_returns_200_for_admin(self, client, monkeypatch):
        """GET /admin/metrics returns 200 for admin user."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        assert rv.status_code == 200

    def test_has_obsidian_class(self, client, monkeypatch):
        """admin_metrics template includes obsidian class."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "obsidian" in html

    def test_has_obs_container(self, client, monkeypatch):
        """admin_metrics template includes obs-container."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "obs-container" in html

    def test_has_glass_card(self, client, monkeypatch):
        """admin_metrics template includes glass-card."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "glass-card" in html

    def test_three_data_sections_present(self, client, monkeypatch):
        """admin_metrics template has all three data sections."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "Permit Issuance Trends" in html
        assert "Station SLA Compliance" in html
        assert "Planning Velocity" in html

    def test_back_link_present(self, client, monkeypatch):
        """admin_metrics template has back link to /admin/ops."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "/admin/ops" in html

    def test_design_system_css_linked(self, client, monkeypatch):
        """admin_metrics template links to design-system.css."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/metrics")
        html = rv.data.decode()
        assert "design-system.css" in html


# ---------------------------------------------------------------------------
# 4. admin_costs.html
# ---------------------------------------------------------------------------

class TestAdminCosts:
    def test_returns_200_for_admin(self, client, monkeypatch):
        """GET /admin/costs returns 200 for admin user."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        assert rv.status_code == 200

    def test_has_obsidian_class(self, client, monkeypatch):
        """admin_costs template includes obsidian class."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "obsidian" in html

    def test_has_obs_container(self, client, monkeypatch):
        """admin_costs template includes obs-container."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "obs-container" in html

    def test_has_glass_card(self, client, monkeypatch):
        """admin_costs template includes glass-card."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "glass-card" in html

    def test_kill_switch_panel_preserved(self, client, monkeypatch):
        """admin_costs template preserves kill switch panel."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "kill-switch" in html or "Kill switch" in html

    def test_signal_colors_used(self, client, monkeypatch):
        """admin_costs template uses Obsidian signal color tokens."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "signal-green" in html or "signal-red" in html or "signal-amber" in html

    def test_alert_banner_present(self, client, monkeypatch):
        """admin_costs template renders alert banner section."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/costs")
        html = rv.data.decode()
        assert "alert-banner" in html


# ---------------------------------------------------------------------------
# 5. admin_activity.html
# ---------------------------------------------------------------------------

class TestAdminActivity:
    def test_returns_200_for_admin(self, client, monkeypatch):
        """GET /admin/activity returns 200 for admin user."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        assert rv.status_code == 200

    def test_has_obsidian_class(self, client, monkeypatch):
        """admin_activity template includes obsidian class."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "obsidian" in html

    def test_has_obs_container(self, client, monkeypatch):
        """admin_activity template includes obs-container."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "obs-container" in html

    def test_has_glass_card(self, client, monkeypatch):
        """admin_activity template includes glass-card."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "glass-card" in html

    def test_filter_functionality_preserved(self, client, monkeypatch):
        """admin_activity template preserves user filter dropdown."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "filterByUser" in html
        assert "All users" in html

    def test_activity_feed_section_present(self, client, monkeypatch):
        """admin_activity template renders activity feed heading."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "Activity Feed" in html

    def test_design_system_css_linked(self, client, monkeypatch):
        """admin_activity template links to design-system.css."""
        _login_admin(client, monkeypatch)
        rv = client.get("/admin/activity")
        html = rv.data.decode()
        assert "design-system.css" in html
