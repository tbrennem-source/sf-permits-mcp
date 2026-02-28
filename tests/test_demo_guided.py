"""Tests for /demo/guided — self-guided walkthrough page (Sprint 97).

Verifies:
- Route returns 200 (public, no auth required)
- All 6 content sections present
- Correct links with expected query params
- Uses Obsidian template base
"""

import pytest

from web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestDemoGuidedRoute:
    def test_route_returns_200(self, client):
        """GET /demo/guided returns HTTP 200 without authentication."""
        rv = client.get("/demo/guided")
        assert rv.status_code == 200

    def test_page_uses_obsidian_template(self, client):
        """Page extends the Obsidian template base (head_obsidian.html)."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        # head_obsidian.html injects the obsidian CSS variables
        assert "obsidian" in html.lower()

    def test_section1_hero_heading(self, client):
        """Section 1 hero contains the primary heading."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "See what sfpermits.ai does" in html

    def test_section1_hero_subtitle(self, client):
        """Section 1 hero contains the subtitle about 2-minute walkthrough."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "2-minute walkthrough" in html

    def test_section2_gantt_content(self, client):
        """Section 2 contains review station content."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "review station" in html

    def test_section2_station_predictor_link(self, client):
        """Section 2 has a link to the station predictor tool."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "station-predictor" in html

    def test_section3_search_link(self, client):
        """Section 3 contains a pre-filled search link with /search?q= param."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "/search?q=" in html
        assert "487 Noe St" in html or "487+Noe+St" in html

    def test_section3_search_subtext(self, client):
        """Section 3 has subtext about real permit data."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "real permits" in html

    def test_section4_stuck_permit_tool(self, client):
        """Section 4 has link to stuck-permit tool with demo permit number."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "stuck-permit" in html
        assert "202412237330" in html

    def test_section4_revision_risk_tool(self, client):
        """Section 4 has link to revision-risk tool."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "revision-risk" in html
        assert "demo=restaurant-mission" in html

    def test_section4_what_if_tool(self, client):
        """Section 4 has link to what-if / scope comparison tool."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "what-if" in html
        assert "demo=kitchen-vs-full" in html

    def test_section4_cost_of_delay_tool(self, client):
        """Section 4 has link to cost-of-delay tool."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "cost-of-delay" in html
        assert "demo=restaurant-15k" in html

    def test_section5_amy_content(self, client):
        """Section 5 references Amy / professionals use case."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "Amy" in html

    def test_section5_morning_triage(self, client):
        """Section 5 mentions morning triage workflow."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "Morning triage" in html or "morning triage" in html

    def test_section5_reviewer_lookup(self, client):
        """Section 5 mentions reviewer lookup."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "Reviewer lookup" in html or "reviewer lookup" in html

    def test_section5_intervention_playbooks(self, client):
        """Section 5 mentions intervention playbooks."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "playbook" in html.lower()

    def test_section6_connect_ai_heading(self, client):
        """Section 6 has Connect Your AI heading."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "Claude" in html or "ChatGPT" in html or "AI assistant" in html

    def test_section6_tools_count(self, client):
        """Section 6 references 34 intelligence tools."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "34" in html

    def test_section6_learn_more_link(self, client):
        """Section 6 has a learn more CTA linking to /methodology."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert "/methodology" in html

    def test_footer_home_link(self, client):
        """Footer has a link back to the landing page."""
        rv = client.get("/demo/guided")
        html = rv.data.decode()
        assert 'href="/"' in html
