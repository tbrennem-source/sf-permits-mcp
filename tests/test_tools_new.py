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
        # Updated QS12: id changed from "results" to "results-area" in UX polish
        assert 'id="results"' in body or 'id="results-area"' in body

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
        # Updated QS12: redesigned from permit-number-input to permit-type select
        assert ('id="permit-number-input"' in body or 'id="assess-btn"' in body
                or 'id="permit-type"' in body or 'id="submit-btn"' in body)

    def test_revision_risk_has_permit_input(self, client):
        """Template should include a permit input field or permit type selector."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        # Updated QS12: redesigned to permit-type select (more accurate tool input)
        assert 'id="permit-number-input"' in body or 'id="permit-type"' in body

    def test_revision_risk_has_assess_button(self, client):
        """Template should include the assess/submit button."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        # Updated QS12: button id changed from assess-btn to submit-btn
        assert 'id="assess-btn"' in body or 'id="submit-btn"' in body or "runRiskAssessment" in body

    def test_revision_risk_has_share_button(self, client):
        """Template should include share button component."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "share-btn" in body or "share-container" in body

    def test_revision_risk_empty_state_present(self, client):
        """Template should render empty/hint state element."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        # Updated QS12: redesigned empty state with empty-state class + demo suggestion
        assert ("results-hint" in body or "Enter a permit number" in body
                or "empty-state" in body or "Predict revision" in body)

    def test_revision_risk_results_content_present(self, client):
        """Template should render results container."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="results"' in body or "results-content" in body

    def test_revision_risk_demo_param_auto_fill(self, client):
        """?permit_type= param page loads fine — input element must be present."""
        resp = client.get("/tools/revision-risk?permit_type=restaurant")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        # Updated QS12: redesigned to use permit-type select instead of permit-number-input
        assert ('id="permit-number-input"' in body or 'id="assess-btn"' in body
                or 'id="permit-type"' in body or 'id="submit-btn"' in body)

    def test_revision_risk_has_analysis_logic(self, client):
        """Template should contain risk assessment logic."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "runRiskAssessment" in body or "revision-risk" in body

    def test_revision_risk_has_trigger_content(self, client):
        """Template should contain trigger/results area."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        # Updated QS12: results panel id changed; results-area or results-panel both valid
        assert "results-area" in body or "results-hint" in body or "results-panel" in body or 'id="results"' in body

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
