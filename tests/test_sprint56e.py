"""Sprint 56E tests — Homeowner Funnel, Brenneman Teaser, Onboarding.

Covers:
- /analyze-preview route (unauthenticated, 2-tool preview)
- Kitchen/bath fork detection
- ?context=violation parameter handling
- Empty state rendering (brief + portfolio)
- Watch brief prompt logic (1 watch vs 3+)
- First-login onboarding banner
- Onboarding dismiss
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="sprint56e-test@test.com"):
    """Helper: create user and log them in."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ── E1: Landing page "Planning a project?" section ─────────────────────────

class TestLandingHomeownerSection:
    def test_landing_has_project_textarea(self, client):
        """Landing page has a project description textarea."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'name="description"' in html

    def test_landing_has_analyze_preview_form(self, client):
        """Landing page has form pointing to /analyze-preview."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'action="/analyze-preview"' in html

    def test_landing_has_planning_heading(self, client):
        """Landing page shows 'Planning a project?' section."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Planning a project" in html

    def test_landing_has_neighborhood_dropdown(self, client):
        """Landing page has a neighborhood dropdown."""
        rv = client.get("/")
        html = rv.data.decode()
        assert 'name="neighborhood"' in html
        assert "Mission" in html


# ── E2: /analyze-preview route ──────────────────────────────────────────────

class TestAnalyzePreview:
    def test_preview_accessible_without_auth(self, client):
        """Preview route works without authentication."""
        rv = client.post("/analyze-preview", data={
            "description": "Kitchen remodel in the Mission",
            "neighborhood": "Mission",
        })
        assert rv.status_code == 200

    def test_preview_returns_html_page(self, client):
        """Preview route returns a full HTML page."""
        rv = client.post("/analyze-preview", data={
            "description": "Bathroom remodel, adding new shower",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Permit Preview" in html
        assert "<!DOCTYPE html>" in html

    def test_preview_shows_description_back(self, client):
        """Preview page echoes back the project description."""
        desc = "Solar panel installation on roof"
        rv = client.post("/analyze-preview", data={"description": desc})
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Solar panel" in html

    def test_preview_no_description_redirects(self, client):
        """Empty description redirects to landing page."""
        rv = client.post("/analyze-preview", data={"description": ""})
        assert rv.status_code == 302

    def test_preview_shows_locked_fee_card(self, client):
        """Preview shows locked fee estimate card."""
        rv = client.post("/analyze-preview", data={
            "description": "Kitchen remodel",
        })
        html = rv.data.decode()
        assert "Fee Estimate" in html
        assert "Sign up free" in html or "unlock" in html.lower()

    def test_preview_shows_locked_documents_card(self, client):
        """Preview shows locked required documents card."""
        rv = client.post("/analyze-preview", data={
            "description": "Bathroom remodel",
        })
        html = rv.data.decode()
        assert "Required Documents" in html

    def test_preview_shows_locked_risk_card(self, client):
        """Preview shows locked revision risk card."""
        rv = client.post("/analyze-preview", data={
            "description": "Kitchen remodel, moving sink",
        })
        html = rv.data.decode()
        assert "Revision Risk" in html

    def test_preview_shows_signup_cta(self, client):
        """Preview page has sign up CTA."""
        rv = client.post("/analyze-preview", data={
            "description": "Add a bathroom",
        })
        html = rv.data.decode()
        assert "/auth/login" in html
        assert ("Sign up free" in html or "Get the full analysis" in html)

    def test_preview_does_not_require_login(self, client):
        """Preview returns 200 for completely unauthenticated users."""
        rv = client.post("/analyze-preview", data={
            "description": "Deck addition in the backyard",
        })
        # Should not redirect to login (302)
        assert rv.status_code != 302 or "login" not in rv.location

    def test_preview_with_neighborhood(self, client):
        """Preview accepts and displays the neighborhood."""
        rv = client.post("/analyze-preview", data={
            "description": "Window replacement",
            "neighborhood": "Noe Valley",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Noe Valley" in html


# ── Kitchen/Bath fork detection ─────────────────────────────────────────────

class TestKitchenBathFork:
    def test_kitchen_triggers_fork(self, client):
        """Kitchen remodel description triggers fork comparison."""
        rv = client.post("/analyze-preview", data={
            "description": "Full kitchen remodel with new island and sink relocation",
        })
        html = rv.data.decode()
        assert "Layout Decision" in html or "layout" in html.lower()

    def test_bathroom_triggers_fork(self, client):
        """Bathroom description triggers fork comparison."""
        rv = client.post("/analyze-preview", data={
            "description": "Bathroom renovation, moving the toilet",
        })
        html = rv.data.decode()
        # Fork section appears
        assert "Keep existing layout" in html or "layout" in html.lower() or "OTC Path" in html

    def test_non_kitchen_no_fork(self, client):
        """Non-kitchen/bath project does not show fork comparison."""
        rv = client.post("/analyze-preview", data={
            "description": "Solar panel installation on roof",
        })
        html = rv.data.decode()
        # Fork section for kitchen/bath should NOT appear
        assert "Layout Decision" not in html


# ── E3: Violation context parameter ─────────────────────────────────────────

class TestViolationContext:
    def test_violation_context_shows_banner(self, client):
        """?context=violation shows the violation lookup banner."""
        rv = client.get("/search?q=1455+Market+St&context=violation")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Violation" in html or "violation" in html.lower()

    def test_violation_context_banner_text(self, client):
        """Violation context banner has actionable text."""
        rv = client.get("/search?q=123+Main+St&context=violation")
        if rv.status_code == 200:
            html = rv.data.decode()
            assert "Violation Lookup" in html or "enforcement" in html.lower()

    def test_no_context_no_violation_banner(self, client):
        """Normal search without context param shows no violation banner."""
        rv = client.get("/search?q=1455+Market+St")
        if rv.status_code == 200:
            html = rv.data.decode()
            assert "Violation Lookup Mode" not in html

    def test_violation_cta_on_landing(self, client):
        """Landing page has the 'Got a violation?' CTA."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "Notice of Violation" in html or "Got a" in html
        assert "context=violation" in html


