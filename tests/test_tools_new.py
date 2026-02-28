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
        assert 'id="network-search"' in body

    def test_entity_network_has_graph_container(self, client):
        """Template should include the D3 graph container element."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert 'id="graph-container"' in body

    def test_entity_network_loads_d3(self, client):
        """Template should load D3 from CDN."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "d3js.org/d3.v7.min.js" in body

    def test_entity_network_loads_entity_graph_js(self, client):
        """Template should include entity-graph.js."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert "entity-graph.js" in body

    def test_entity_network_empty_state_present(self, client):
        """Template should render empty state element."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert 'id="graph-empty"' in body

    def test_entity_network_address_param_auto_fill(self, client):
        """?address= param page loads fine — input auto-fill hook exists in JS."""
        resp = client.get("/tools/entity-network?address=487+Noe+St")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        # JS reads ?address= via URLSearchParams; the input element must be present
        assert 'id="network-search"' in body

    def test_entity_network_entity_detail_sidebar(self, client):
        """Template should render entity detail sidebar."""
        resp = client.get("/tools/entity-network")
        body = resp.data.decode("utf-8")
        assert 'id="entity-detail"' in body


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
        """Template should render the assessment form."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="risk-form"' in body

    def test_revision_risk_has_permit_type_dropdown(self, client):
        """Template should include permit type dropdown."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="permit-type"' in body

    def test_revision_risk_has_neighborhood_dropdown(self, client):
        """Template should include neighborhood dropdown."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="neighborhood"' in body

    def test_revision_risk_has_project_type_input(self, client):
        """Template should include project description text input."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="project-type"' in body

    def test_revision_risk_empty_state_present(self, client):
        """Template should render empty state element."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="results-empty"' in body

    def test_revision_risk_results_content_present(self, client):
        """Template should render results content container."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'id="results-content"' in body

    def test_revision_risk_demo_param_auto_fill(self, client):
        """?demo=restaurant-mission returns 200 — auto-fill hook exists in JS."""
        resp = client.get("/tools/revision-risk?demo=restaurant-mission")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8")
        assert 'id="risk-form"' in body

    def test_revision_risk_has_gauge_js(self, client):
        """Template should contain JS / HTML for rendering the risk gauge."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "renderGauge" in body or "gauge-card" in body

    def test_revision_risk_has_trigger_list_js(self, client):
        """Template should contain JS / HTML for rendering correction triggers."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "renderTriggers" in body or "triggers-card" in body

    def test_revision_risk_has_mitigation_js(self, client):
        """Template should contain JS / HTML for rendering mitigation strategies."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert "renderMitigation" in body or "mitigation-card" in body

    def test_revision_risk_adu_in_permit_options(self, client):
        """ADU should be an option in the permit type dropdown."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'value="adu"' in body

    def test_revision_risk_restaurant_in_permit_options(self, client):
        """Restaurant should be an option in the permit type dropdown."""
        resp = client.get("/tools/revision-risk")
        body = resp.data.decode("utf-8")
        assert 'value="restaurant"' in body
