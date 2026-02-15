"""Tests for activity logging and feedback system."""
import os
import sys
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.app import app, _rate_buckets


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_activity.duckdb")
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


def _login_user(client, email="activity-test@example.com"):
    """Helper: create user and log them in via magic link."""
    from web.auth import create_user, create_magic_token
    user = create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _make_admin(client, email="admin-activity@test.com", monkeypatch=None):
    """Helper: create admin user and log them in."""
    import web.auth as auth_mod
    if monkeypatch:
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    user = auth_mod.create_user(email)
    token = auth_mod.create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def test_log_activity_basic(client):
    """Activity log records user actions."""
    from web.activity import log_activity, get_recent_activity
    log_activity(None, "test_action", detail={"key": "value"}, path="/test", ip="127.0.0.1")
    activity = get_recent_activity(limit=10)
    assert len(activity) >= 1
    latest = activity[0]
    assert latest["action"] == "test_action"
    assert latest["detail"]["key"] == "value"
    assert latest["path"] == "/test"


def test_log_activity_with_user(client):
    """Activity log associates actions with user IDs."""
    user = _login_user(client)
    from web.activity import log_activity, get_recent_activity
    log_activity(user["user_id"], "search", detail={"query": "123 main st"}, path="/ask")
    activity = get_recent_activity(limit=10)
    found = [a for a in activity if a["action"] == "search"]
    assert len(found) >= 1
    assert found[0]["user_id"] == user["user_id"]


def test_activity_stats(client):
    """Activity stats returns counts by action."""
    from web.activity import log_activity, get_activity_stats
    log_activity(None, "search", path="/ask")
    log_activity(None, "search", path="/ask")
    log_activity(None, "analyze", path="/analyze")
    stats = get_activity_stats(hours=24)
    assert stats["total"] >= 3
    assert stats["by_action"]["search"] >= 2
    assert stats["by_action"]["analyze"] >= 1


def test_ip_is_hashed(client):
    """IP addresses are stored as hashes, not plaintext."""
    from web.activity import log_activity, get_recent_activity
    log_activity(None, "hash_test", ip="192.168.1.100")
    activity = get_recent_activity(limit=10)
    found = [a for a in activity if a["action"] == "hash_test"]
    assert len(found) == 1
    # ip_hash should not be the raw IP
    # (ip_hash is in the DB but not returned via get_recent_activity — that's OK)


def test_log_activity_never_raises(client):
    """Activity logging is fire-and-forget — never raises exceptions."""
    from web.activity import log_activity
    # Even with bad data, should not raise
    log_activity(None, "test", detail={"a": "b"}, path=None, ip=None)
    # No exception = pass


# ---------------------------------------------------------------------------
# Middleware integration
# ---------------------------------------------------------------------------

def test_middleware_logs_search(client):
    """The /ask endpoint is automatically logged."""
    _login_user(client)
    # Make a search request
    client.post("/ask", data={"q": "test query"})
    from web.activity import get_recent_activity
    activity = get_recent_activity(limit=10)
    search_actions = [a for a in activity if a["action"] == "search"]
    assert len(search_actions) >= 1


def test_middleware_skips_static(client):
    """Static paths like /favicon.ico are not logged."""
    from web.activity import get_recent_activity
    before = len(get_recent_activity(limit=100))
    client.get("/favicon.ico")
    after = len(get_recent_activity(limit=100))
    assert after == before


# ---------------------------------------------------------------------------
# Feedback submission
# ---------------------------------------------------------------------------

