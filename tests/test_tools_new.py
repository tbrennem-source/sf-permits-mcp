"""Tests for new tool pages: Entity Network and Revision Risk.

Sprint QS11-T3-3C — entity_network.html + revision_risk.html routes.
"""

import pytest

from web.app import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Return a Flask test client with TESTING=True."""
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Entity Network — /tools/entity-network
# ---------------------------------------------------------------------------

class TestEntityNetworkRoute:
    """Route and template rendering tests for /tools/entity-network."""

    def test_entity_network_returns_200(self, client):
        """GET /tools/entity-network → 200 OK."""
        resp = client.get("/tools/entity-network")
        assert resp.status_code == 200

    def test_entity_network_content_type_html(self, client):
        """Response should be HTML."""
        resp = client.get("/tools/entity-network")
        assert "text/html" in resp.content_type

    def test_entity_network_has_page_title(self, client):
        """Template should include the page title."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "Entity Network" in body

    def test_entity_network_has_search_input(self, client):
        """Template should render a search input field."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert 'id="entity-input"' in body

    def test_entity_network_has_results_container(self, client):
        """Template should include a results container element."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert 'id="results"' in body

    def test_entity_network_has_analyze_button(self, client):
        """Template should include analyze button."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "runNetworkAnalysis" in body

    def test_entity_network_has_share_button(self, client):
        """Template should include share button component."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "share-btn" in body or "share_button.html" in body or "share-container" in body

    def test_entity_network_empty_state_present(self, client):
        """Template should render empty/hint state element."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "results-hint" in body or "Enter a contractor" in body

    def test_entity_network_address_param_auto_fill(self, client):
        """?address= or ?q= param page loads fine — input element must be present."""
        resp = client.get("/tools/entity-network?address=487+Noe+St")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert 'id="entity-input"' in body

    def test_entity_network_has_network_analysis_logic(self, client):
        """Template should contain network analysis logic."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "runNetworkAnalysis" in body or "entity-network" in body


# ---------------------------------------------------------------------------
# Revision Risk — /tools/revision-risk
# ---------------------------------------------------------------------------

class TestRevisionRiskRoute:
    """Route and template rendering tests for /tools/revision-risk."""

    def test_revision_risk_returns_200(self, client):
        """GET /tools/revision-risk → 200 OK."""
        resp = client.get("/tools/revision-risk")
        assert resp.status_code == 200

    def test_revision_risk_content_type_html(self, client):
        """Response should be HTML."""
        resp = client.get("/tools/revision-risk")
        assert "text/html" in resp.content_type

    def test_revision_risk_has_page_title(self, client):
        """Template should include the page title."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "Revision Risk" in body

    def test_revision_risk_has_form(self, client):
        """Template should render the assessment form input."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="permit-number-input"' in body or 'id="assess-btn"' in body

    def test_revision_risk_has_permit_input(self, client):
        """Template should include permit number input field."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="permit-number-input"' in body

    def test_revision_risk_has_assess_button(self, client):
        """Template should include the assess button."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="assess-btn"' in body or "runRiskAssessment" in body

    def test_revision_risk_has_share_button(self, client):
        """Template should include share button component."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "share-btn" in body or "share-container" in body

    def test_revision_risk_empty_state_present(self, client):
        """Template should render empty/hint state element."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "results-hint" in body or "Enter a permit number" in body

    def test_revision_risk_results_content_present(self, client):
        """Template should render results container."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="results"' in body or "results-content" in body

    def test_revision_risk_demo_param_auto_fill(self, client):
        """?demo= param page loads fine — input element must be present."""
        resp = client.get("/tools/revision-risk?demo=restaurant-mission")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert 'id="permit-number-input"' in body or 'id="assess-btn"' in body

    def test_revision_risk_has_analysis_logic(self, client):
        """Template should contain risk assessment logic."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "runRiskAssessment" in body or "revision-risk" in body

    def test_revision_risk_has_trigger_content(self, client):
        """Template should contain trigger/results area."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "results-area" in body or "results-hint" in body

    def test_revision_risk_has_share_js(self, client):
        """Template should link share.js."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "share.js" in body

    def test_revision_risk_has_assessment_endpoint_ref(self, client):
        """Template JS should reference the revision-risk API endpoint."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "revision-risk" in body

    def test_revision_risk_has_error_handling(self, client):
        """Template should include error handling JS."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "showError" in body or "error" in body.lower()
