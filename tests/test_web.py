"""Tests for the sfpermits.ai web UI."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, md_to_html


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_loads(client):
    """Homepage renders with form and preset chips."""
    rv = client.get("/")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "sfpermits.ai" in html
    assert "Analyze Project" in html
    assert "Kitchen Remodel" in html  # preset chip


def test_index_has_neighborhoods(client):
    """Neighborhood dropdown is populated."""
    rv = client.get("/")
    html = rv.data.decode()
    assert "Noe Valley" in html
    assert "Mission" in html
    assert "Pacific Heights" in html


def test_analyze_empty_description(client):
    """POST with empty description returns 400."""
    rv = client.post("/analyze", data={"description": ""})
    assert rv.status_code == 400
    assert b"Please enter a project description" in rv.data


def test_analyze_basic(client):
    """POST with minimal input returns 5 result panels."""
    rv = client.post("/analyze", data={
        "description": "Kitchen remodel removing wall",
        "cost": "85000",
        "neighborhood": "Noe Valley",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    # All 5 tab panels present
    assert 'id="panel-predict"' in html
    assert 'id="panel-fees"' in html
    assert 'id="panel-timeline"' in html
    assert 'id="panel-docs"' in html
    assert 'id="panel-risk"' in html


def test_analyze_no_cost(client):
    """POST without cost still runs predict/timeline/docs/risk but fees shows info message."""
    rv = client.post("/analyze", data={
        "description": "Small bathroom refresh",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert 'id="panel-predict"' in html
    assert "Enter an estimated cost" in html  # fees info message


def test_analyze_restaurant(client):
    """Restaurant project triggers DPH/fire routing."""
    rv = client.post("/analyze", data={
        "description": "Convert retail to restaurant with Type I hood, grease interceptor, 49 seats",
        "cost": "250000",
        "neighborhood": "Mission",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "restaurant" in html.lower() or "food" in html.lower()


def test_analyze_adu(client):
    """ADU project gets proper routing."""
    rv = client.post("/analyze", data={
        "description": "Convert garage to ADU with kitchenette and bathroom, 450 sq ft",
        "cost": "180000",
        "sqft": "450",
        "neighborhood": "Sunset/Parkside",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "adu" in html.lower() or "accessory" in html.lower()


def test_md_to_html_basic():
    """md_to_html converts markdown tables and bold."""
    result = md_to_html("**bold text**\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    assert "<strong>" in result
    assert "<table>" in result


def test_md_to_html_links():
    """md_to_html preserves links."""
    result = md_to_html("[sf.gov](https://sf.gov)")
    assert 'href="https://sf.gov"' in result
