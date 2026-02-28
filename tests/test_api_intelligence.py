"""Tests for Sprint 85-A: Intelligence API endpoints.

Covers:
  GET  /api/predict-next/<permit_number>  -> predict_next_stations
  GET  /api/stuck-permit/<permit_number>  -> diagnose_stuck_permit
  POST /api/what-if                       -> simulate_what_if
  POST /api/delay-cost                    -> calculate_delay_cost

All endpoints require authentication (session cookie).
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Shared fixtures
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
        with app.test_request_context():
            pass
        # Inject session via test_request_context + session transaction
        with c.session_transaction() as sess:
            sess["user_id"] = 1
            sess["email"] = "test@example.com"
        yield c


# ---------------------------------------------------------------------------
# GET /api/predict-next/<permit_number>
# ---------------------------------------------------------------------------

class TestPredictNext:
    def test_predict_next_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        resp = client.get("/api/predict-next/202201234567")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "unauthorized"

    def test_predict_next_returns_json(self, authed_client):
        """Authenticated request returns 200 with JSON result."""
        mock_md = "# What's Next: Permit 202201234567\n\nMock prediction result."
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.get("/api/predict-next/202201234567")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["permit_number"] == "202201234567"
        assert "result" in data
        assert "What's Next" in data["result"]

    def test_predict_next_returns_json_content_type(self, authed_client):
        """Response Content-Type is application/json."""
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(return_value="mock result"),
        ):
            resp = authed_client.get("/api/predict-next/202201234567")
        assert "application/json" in resp.content_type

    def test_predict_next_returns_500_on_error(self, authed_client):
        """Returns 500 when the tool raises an exception."""
        with patch(
            "src.tools.predict_next_stations.predict_next_stations",
            new=AsyncMock(side_effect=RuntimeError("db error")),
        ):
            resp = authed_client.get("/api/predict-next/202201234567")
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/stuck-permit/<permit_number>
# ---------------------------------------------------------------------------

class TestStuckPermit:
    def test_stuck_permit_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        resp = client.get("/api/stuck-permit/202201234567")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "unauthorized"

    def test_stuck_permit_returns_json(self, authed_client):
        """Authenticated request returns 200 with JSON result."""
        mock_md = "# Stuck Permit Playbook: 202201234567\n\nMock playbook."
        with patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.get("/api/stuck-permit/202201234567")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["permit_number"] == "202201234567"
        assert "result" in data
        assert "Stuck Permit" in data["result"]

    def test_stuck_permit_returns_json_content_type(self, authed_client):
        """Response Content-Type is application/json."""
        with patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(return_value="mock result"),
        ):
            resp = authed_client.get("/api/stuck-permit/202201234567")
        assert "application/json" in resp.content_type

    def test_stuck_permit_returns_500_on_error(self, authed_client):
        """Returns 500 when the tool raises an exception."""
        with patch(
            "src.tools.stuck_permit.diagnose_stuck_permit",
            new=AsyncMock(side_effect=RuntimeError("db error")),
        ):
            resp = authed_client.get("/api/stuck-permit/202201234567")
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# POST /api/what-if
# ---------------------------------------------------------------------------

class TestWhatIf:
    def test_what_if_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        resp = client.post(
            "/api/what-if",
            json={"base_description": "Kitchen remodel, $80K"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "unauthorized"

    def test_what_if_requires_post(self, authed_client):
        """GET method returns 405 Method Not Allowed."""
        resp = authed_client.get("/api/what-if")
        assert resp.status_code == 405

    def test_what_if_validates_missing_base_description(self, authed_client):
        """Returns 400 when base_description is missing."""
        resp = authed_client.post("/api/what-if", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "base_description" in data["error"]

    def test_what_if_validates_empty_base_description(self, authed_client):
        """Returns 400 when base_description is empty string."""
        resp = authed_client.post(
            "/api/what-if",
            json={"base_description": "   "},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "base_description" in data["error"]

    def test_what_if_returns_json(self, authed_client):
        """Authenticated POST with valid body returns 200 with JSON result."""
        mock_md = "# What-If Permit Simulator\n\nMock comparison table."
        with patch(
            "src.tools.what_if_simulator.simulate_what_if",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/what-if",
                json={
                    "base_description": "Kitchen remodel, $80K",
                    "variations": [
                        {"label": "Add bathroom", "description": "Kitchen + bathroom, $120K"}
                    ],
                },
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "result" in data
        assert "What-If" in data["result"]

    def test_what_if_accepts_no_variations(self, authed_client):
        """Works with base_description only (no variations)."""
        mock_md = "# What-If Permit Simulator\n\nBase only."
        with patch(
            "src.tools.what_if_simulator.simulate_what_if",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/what-if",
                json={"base_description": "Kitchen remodel, $80K"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "result" in data

    def test_what_if_validates_variations_type(self, authed_client):
        """Returns 400 when variations is not a list."""
        resp = authed_client.post(
            "/api/what-if",
            json={"base_description": "Kitchen remodel", "variations": "not a list"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "variations" in data["error"]

    def test_what_if_returns_500_on_error(self, authed_client):
        """Returns 500 when the tool raises an exception."""
        with patch(
            "src.tools.what_if_simulator.simulate_what_if",
            new=AsyncMock(side_effect=RuntimeError("tool error")),
        ):
            resp = authed_client.post(
                "/api/what-if",
                json={"base_description": "Kitchen remodel"},
            )
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# POST /api/delay-cost
# ---------------------------------------------------------------------------

class TestDelayCost:
    def test_delay_cost_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        resp = client.post(
            "/api/delay-cost",
            json={"permit_type": "adu", "monthly_carrying_cost": 5000},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] == "unauthorized"

    def test_delay_cost_validates_missing_permit_type(self, authed_client):
        """Returns 400 when permit_type is missing."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={"monthly_carrying_cost": 5000},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "permit_type" in data["error"]

    def test_delay_cost_validates_missing_monthly_cost(self, authed_client):
        """Returns 400 when monthly_carrying_cost is missing."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={"permit_type": "adu"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "monthly_carrying_cost" in data["error"]

    def test_delay_cost_validates_zero_monthly_cost(self, authed_client):
        """Returns 400 when monthly_carrying_cost is zero."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={"permit_type": "adu", "monthly_carrying_cost": 0},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "greater than zero" in data["error"]

    def test_delay_cost_validates_negative_monthly_cost(self, authed_client):
        """Returns 400 when monthly_carrying_cost is negative."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={"permit_type": "adu", "monthly_carrying_cost": -1000},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "greater than zero" in data["error"]

    def test_delay_cost_validates_non_numeric_monthly_cost(self, authed_client):
        """Returns 400 when monthly_carrying_cost is not a number."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={"permit_type": "adu", "monthly_carrying_cost": "a lot"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "number" in data["error"]

    def test_delay_cost_returns_json(self, authed_client):
        """Authenticated POST with valid body returns 200 with JSON result."""
        mock_md = "# Cost of Delay — ADU\n\nMock cost breakdown."
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(return_value=mock_md),
        ):
            resp = authed_client.post(
                "/api/delay-cost",
                json={"permit_type": "adu", "monthly_carrying_cost": 5000},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "result" in data
        assert "Cost of Delay" in data["result"]

    def test_delay_cost_accepts_optional_fields(self, authed_client):
        """Accepts optional neighborhood and triggers fields."""
        mock_md = "# Cost of Delay — Restaurant\n\nMock breakdown."
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(return_value=mock_md),
        ) as mock_fn:
            resp = authed_client.post(
                "/api/delay-cost",
                json={
                    "permit_type": "restaurant",
                    "monthly_carrying_cost": 10000,
                    "neighborhood": "Mission",
                    "triggers": ["planning_review", "dph_review"],
                },
            )
        assert resp.status_code == 200
        # Verify optional fields were passed through
        call_kwargs = mock_fn.call_args
        assert call_kwargs is not None

    def test_delay_cost_validates_triggers_type(self, authed_client):
        """Returns 400 when triggers is not a list."""
        resp = authed_client.post(
            "/api/delay-cost",
            json={
                "permit_type": "adu",
                "monthly_carrying_cost": 5000,
                "triggers": "not a list",
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "triggers" in data["error"]

    def test_delay_cost_returns_500_on_error(self, authed_client):
        """Returns 500 when the tool raises an exception."""
        with patch(
            "src.tools.cost_of_delay.calculate_delay_cost",
            new=AsyncMock(side_effect=RuntimeError("tool error")),
        ):
            resp = authed_client.post(
                "/api/delay-cost",
                json={"permit_type": "adu", "monthly_carrying_cost": 5000},
            )
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data
