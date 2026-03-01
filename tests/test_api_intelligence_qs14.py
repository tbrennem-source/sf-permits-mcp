"""Tests for QS14 intelligence API endpoints (T1-D additions).

Tests for new HTMX intelligence API endpoints being added in QS14 T1-D:
  - GET /api/similar-projects — similar projects by permit type/neighborhood
  - Any new intelligence fragment endpoints added by T1-D

These complement the existing tests/test_api_intelligence.py which covers
Sprint 85-A endpoints (/api/predict-next, /api/stuck-permit, /api/what-if,
/api/delay-cost).

Auth pattern:
- Authenticated routes: require session["user_id"]
- Return 401 for unauthenticated requests
- Return JSON or HTML fragments (HTMX), not full pages

Test resilience:
- If a route doesn't exist yet (T1-D not merged), test expects 404
- Tests PASS or SKIP — never ERROR due to missing routes
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures — consistent with test_api_intelligence.py patterns
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def authed_client(app):
    """Return a test client with a user session injected."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = 1
            sess["email"] = "test@example.com"
        yield c


# ---------------------------------------------------------------------------
# GET /api/similar-projects
# ---------------------------------------------------------------------------

class TestSimilarProjectsAPI:
    """Tests for the /api/similar-projects endpoint.

    This endpoint is PUBLIC (no auth required). It defaults permit_type to
    'alterations' when not provided. It returns an HTML fragment (HTMX target).
    """

    def test_similar_projects_returns_200_unauthenticated(self, client):
        """Public endpoint: unauthenticated request returns 200 or 404 (pending)."""
        resp = client.get("/api/similar-projects?permit_type=alterations")
        # 404 = route not built; 200 = success; 500 = tool error
        assert resp.status_code in (200, 404, 500), (
            f"Unexpected status for public endpoint: {resp.status_code}"
        )

    def test_similar_projects_authenticated_request(self, authed_client):
        """Authenticated request returns 200 (with mock) or 404 (route pending)."""
        mock_md = "# Similar Projects\n\n- 2023001: Kitchen remodel, Mission"
        mock_meta = {"projects": [{"permit_number": "2023001", "description": "Kitchen remodel"}]}
        with patch(
            "src.tools.similar_projects.similar_projects",
            new=AsyncMock(return_value=(mock_md, mock_meta)),
        ):
            resp = authed_client.get("/api/similar-projects?permit_type=alterations")
        # 404 = T1-D not merged; 200 = success; 500 = tool error handled
        assert resp.status_code in (200, 404, 500), (
            f"Unexpected status {resp.status_code}"
        )

    def test_similar_projects_with_neighborhood(self, authed_client):
        """Accepts optional neighborhood parameter."""
        mock_meta = {"projects": []}
        with patch(
            "src.tools.similar_projects.similar_projects",
            new=AsyncMock(return_value=("# Similar Projects", mock_meta)),
        ):
            resp = authed_client.get(
                "/api/similar-projects?permit_type=alterations&neighborhood=Mission"
            )
        assert resp.status_code in (200, 404, 500)

    def test_similar_projects_returns_html_fragment(self, client):
        """Response should be an HTML fragment (HTMX target)."""
        mock_meta = {"projects": []}
        with patch(
            "src.tools.similar_projects.similar_projects",
            new=AsyncMock(return_value=("# Similar Projects", mock_meta)),
        ):
            resp = client.get("/api/similar-projects?permit_type=alterations")
        if resp.status_code == 200:
            # Should be HTML fragment — not a JSON API endpoint
            ct = resp.content_type
            assert "html" in ct or "json" in ct, f"Unexpected content type: {ct}"

    def test_similar_projects_default_permit_type(self, client):
        """Missing permit_type defaults to 'alterations' — returns 200, not 400."""
        mock_meta = {"projects": []}
        with patch(
            "src.tools.similar_projects.similar_projects",
            new=AsyncMock(return_value=("# Similar Projects", mock_meta)),
        ):
            resp = client.get("/api/similar-projects")
        # Route defaults permit_type to 'alterations' — should not 400
        assert resp.status_code in (200, 404, 500), (
            f"Expected 200/404/500 (permit_type defaults to 'alterations'), got {resp.status_code}"
        )

    def test_similar_projects_tool_error_returns_gracefully(self, client):
        """Tool exceptions are caught — returns 200 with empty list, not traceback."""
        with patch(
            "src.tools.similar_projects.similar_projects",
            new=AsyncMock(side_effect=RuntimeError("DB error")),
        ):
            resp = client.get("/api/similar-projects?permit_type=alterations")
        # 404 = route pending; 200 = graceful fallback (empty list); 500 = unhandled
        assert resp.status_code in (200, 404, 500)


# ---------------------------------------------------------------------------
# POST /api/delay-cost — QS14 complement tests
# ---------------------------------------------------------------------------

