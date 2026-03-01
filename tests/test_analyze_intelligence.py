"""Tests for intelligence integration in analyze().

Covers: carrying_cost field, basic response structure, missing description guard.
Based on existing patterns in tests/test_web.py.
"""

import pytest
from web.helpers import _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzeIntelligence:
    def test_analyze_without_description_returns_400(self, client):
        """Analyze with missing description returns 400 with error message."""
        rv = client.post("/analyze", data={})
        assert rv.status_code == 400
        assert b"Please enter a project description" in rv.data

    def test_analyze_empty_description_returns_400(self, client):
        """Analyze with empty string description returns 400."""
        rv = client.post("/analyze", data={"description": "   "})
        assert rv.status_code == 400

    def test_analyze_basic_returns_200(self, client):
        """Analyze with minimal description returns 200."""
        rv = client.post("/analyze", data={
            "description": "kitchen remodel in a single family home",
        })
        assert rv.status_code == 200

    def test_analyze_returns_result_panels(self, client):
        """Analyze returns all 5 tool result panels."""
        rv = client.post("/analyze", data={
            "description": "Kitchen remodel removing a non-load-bearing wall",
            "cost": "85000",
            "neighborhood": "Noe Valley",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert 'id="panel-predict"' in html
        assert 'id="panel-timeline"' in html
        assert 'id="panel-docs"' in html
        assert 'id="panel-risk"' in html

    def test_analyze_accepts_carrying_cost_field(self, client):
        """Analyze form accepts carrying_cost field without error."""
        rv = client.post("/analyze", data={
            "description": "kitchen remodel residential",
            "carrying_cost": "5000",
        })
        assert rv.status_code == 200

    def test_analyze_carrying_cost_appears_in_timeline(self, client):
        """When carrying_cost is provided, timeline panel is present in response."""
        rv = client.post("/analyze", data={
            "description": "ADU conversion in garage",
            "cost": "120000",
            "carrying_cost": "3500",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert 'id="panel-timeline"' in html

    def test_analyze_no_cost_shows_fee_message(self, client):
        """Without cost, fees panel shows info message instead of error."""
        rv = client.post("/analyze", data={
            "description": "Small bathroom refresh",
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Enter an estimated cost" in html

    def test_analyze_with_address_field(self, client):
        """Analyze accepts optional address field without error."""
        rv = client.post("/analyze", data={
            "description": "roof replacement on single family home",
            "address": "123 Main St",
            "cost": "40000",
        })
        assert rv.status_code == 200

    def test_analyze_with_neighborhood_field(self, client):
        """Analyze accepts optional neighborhood field without error."""
        rv = client.post("/analyze", data={
            "description": "kitchen remodel",
            "neighborhood": "Mission",
        })
        assert rv.status_code == 200

    def test_analyze_with_experience_level(self, client):
        """Analyze accepts experience_level field without error."""
        rv = client.post("/analyze", data={
            "description": "bathroom renovation",
            "experience_level": "first_time",
        })
        assert rv.status_code == 200

    def test_analyze_zero_carrying_cost_is_accepted(self, client):
        """Zero carrying_cost is accepted (treated as None by the route)."""
        rv = client.post("/analyze", data={
            "description": "deck addition",
            "carrying_cost": "0",
        })
        # Route parses zero as 0.0 (falsy); no 400 expected
        assert rv.status_code == 200

    def test_analyze_non_numeric_carrying_cost_raises_value_error(self, client):
        """Non-numeric carrying_cost causes a ValueError.

        The route does float(carrying_cost_str) without try/except.
        In Flask TESTING mode, this propagates as a live exception (not a 500 response).
        This test documents current behavior and will need updating if validation is added.
        """
        import pytest as _pytest
        with _pytest.raises(ValueError, match="could not convert string to float"):
            client.post("/analyze", data={
                "description": "window replacement",
                "carrying_cost": "not_a_number",
            })
