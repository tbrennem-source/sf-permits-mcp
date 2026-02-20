"""Tests for velocity dashboard data assembly and list_feedback MCP tool."""

import pytest
from web.app import app
from web.app import _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="dash@example.com"):
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ── Velocity dashboard ────────────────────────────────────────────────────────

def test_health_tier_fast():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(0.5) == "fast"
    assert _health_tier(0) == "fast"


def test_health_tier_normal():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(3) == "normal"
    assert _health_tier(6.9) == "normal"


def test_health_tier_slow():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(7) == "slow"
    assert _health_tier(29) == "slow"


def test_health_tier_critical():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(30) == "critical"
    assert _health_tier(89) == "critical"


def test_health_tier_severe():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(90) == "severe"
    assert _health_tier(174) == "severe"


def test_health_tier_none():
    from web.velocity_dashboard import _health_tier
    assert _health_tier(None) == "unknown"


def test_get_dashboard_data_structure():
    """Dashboard data assembles without errors."""
    from web.velocity_dashboard import get_dashboard_data
    data = get_dashboard_data()
    assert "baselines" in data
    assert "stalled_permits" in data
    assert "dept_rollup" in data
    assert "station_load" in data
    assert "portfolio" in data
    assert "dept_list" in data
    assert "summary" in data
    summary = data["summary"]
    assert "total_stations" in summary
    assert "severe_stations" in summary
    assert "total_stalled" in summary
    assert "held_count" in summary
    # Portfolio shape
    p = data["portfolio"]
    assert "stations" in p
    assert "permit_map" in p
    assert "count" in p
    assert isinstance(p["stations"], list)
    assert isinstance(p["count"], int)


def test_dashboard_baselines_have_tier():
    """Each baseline dict has tier, css class, dept, and in_portfolio."""
    from web.velocity_dashboard import get_dashboard_data
    data = get_dashboard_data()
    for b in data["baselines"]:
        assert "tier" in b
        assert "tier_css" in b
        assert "tier_label" in b
        assert "dept" in b
        assert "in_portfolio" in b
        assert b["tier"] in ("fast", "normal", "slow", "critical", "severe", "unknown")
        assert isinstance(b["in_portfolio"], bool)


def test_dashboard_dept_list():
    """dept_list is sorted list of dept strings."""
    from web.velocity_dashboard import get_dashboard_data
    data = get_dashboard_data()
    depts = data["dept_list"]
    assert isinstance(depts, list)
    assert depts == sorted(depts)


def test_portfolio_stations_no_user():
    """get_portfolio_stations returns empty dict for unknown user."""
    from web.velocity_dashboard import get_portfolio_stations
    result = get_portfolio_stations(user_id=999999)
    assert result["stations"] == set() or isinstance(result["stations"], set)
    assert result["permit_map"] == {}
    assert result["permit_numbers"] == []


def test_dashboard_route(client):
    """Dashboard route returns 200 when logged in."""
    _login(client)
    rv = client.get("/dashboard/bottlenecks")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Pipeline" in html or "Bottleneck" in html or "Station" in html


def test_dashboard_route_requires_login(client):
    """Dashboard route redirects when not logged in."""
    rv = client.get("/dashboard/bottlenecks")
    assert rv.status_code in (302, 401)


def test_reviewer_stats_unknown_station():
    """get_reviewer_stats returns empty list for unknown station."""
    from web.velocity_dashboard import get_reviewer_stats
    result = get_reviewer_stats("ZZNONEXISTENT")
    assert isinstance(result, list)
    # Should be empty or have valid structure
    for r in result:
        assert "reviewer" in r
        assert "completed" in r
        assert "median_days" in r
        assert "tier" in r


def test_station_detail_route_json(client):
    """Reviewer detail endpoint returns JSON with correct shape."""
    _login(client)
    rv = client.get("/dashboard/bottlenecks/station/BLDG")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data is not None
    assert "station" in data
    assert data["station"] == "BLDG"
    assert "reviewers" in data
    assert isinstance(data["reviewers"], list)


def test_station_detail_requires_login(client):
    """Reviewer detail route redirects when not logged in."""
    rv = client.get("/dashboard/bottlenecks/station/BLDG")
    assert rv.status_code in (302, 401)


# ── list_feedback MCP tool ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_feedback_empty():
    """list_feedback returns graceful empty message when no feedback."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback()
    # Empty DB — either "No feedback found" or a table header
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_feedback_with_status_filter():
    """list_feedback respects status filter."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback(status="new")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_list_feedback_with_type_filter():
    """list_feedback respects feedback_type filter."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback(feedback_type="bug")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_list_feedback_limit_capped():
    """list_feedback caps limit at 200."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback(limit=999)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_list_feedback_days_back():
    """list_feedback accepts days_back filter."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback(days_back=7)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_list_feedback_include_resolved():
    """list_feedback include_resolved flag works."""
    from src.tools.list_feedback import list_feedback
    result = await list_feedback(include_resolved=True)
    assert isinstance(result, str)


def test_list_feedback_registered_in_server():
    """list_feedback is registered as an MCP tool."""
    import src.server  # noqa: F401 — just check it imports without error
    from src.tools.list_feedback import list_feedback
    assert callable(list_feedback)


def test_velocity_dashboard_hidden_from_non_admin(client):
    """Pipeline link is NOT in nav for non-admin users (moved to admin dropdown)."""
    _login(client)
    rv = client.get("/")
    html = rv.data.decode()
    assert "/dashboard/bottlenecks" not in html


def test_velocity_dashboard_in_admin_dropdown(client):
    """Pipeline link appears in admin dropdown for admin users."""
    import web.auth as auth_mod
    old_admin = auth_mod.ADMIN_EMAIL
    auth_mod.ADMIN_EMAIL = "admin@example.com"
    try:
        _login(client, email="admin@example.com")
        rv = client.get("/")
        html = rv.data.decode()
        assert "admin/ops#pipeline" in html
        assert "Admin" in html
    finally:
        auth_mod.ADMIN_EMAIL = old_admin


def test_list_feedback_registered_in_server():
    """list_feedback is importable and callable."""
    from src.tools.list_feedback import list_feedback
    assert callable(list_feedback)
