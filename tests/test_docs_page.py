"""Tests for /docs API documentation page and docs_generator module."""

import pytest

from web.app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# docs_generator unit tests
# ---------------------------------------------------------------------------

def test_get_tool_catalog_structure():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    assert "categories" in catalog
    assert "total_tools" in catalog
    assert "total_categories" in catalog
    assert isinstance(catalog["categories"], list)


def test_get_tool_catalog_has_seven_categories():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    assert catalog["total_categories"] == 7, (
        f"Expected 7 categories, got {catalog['total_categories']}"
    )


def test_get_tool_catalog_has_expected_category_names():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    names = {cat["name"] for cat in catalog["categories"]}
    expected = {
        "Search & Lookup",
        "Analytics",
        "Intelligence",
        "Advanced",
        "Plan Analysis",
        "Network",
        "System",
    }
    assert names == expected, f"Category names mismatch: {names}"


def test_get_tool_catalog_has_at_least_30_tools():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    assert catalog["total_tools"] >= 30, (
        f"Expected at least 30 tools, got {catalog['total_tools']}"
    )


def test_get_tool_catalog_tool_structure():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    for cat in catalog["categories"]:
        for tool in cat["tools"]:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "parameters" in tool, f"Tool missing 'parameters': {tool}"
            assert isinstance(tool["parameters"], list)


def test_get_tool_catalog_parameter_structure():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    for cat in catalog["categories"]:
        for tool in cat["tools"]:
            for param in tool["parameters"]:
                assert "name" in param, f"Param missing 'name' in {tool['name']}"
                assert "type" in param, f"Param missing 'type' in {tool['name']}"
                assert "required" in param, f"Param missing 'required' in {tool['name']}"
                assert "description" in param, f"Param missing 'description' in {tool['name']}"


def test_get_tool_catalog_all_34_tools():
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    assert catalog["total_tools"] == 34, (
        f"Expected exactly 34 tools, got {catalog['total_tools']}"
    )


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_docs_returns_200(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_docs_contains_all_category_names(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    # Decode and unescape HTML entities for comparison
    import html as html_module
    html_text = html_module.unescape(resp.data.decode())
    for name in ["Search & Lookup", "Analytics", "Intelligence", "Advanced",
                 "Plan Analysis", "Network", "System"]:
        assert name in html_text, f"Category '{name}' not found in /docs"


def test_docs_lists_at_least_30_tools(client):
    from web.docs_generator import get_tool_catalog
    resp = client.get("/docs")
    assert resp.status_code == 200
    html = resp.data.decode()
    catalog = get_tool_catalog()
    # Check at least 30 tool names appear in the HTML
    found = sum(1 for cat in catalog["categories"]
                for tool in cat["tools"]
                if tool["name"] in html)
    assert found >= 30, f"Only {found} tool names found in /docs HTML"


def test_docs_no_auth_required(client):
    """Docs page is public — no login needed."""
    resp = client.get("/docs")
    # Should not redirect to login
    assert resp.status_code == 200
    assert b"login" not in resp.data.lower() or b"API Documentation" in resp.data
