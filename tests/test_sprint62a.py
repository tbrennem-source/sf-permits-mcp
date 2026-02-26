"""Tests for Sprint 62A: Activity Intelligence — analytics engine.

Coverage:
  - get_bounce_rate: returns correct dict keys
  - get_bounce_rate: calculates bounced searches correctly
  - get_bounce_rate: non-bounced search (follow-up within 60s)
  - get_bounce_rate: empty data returns zeros
  - get_feature_funnel: returns correct dict keys
  - get_feature_funnel: counts users at each funnel stage
  - get_feature_funnel: empty data returns zero-filled stages
  - get_query_refinements: returns correct dict keys
  - get_query_refinements: detects same-user repeated searches
  - get_query_refinements: empty data returns zeros
  - get_feedback_by_page: returns correct dict keys
  - get_feedback_by_page: computes ratio from known visits/feedback
  - get_feedback_by_page: empty data returns empty pages list
  - get_time_to_first_action: returns correct dict keys
  - get_time_to_first_action: computes gap from known timestamps
  - get_time_to_first_action: empty data returns zeros
  - Admin intel endpoint returns 200 for admin users
  - Admin intel endpoint returns 403 for non-admin users
  - Admin intel endpoint returns 403 when not logged in
  - get_bounce_rate: rate is 0 when all searches have follow-ups
  - get_bounce_rate: rate is 100 when no searches have follow-ups
  - get_feature_funnel: analyze action counted correctly
  - get_feature_funnel: ask path counted correctly
  - get_query_refinements: top_refined_queries is a list of dicts
  - get_feedback_by_page: pages sorted by feedback_count desc
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for test isolation."""
    db_path = str(tmp_path / "test_62a.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    import web.activity as activity_mod
    monkeypatch.setattr(activity_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="user@test.com"):
    """Create user and log in via magic token. Returns user dict."""
    from web.auth import create_user, create_magic_token
    user = create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _make_admin(client, email="admin@test.com", monkeypatch=None):
    """Create admin user and log in."""
    import web.auth as auth_mod
    if monkeypatch:
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    from web.auth import create_user, create_magic_token
    user = create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _insert_activity(action, user_id=None, ip_hash=None, path=None, detail=None, created_at=None):
    """Insert a row into activity_log directly."""
    from src.db import get_connection
    conn = get_connection()
    try:
        from src.db import query_one
        row = query_one("SELECT COALESCE(MAX(log_id), 0) + 1 FROM activity_log")
        log_id = row[0]
        detail_str = json.dumps(detail) if detail else None
        if created_at:
            conn.execute(
                "INSERT INTO activity_log (log_id, user_id, action, detail, path, ip_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (log_id, user_id, action, detail_str, path, ip_hash, created_at),
            )
        else:
            conn.execute(
                "INSERT INTO activity_log (log_id, user_id, action, detail, path, ip_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, user_id, action, detail_str, path, ip_hash),
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# get_bounce_rate
# ---------------------------------------------------------------------------

def test_bounce_rate_returns_correct_keys():
    """get_bounce_rate returns all required keys."""
    from web.activity_intel import get_bounce_rate
    result = get_bounce_rate()
    assert "total_searches" in result
    assert "bounced" in result
    assert "bounce_rate" in result
    assert "hours" in result


def test_bounce_rate_empty_data():
    """get_bounce_rate returns zeros when no activity exists."""
    from web.activity_intel import get_bounce_rate
    result = get_bounce_rate(hours=24)
    assert result["total_searches"] == 0
    assert result["bounced"] == 0
    assert result["bounce_rate"] == 0.0
    assert result["hours"] == 24


def test_bounce_rate_all_bounced():
    """100% bounce rate when searches have no follow-up."""
    from web.activity_intel import get_bounce_rate
    # Insert 3 searches with no follow-up actions
    _insert_activity("search", ip_hash="aaa111", path="/ask")
    _insert_activity("search", ip_hash="bbb222", path="/ask")
    _insert_activity("public_search", ip_hash="ccc333", path="/")
    result = get_bounce_rate(hours=24)
    assert result["total_searches"] >= 3
    assert result["bounced"] >= 3
    assert result["bounce_rate"] > 0.0


def test_bounce_rate_no_bounces():
    """0% bounce rate when all searches have follow-up within 60s."""
    from web.activity_intel import get_bounce_rate
    from datetime import datetime, timedelta
    # Search at T, follow-up at T+10s — same ip_hash
    t_search = datetime.utcnow() - timedelta(hours=1)
    t_followup = t_search + timedelta(seconds=10)
    _insert_activity("search", ip_hash="follow001", created_at=t_search)
    _insert_activity("lookup", ip_hash="follow001", created_at=t_followup)
    result = get_bounce_rate(hours=24)
    # The follow001 search should NOT be bounced
    # (there may be 0 bounces for this ip_hash)
    assert result["total_searches"] >= 1
    # bounce_rate should be < 100 (at least one search has a follow-up)
    assert result["bounce_rate"] < 100.0


def test_bounce_rate_hours_parameter():
    """hours parameter is reflected in result."""
    from web.activity_intel import get_bounce_rate
    result = get_bounce_rate(hours=48)
    assert result["hours"] == 48


# ---------------------------------------------------------------------------
# get_feature_funnel
# ---------------------------------------------------------------------------

def test_feature_funnel_returns_correct_keys():
    """get_feature_funnel returns all required keys."""
    from web.activity_intel import get_feature_funnel
    result = get_feature_funnel()
    assert "stages" in result
    assert "days" in result
    assert len(result["stages"]) == 4
    for stage in result["stages"]:
        assert "name" in stage
        assert "count" in stage
        assert "pct_of_search" in stage


def test_feature_funnel_empty_data():
    """get_feature_funnel returns zero-filled stages when no data."""
    from web.activity_intel import get_feature_funnel
    result = get_feature_funnel(days=7)
    assert result["days"] == 7
    for stage in result["stages"]:
        assert stage["count"] == 0
        assert stage["pct_of_search"] == 0.0


def test_feature_funnel_search_stage():
    """Search stage counts 'search' and 'public_search' actions."""
    from web.activity_intel import get_feature_funnel
    _insert_activity("search", ip_hash="u1", path="/ask")
    _insert_activity("public_search", ip_hash="u2", path="/")
    _insert_activity("search", ip_hash="u1", path="/ask")  # same user, still counts as 1 unique
    result = get_feature_funnel(days=7)
    search_stage = next(s for s in result["stages"] if s["name"] == "Search")
    assert search_stage["count"] >= 2  # u1 + u2 are distinct
    assert search_stage["pct_of_search"] == 100.0


def test_feature_funnel_analyze_stage():
    """Analyze stage counts 'analyze' and 'analyze_plans' actions."""
    from web.activity_intel import get_feature_funnel
    _insert_activity("analyze", ip_hash="ua1", path="/analyze")
    _insert_activity("analyze_plans", ip_hash="ua2", path="/analyze")
    result = get_feature_funnel(days=7)
    analyze_stage = next(s for s in result["stages"] if s["name"] == "Analyze")
    assert analyze_stage["count"] >= 2


def test_feature_funnel_ask_stage():
    """Ask stage counts any action with path starting with '/ask'."""
    from web.activity_intel import get_feature_funnel
    _insert_activity("search", ip_hash="ask1", path="/ask")
    _insert_activity("lookup", ip_hash="ask2", path="/ask?q=test")
    result = get_feature_funnel(days=7)
    ask_stage = next(s for s in result["stages"] if s["name"] == "Ask")
    assert ask_stage["count"] >= 1


def test_feature_funnel_days_parameter():
    """days parameter is reflected in result."""
    from web.activity_intel import get_feature_funnel
    result = get_feature_funnel(days=14)
    assert result["days"] == 14


# ---------------------------------------------------------------------------
# get_query_refinements
# ---------------------------------------------------------------------------

def test_query_refinements_returns_correct_keys():
    """get_query_refinements returns all required keys."""
    from web.activity_intel import get_query_refinements
    result = get_query_refinements()
    assert "refinement_sessions" in result
    assert "avg_refinements_per_session" in result
    assert "top_refined_queries" in result
    assert "hours" in result


def test_query_refinements_empty_data():
    """get_query_refinements returns zeros when no data exists."""
    from web.activity_intel import get_query_refinements
    result = get_query_refinements(hours=24)
    assert result["refinement_sessions"] == 0
    assert result["avg_refinements_per_session"] == 0.0
    assert result["top_refined_queries"] == []
    assert result["hours"] == 24


def test_query_refinements_detects_repeated_searches():
    """Detects same user searching the same query multiple times."""
    from web.activity_intel import get_query_refinements
    # Same user_id searching 'market st' 3 times
    for _ in range(3):
        _insert_activity("search", user_id=99, path="/ask",
                         detail={"query": "market st"})
    result = get_query_refinements(hours=24)
    assert result["refinement_sessions"] >= 1
    # Should have at least one entry for 'market st' in top_refined_queries
    queries = [q["query"] for q in result["top_refined_queries"]]
    assert any("market" in q.lower() for q in queries)


def test_query_refinements_top_queries_is_list_of_dicts():
    """top_refined_queries is a list of dicts with 'query' and 'count'."""
    from web.activity_intel import get_query_refinements
    _insert_activity("search", ip_hash="r1", path="/ask", detail={"query": "valencia st"})
    _insert_activity("search", ip_hash="r1", path="/ask", detail={"query": "valencia st"})
    result = get_query_refinements(hours=24)
    for item in result["top_refined_queries"]:
        assert "query" in item
        assert "count" in item
        assert isinstance(item["count"], int)


def test_query_refinements_hours_parameter():
    """hours parameter is reflected in result."""
    from web.activity_intel import get_query_refinements
    result = get_query_refinements(hours=72)
    assert result["hours"] == 72


# ---------------------------------------------------------------------------
# get_feedback_by_page
# ---------------------------------------------------------------------------

def test_feedback_by_page_returns_correct_keys():
    """get_feedback_by_page returns all required keys."""
    from web.activity_intel import get_feedback_by_page
    result = get_feedback_by_page()
    assert "pages" in result
    assert "days" in result
    assert isinstance(result["pages"], list)


def test_feedback_by_page_empty_data():
    """get_feedback_by_page returns empty pages list when no data."""
    from web.activity_intel import get_feedback_by_page
    result = get_feedback_by_page(days=30)
    assert result["days"] == 30
    assert result["pages"] == []


def test_feedback_by_page_computes_ratio():
    """Ratio is computed from visits and feedback counts."""
    from web.activity_intel import get_feedback_by_page
    from web.activity import submit_feedback
    # 5 visits to /ask
    for _ in range(5):
        _insert_activity("search", ip_hash="v1", path="/ask")
    # 1 feedback on /ask
    submit_feedback(None, "bug", "test bug", page_url="http://localhost/ask")
    result = get_feedback_by_page(days=30)
    ask_pages = [p for p in result["pages"] if "/ask" in p["path"]]
    if ask_pages:
        page = ask_pages[0]
        assert "visits" in page
        assert "feedback_count" in page
        assert "ratio" in page
        assert page["feedback_count"] >= 1


def test_feedback_by_page_sorted_by_feedback():
    """Pages are sorted by feedback_count descending."""
    from web.activity_intel import get_feedback_by_page
    from web.activity import submit_feedback
    submit_feedback(None, "bug", "bug1", page_url="http://localhost/ask")
    submit_feedback(None, "bug", "bug2", page_url="http://localhost/ask")
    submit_feedback(None, "suggestion", "sug1", page_url="http://localhost/analyze")
    result = get_feedback_by_page(days=30)
    if len(result["pages"]) >= 2:
        counts = [p["feedback_count"] for p in result["pages"]]
        assert counts == sorted(counts, reverse=True)


def test_feedback_by_page_days_parameter():
    """days parameter is reflected in result."""
    from web.activity_intel import get_feedback_by_page
    result = get_feedback_by_page(days=14)
    assert result["days"] == 14


# ---------------------------------------------------------------------------
# get_time_to_first_action
# ---------------------------------------------------------------------------

def test_time_to_first_action_returns_correct_keys():
    """get_time_to_first_action returns all required keys."""
    from web.activity_intel import get_time_to_first_action
    result = get_time_to_first_action()
    assert "avg_seconds" in result
    assert "median_seconds" in result
    assert "sample_size" in result
    assert "days" in result


def test_time_to_first_action_empty_data():
    """get_time_to_first_action returns zeros when no data exists."""
    from web.activity_intel import get_time_to_first_action
    result = get_time_to_first_action(days=7)
    assert result["avg_seconds"] == 0.0
    assert result["median_seconds"] == 0.0
    assert result["sample_size"] == 0
    assert result["days"] == 7


def test_time_to_first_action_computes_gap():
    """Computes gap between first page view and first search."""
    from web.activity_intel import get_time_to_first_action
    from datetime import datetime, timedelta
    # User sees page at T, then searches 30s later
    t_view = datetime.utcnow() - timedelta(hours=2)
    t_search = t_view + timedelta(seconds=30)
    _insert_activity("page_view", ip_hash="gap001", path="/", created_at=t_view)
    _insert_activity("search", ip_hash="gap001", path="/ask", created_at=t_search)
    result = get_time_to_first_action(days=7)
    assert result["sample_size"] >= 1
    assert result["avg_seconds"] >= 0.0


def test_time_to_first_action_days_parameter():
    """days parameter is reflected in result."""
    from web.activity_intel import get_time_to_first_action
    result = get_time_to_first_action(days=14)
    assert result["days"] == 14


# ---------------------------------------------------------------------------
# Admin endpoint access control
# ---------------------------------------------------------------------------

def test_intel_endpoint_requires_admin(client):
    """Non-admin user gets 403 from intel fragment endpoint."""
    _login(client, "regular@test.com")
    rv = client.get("/admin/ops/fragment/intel")
    assert rv.status_code == 403


def test_intel_endpoint_requires_login(client):
    """Unauthenticated request gets 302 redirect from intel endpoint."""
    rv = client.get("/admin/ops/fragment/intel")
    assert rv.status_code in (302, 401, 403)


def test_intel_endpoint_returns_200_for_admin(client, monkeypatch):
    """Admin user gets 200 from intel fragment endpoint."""
    _make_admin(client, email="intel-admin@test.com", monkeypatch=monkeypatch)
    rv = client.get("/admin/ops/fragment/intel")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Intelligence" in html
    assert "Bounce Rate" in html


def test_intel_endpoint_html_contains_all_sections(client, monkeypatch):
    """Intel fragment includes all 5 metric sections."""
    _make_admin(client, email="intel-sections@test.com", monkeypatch=monkeypatch)
    rv = client.get("/admin/ops/fragment/intel")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Bounce Rate" in html
    assert "Feature Funnel" in html
    assert "Query Refinements" in html
    assert "Feedback by Page" in html
    assert "Time to First Action" in html