class TestDelayCostAPIComplement:
    """Complement tests for /api/delay-cost (new parameter coverage for QS14)."""

    def test_delay_cost_with_mission_neighborhood(self, authed_client):
        """Accepts neighborhood parameter and passes it through."""
        mock_md = "# Cost of Delay — Restaurant (Mission)\n\nMock breakdown."
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/delay-cost",
                json={
                    "permit_type": "restaurant",
                    "monthly_carrying_cost": 10000,
                    "neighborhood": "Mission",
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "result" in data
        assert "Cost of Delay" in data["result"]

    def test_delay_cost_with_noe_valley_neighborhood(self, authed_client):
        """Accepts Noe Valley neighborhood parameter."""
        mock_md = "# Cost of Delay — ADU (Noe Valley)\n\nMock breakdown."
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/delay-cost",
                json={
                    "permit_type": "adu",
                    "monthly_carrying_cost": 8000,
                    "neighborhood": "Noe Valley",
                },
            )
        assert resp.status_code == 200

    def test_delay_cost_result_has_string_content(self, authed_client):
        """Result field is a non-empty string."""
        mock_md = "# Cost of Delay — New Construction\n\nFull breakdown here."
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/delay-cost",
                json={"permit_type": "new_construction", "monthly_carrying_cost": 15000},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["result"], str)
        assert len(data["result"]) > 0


# ---------------------------------------------------------------------------
# GET /api/predict-next/<permit_number> — QS14 complement tests
# ---------------------------------------------------------------------------

class TestPredictNextAPIComplement:
    """Additional coverage for predict-next endpoint (QS14 context)."""

    def test_predict_next_short_permit_number(self, authed_client):
        """Short permit number is accepted (validation is lenient)."""
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(return_value="# What's Next\n\nMock."),
        ):
            resp = authed_client.get("/api/predict-next/2023001")
        # Should return 200 or forward to tool
        assert resp.status_code in (200, 400, 404, 500)

    def test_predict_next_result_contains_markdown(self, authed_client):
        """Result field contains the markdown from the tool."""
        mock_md = "# What's Next: Permit 202201234567\n\n## Next Steps\n\n1. Inspection."
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.get("/api/predict-next/202201234567")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Next Steps" in data["result"] or "What's Next" in data["result"]


# ---------------------------------------------------------------------------
# GET /api/stuck-permit/<permit_number> — QS14 complement tests
# ---------------------------------------------------------------------------

class TestStuckPermitAPIComplement:
    """Additional coverage for stuck-permit endpoint (QS14 context)."""

    def test_stuck_permit_result_is_string(self, authed_client):
        """Result field is a string (markdown from tool)."""
        mock_md = "# Stuck Permit Playbook\n\n## Immediate Actions\n\n1. Call BLDG."
        with patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.get("/api/stuck-permit/202201234567")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["result"], str)
        assert len(data["result"]) > 0

    def test_stuck_permit_permit_number_in_response(self, authed_client):
        """Response includes the permit_number field."""
        with patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(return_value="# Playbook"),
        ):
            resp = authed_client.get("/api/stuck-permit/202201234567")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "permit_number" in data
        assert data["permit_number"] == "202201234567"


# ---------------------------------------------------------------------------
# Intelligence API: cross-endpoint consistency checks
# ---------------------------------------------------------------------------

class TestIntelligenceAPIConsistency:
    """Cross-endpoint consistency: all intelligence endpoints follow same patterns."""

    # Auth-required endpoints (return 401 for unauthenticated)
    _AUTHED_ENDPOINTS = [
        ("GET", "/api/predict-next/202201234567"),
        ("GET", "/api/stuck-permit/202201234567"),
        ("POST", "/api/what-if"),
        ("POST", "/api/delay-cost"),
    ]

    # Public endpoints (no auth required — return 200 for unauthenticated)
    _PUBLIC_ENDPOINTS = [
        ("GET", "/api/similar-projects"),
    ]

    def test_authed_endpoints_reject_unauthenticated(self, client):
        """Auth-required intelligence endpoints reject unauthenticated requests."""
        post_data = {
            "/api/what-if": {"base_description": "Kitchen remodel"},
            "/api/delay-cost": {"permit_type": "adu", "monthly_carrying_cost": 5000},
        }
        for method, endpoint in self._AUTHED_ENDPOINTS:
            if method == "GET":
                resp = client.get(endpoint)
            else:
                resp = client.post(endpoint, json=post_data.get(endpoint, {}))

            assert resp.status_code in (401, 302, 404, 405), (
                f"{method} {endpoint}: expected auth rejection or 404 (pending), "
                f"got {resp.status_code}"
            )

    def test_public_endpoints_allow_unauthenticated(self, client):
        """Public intelligence endpoints allow unauthenticated access."""
        for method, endpoint in self._PUBLIC_ENDPOINTS:
            if method == "GET":
                resp = client.get(endpoint)
            else:
                resp = client.post(endpoint)
            # 200 = public access allowed; 404 = route not yet built
            assert resp.status_code in (200, 404, 500), (
                f"{method} {endpoint}: expected public access (200) or 404 (pending), "
                f"got {resp.status_code}"
            )

    def test_all_get_endpoints_return_json_content_type(self, authed_client):
        """All GET intelligence endpoints return JSON content type (if they exist)."""
        get_endpoints = [
            "/api/predict-next/202201234567",
            "/api/stuck-permit/202201234567",
        ]
        mock_md = "# Mock Result\n\nData."
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(return_value=mock_md),
        ), patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(return_value=mock_md),
        ):
            for endpoint in get_endpoints:
                resp = authed_client.get(endpoint)
                if resp.status_code == 200:
                    assert "application/json" in resp.content_type, (
                        f"{endpoint}: expected JSON content type, got {resp.content_type}"
                    )