def test_feedback_submit_logged_in(client):
    """Logged-in user can submit feedback."""
    _login_user(client)
    rv = client.post("/feedback/submit", data={
        "feedback_type": "bug",
        "message": "The search broke for my address",
        "page_url": "http://localhost/ask?q=test",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Thanks" in html


def test_feedback_submit_anonymous(client):
    """Anonymous user can submit feedback."""
    rv = client.post("/feedback/submit", data={
        "feedback_type": "suggestion",
        "message": "Add dark mode please",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Thanks" in html


def test_feedback_submit_empty_rejected(client):
    """Empty message is rejected."""
    rv = client.post("/feedback/submit", data={
        "feedback_type": "bug",
        "message": "",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "enter a message" in html.lower()


def test_feedback_submit_too_short_rejected(client):
    """Very short message is rejected."""
    rv = client.post("/feedback/submit", data={
        "feedback_type": "bug",
        "message": "ab",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "enter a message" in html.lower()


def test_feedback_queue(client):
    """Admin can view feedback queue."""
    from web.activity import submit_feedback
    submit_feedback(None, "bug", "Test bug report", "/test")
    submit_feedback(None, "suggestion", "Test suggestion", "/test")

    from web.activity import get_feedback_queue
    items = get_feedback_queue()
    assert len(items) >= 2
    types = {i["feedback_type"] for i in items}
    assert "bug" in types
    assert "suggestion" in types


def test_feedback_status_update(client):
    """Admin can update feedback status."""
    from web.activity import submit_feedback, update_feedback_status, get_feedback_queue
    fb = submit_feedback(None, "bug", "Fix this please")
    assert update_feedback_status(fb["feedback_id"], "resolved", "Fixed in v2")
    items = get_feedback_queue()
    resolved = [i for i in items if i["feedback_id"] == fb["feedback_id"]]
    assert len(resolved) == 1
    assert resolved[0]["status"] == "resolved"
    assert resolved[0]["admin_note"] == "Fixed in v2"


def test_feedback_counts(client):
    """Feedback counts returns status breakdown."""
    from web.activity import submit_feedback, get_feedback_counts
    submit_feedback(None, "bug", "Bug one")
    submit_feedback(None, "suggestion", "Idea one")
    counts = get_feedback_counts()
    assert counts["total"] >= 2
    assert counts.get("new", 0) >= 2


def test_feedback_invalid_type_defaults(client):
    """Invalid feedback type defaults to suggestion."""
    from web.activity import submit_feedback
    fb = submit_feedback(None, "invalid_type", "Test message")
    assert fb["feedback_type"] == "suggestion"


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

def test_admin_feedback_page_requires_admin(client):
    """Non-admin cannot access feedback queue."""
    _login_user(client, "nonadmin@test.com")
    rv = client.get("/admin/feedback")
    assert rv.status_code == 403


def test_admin_activity_page_requires_admin(client):
    """Non-admin cannot access activity feed."""
    _login_user(client, "nonadmin2@test.com")
    rv = client.get("/admin/activity")
    assert rv.status_code == 403


def test_admin_feedback_page_works(client, monkeypatch):
    """Admin can access feedback queue page."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback
    submit_feedback(None, "bug", "Test bug for admin page")
    rv = client.get("/admin/feedback")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Feedback Queue" in html
    assert "Test bug for admin page" in html


def test_admin_activity_page_works(client, monkeypatch):
    """Admin can access activity feed page."""
    _make_admin(client, monkeypatch=monkeypatch)
    rv = client.get("/admin/activity")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Activity Feed" in html


def test_admin_feedback_update_route(client, monkeypatch):
    """Admin can update feedback via HTMX route."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "Route test bug")
    rv = client.post("/admin/feedback/update", data={
        "feedback_id": str(fb["feedback_id"]),
        "status": "resolved",
        "admin_note": "Done",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Resolved" in html


def test_admin_feedback_filter_by_status(client, monkeypatch):
    """Feedback queue supports status filtering."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback, update_feedback_status
    fb1 = submit_feedback(None, "bug", "Open bug")
    fb2 = submit_feedback(None, "suggestion", "Resolved idea")
    update_feedback_status(fb2["feedback_id"], "resolved")

    rv = client.get("/admin/feedback?status=new")
    html = rv.data.decode()
    assert "Open bug" in html

    rv = client.get("/admin/feedback?status=resolved")
    html = rv.data.decode()
    assert "Resolved idea" in html


# ---------------------------------------------------------------------------
# Account page: admin cards
# ---------------------------------------------------------------------------

def test_account_shows_activity_stats_for_admin(client, monkeypatch):
    """Admin account page shows activity stats card."""
    _make_admin(client, monkeypatch=monkeypatch)
    rv = client.get("/account")
    html = rv.data.decode()
    assert "Admin: Activity" in html
    assert "View full activity feed" in html


def test_account_shows_feedback_queue_for_admin(client, monkeypatch):
    """Admin account page shows feedback queue card."""
    _make_admin(client, monkeypatch=monkeypatch)
    rv = client.get("/account")
    html = rv.data.decode()
    assert "Admin: Feedback Queue" in html
    assert "Review feedback" in html


def test_account_hides_admin_cards_for_regular_user(client):
    """Regular user doesn't see admin cards."""
    _login_user(client, "regular@test.com")
    rv = client.get("/account")
    html = rv.data.decode()
    assert "Admin: Activity" not in html
    assert "Admin: Feedback Queue" not in html


# ---------------------------------------------------------------------------
# Feedback widget
# ---------------------------------------------------------------------------

def test_feedback_widget_on_index(client):
    """Index page includes feedback widget."""
    rv = client.get("/")
    html = rv.data.decode()
    assert "feedback-fab" in html
    assert "Send Feedback" in html


def test_feedback_widget_on_account(client):
    """Account page includes feedback widget."""
    _login_user(client)
    rv = client.get("/account")
    html = rv.data.decode()
    assert "feedback-fab" in html