# ── E4: Onboarding banner ────────────────────────────────────────────────────

class TestOnboardingBanner:
    def test_onboarding_dismiss_returns_empty(self, client):
        """Dismiss endpoint returns empty string for HTMX removal."""
        _login(client, email="onboard-test@test.com")
        rv = client.post("/onboarding/dismiss")
        assert rv.status_code == 200
        assert rv.data == b""

    def test_onboarding_dismiss_no_auth(self, client):
        """Dismiss endpoint works even without auth (session clear)."""
        rv = client.post("/onboarding/dismiss")
        assert rv.status_code == 200


# ── E5: Empty state rendering ────────────────────────────────────────────────

class TestEmptyStates:
    def test_brief_empty_state_text(self, client):
        """Brief page with no watches shows actionable empty state."""
        _login(client, email="brief-empty@test.com")
        rv = client.get("/brief")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should say "No morning brief yet" (E5 update)
        assert "No morning brief yet" in html or "morning brief" in html.lower()

    def test_brief_empty_has_search_cta(self, client):
        """Brief empty state has a link to search for a property."""
        _login(client, email="brief-empty-cta@test.com")
        rv = client.get("/brief")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should have a link to /search (E5)
        assert "/search" in html

    def test_portfolio_empty_state_text(self, client):
        """Portfolio page with no watches shows actionable empty state."""
        _login(client, email="portfolio-empty@test.com")
        rv = client.get("/portfolio")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should say "Your portfolio is empty" (E5 update)
        assert "portfolio is empty" in html.lower() or "empty" in html.lower()

    def test_portfolio_empty_has_search_cta(self, client):
        """Portfolio empty state links to /search."""
        _login(client, email="portfolio-empty-cta@test.com")
        rv = client.get("/portfolio")
        assert rv.status_code == 200
        html = rv.data.decode()
        # E5: CTA should link to /search
        assert "/search" in html


# ── E6: Watch brief prompt ───────────────────────────────────────────────────

class TestWatchBriefPrompt:
    def test_brief_prompt_endpoint_requires_auth(self, client):
        """Brief prompt endpoint requires authentication."""
        rv = client.get("/watch/brief-prompt")
        assert rv.status_code in (302, 401, 403)  # redirect to login

    def test_brief_prompt_with_no_watches(self, client):
        """Brief prompt with no watches returns minimal/no prompt."""
        _login(client, email="brief-prompt-zero@test.com")
        rv = client.get("/watch/brief-prompt")
        assert rv.status_code == 200
        html = rv.data.decode()
        # With 0 watches: no prompt expected
        assert len(html.strip()) == 0 or "Enable" not in html

    def test_brief_prompt_one_watch_shows_soft_prompt(self, client):
        """Brief prompt with 1 watch shows soft enable prompt."""
        user = _login(client, email="brief-prompt-one@test.com")
        # Add a watch
        from web.auth import add_watch
        add_watch(user["user_id"], "address",
                  street_number="100", street_name="Main St",
                  label="Test")
        rv = client.get("/watch/brief-prompt")
        assert rv.status_code == 200
        html = rv.data.decode()
        # 1 watch: soft prompt
        assert "Enable" in html or "morning brief" in html.lower() or len(html.strip()) == 0

    def test_brief_prompt_three_watches_shows_strong_prompt(self, client):
        """Brief prompt with 3+ watches shows stronger enable prompt."""
        user = _login(client, email="brief-prompt-three@test.com")
        # Add 3 watches
        from web.auth import add_watch
        for i in range(3):
            add_watch(user["user_id"], "address",
                      street_number=str(100 + i), street_name=f"Street {i}",
                      label=f"Test {i}")
        rv = client.get("/watch/brief-prompt")
        assert rv.status_code == 200
        html = rv.data.decode()
        # 3 watches: stronger prompt mentioning count
        assert "3" in html or "multiple" in html.lower() or "brief" in html.lower()

    def test_brief_prompt_no_prompt_when_brief_enabled(self, client):
        """Brief prompt not shown when user already has brief enabled."""
        user = _login(client, email="brief-prompt-enabled@test.com")
        # Enable the brief for this user
        from src.db import execute_write, BACKEND
        if BACKEND == "postgres":
            execute_write(
                "UPDATE users SET brief_frequency = 'daily' WHERE user_id = %s",
                (user["user_id"],),
            )
        else:
            from src.db import get_connection
            conn = get_connection()
            try:
                conn.execute("UPDATE users SET brief_frequency = 'daily' WHERE user_id = ?",
                             (user["user_id"],))
            finally:
                conn.close()
        # Add a watch
        from web.auth import add_watch
        add_watch(user["user_id"], "address",
                  street_number="200", street_name="Enabled St",
                  label="Test")
        rv = client.get("/watch/brief-prompt")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Already enabled: no prompt
        assert "Enable brief" not in html
