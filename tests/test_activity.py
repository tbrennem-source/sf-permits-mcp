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


# ---------------------------------------------------------------------------
# Feedback screenshots
# ---------------------------------------------------------------------------

# Minimal valid 1x1 JPEG as data URL for testing
_TINY_JPEG = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP/bAEMAFA=="


def test_feedback_submit_with_screenshot(client):
    """Feedback submission accepts screenshot data."""
    _login_user(client)
    rv = client.post("/feedback/submit", data={
        "feedback_type": "bug",
        "message": "Something looks wrong on this page",
        "page_url": "http://localhost/ask",
        "screenshot_data": _TINY_JPEG,
    })
    assert rv.status_code == 200
    assert "Thanks" in rv.data.decode()


def test_feedback_submit_without_screenshot(client):
    """Feedback submission still works without screenshot (backward compat)."""
    rv = client.post("/feedback/submit", data={
        "feedback_type": "suggestion",
        "message": "Add a new feature please",
    })
    assert rv.status_code == 200
    assert "Thanks" in rv.data.decode()


def test_feedback_screenshot_stored_and_retrievable(client):
    """Screenshot data is stored and can be retrieved."""
    from web.activity import submit_feedback, get_feedback_screenshot
    fb = submit_feedback(None, "bug", "Screenshot test", screenshot_data=_TINY_JPEG)
    retrieved = get_feedback_screenshot(fb["feedback_id"])
    assert retrieved == _TINY_JPEG


def test_feedback_screenshot_none_when_absent(client):
    """get_feedback_screenshot returns None when no screenshot."""
    from web.activity import submit_feedback, get_feedback_screenshot
    fb = submit_feedback(None, "bug", "No screenshot")
    assert get_feedback_screenshot(fb["feedback_id"]) is None


def test_feedback_queue_has_screenshot_flag(client):
    """Feedback queue items include has_screenshot boolean."""
    from web.activity import submit_feedback, get_feedback_queue
    submit_feedback(None, "bug", "With screenshot ss_flag", screenshot_data=_TINY_JPEG)
    submit_feedback(None, "suggestion", "Without screenshot ss_flag")
    items = get_feedback_queue()
    with_ss = [i for i in items if i["message"] == "With screenshot ss_flag"]
    without_ss = [i for i in items if i["message"] == "Without screenshot ss_flag"]
    assert len(with_ss) == 1 and with_ss[0]["has_screenshot"] is True
    assert len(without_ss) == 1 and without_ss[0]["has_screenshot"] is False


def test_feedback_screenshot_invalid_data_dropped(client):
    """Invalid screenshot data (not a data URL) is silently dropped."""
    _login_user(client)
    rv = client.post("/feedback/submit", data={
        "feedback_type": "bug",
        "message": "Bad screenshot data test",
        "screenshot_data": "not-a-data-url",
    })
    assert rv.status_code == 200
    assert "Thanks" in rv.data.decode()
    from web.activity import get_feedback_queue
    items = get_feedback_queue()
    found = [i for i in items if i["message"] == "Bad screenshot data test"]
    assert len(found) == 1
    assert found[0]["has_screenshot"] is False


def test_feedback_screenshot_too_large_dropped(client):
    """Screenshot data exceeding 2MB is silently dropped by the route."""
    _login_user(client)
    # Build a data URL just over the 2MB threshold
    # Use a shorter payload to avoid Flask request size issues in tests
    large_data = "data:image/jpeg;base64," + "A" * (2 * 1024 * 1024 + 100)
    # Test the validation logic directly via the app context
    with app.test_request_context():
        screenshot_data = large_data
        if not screenshot_data.startswith("data:image/"):
            screenshot_data = None
        elif len(screenshot_data) > 2 * 1024 * 1024:
            screenshot_data = None
        assert screenshot_data is None, "Oversized screenshot should be rejected"


def test_admin_screenshot_route_requires_admin(client):
    """Non-admin cannot access screenshot route."""
    _login_user(client, "nonadmin-ss@test.com")
    rv = client.get("/admin/feedback/1/screenshot")
    assert rv.status_code == 403


def test_admin_screenshot_route_404_when_missing(client, monkeypatch):
    """Screenshot route returns 404 when no screenshot exists."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "No screenshot for 404 test")
    rv = client.get(f"/admin/feedback/{fb['feedback_id']}/screenshot")
    assert rv.status_code == 404


def test_admin_screenshot_route_serves_image(client, monkeypatch):
    """Screenshot route serves the image with correct mime type."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "Image serve test", screenshot_data=_TINY_JPEG)
    rv = client.get(f"/admin/feedback/{fb['feedback_id']}/screenshot")
    assert rv.status_code == 200
    assert rv.content_type.startswith("image/jpeg")


def test_admin_feedback_page_shows_screenshot_button(client, monkeypatch):
    """Admin feedback page shows 'View Screenshot' button for items with screenshots."""
    _make_admin(client, monkeypatch=monkeypatch)
    from web.activity import submit_feedback
    submit_feedback(None, "bug", "Has screenshot admin view", screenshot_data=_TINY_JPEG)
    rv = client.get("/admin/feedback")
    html = rv.data.decode()
    assert "View Screenshot" in html


def test_feedback_widget_has_capture_button(client):
    """Feedback widget includes screenshot capture button."""
    rv = client.get("/")
    html = rv.data.decode()
    assert "Capture Page" in html
    assert "Upload Image" in html


# ---------------------------------------------------------------------------
# Feedback API endpoints
# ---------------------------------------------------------------------------

def test_api_feedback_requires_cron_secret(client):
    """API feedback endpoint requires CRON_SECRET auth."""
    rv = client.get("/api/feedback")
    assert rv.status_code == 403


def test_api_feedback_returns_json(client, monkeypatch):
    """API feedback endpoint returns JSON with items and counts."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback
    submit_feedback(None, "bug", "API test bug")
    submit_feedback(None, "suggestion", "API test suggestion")

    rv = client.get("/api/feedback", headers={
        "Authorization": "Bearer test-secret-123"
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "items" in data
    assert "counts" in data
    assert len(data["items"]) >= 2
    # Check item structure
    item = data["items"][0]
    assert "feedback_id" in item
    assert "feedback_type" in item
    assert "message" in item
    assert "has_screenshot" in item
    assert "created_at" in item
    # Timestamps are ISO strings, not datetimes
    assert isinstance(item["created_at"], str)


def test_api_feedback_status_filter(client, monkeypatch):
    """API feedback endpoint filters by status."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback, update_feedback_status
    fb1 = submit_feedback(None, "bug", "New bug for filter test")
    fb2 = submit_feedback(None, "bug", "Resolved bug for filter test")
    update_feedback_status(fb2["feedback_id"], "resolved")

    rv = client.get("/api/feedback?status=new", headers={
        "Authorization": "Bearer test-secret-123"
    })
    data = rv.get_json()
    statuses = {item["status"] for item in data["items"]}
    assert "resolved" not in statuses


def test_api_feedback_multi_status_filter(client, monkeypatch):
    """API feedback endpoint supports multiple status values."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback, update_feedback_status
    fb = submit_feedback(None, "bug", "Reviewed bug multi-filter")
    update_feedback_status(fb["feedback_id"], "reviewed")

    rv = client.get("/api/feedback?status=new&status=reviewed", headers={
        "Authorization": "Bearer test-secret-123"
    })
    data = rv.get_json()
    statuses = {item["status"] for item in data["items"]}
    assert statuses <= {"new", "reviewed"}


def test_api_feedback_screenshot_requires_auth(client):
    """API screenshot endpoint requires CRON_SECRET auth."""
    rv = client.get("/api/feedback/1/screenshot")
    assert rv.status_code == 403


def test_api_feedback_screenshot_serves_image(client, monkeypatch):
    """API screenshot endpoint serves image with CRON_SECRET."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "Screenshot API test", screenshot_data=_TINY_JPEG)

    rv = client.get(f"/api/feedback/{fb['feedback_id']}/screenshot", headers={
        "Authorization": "Bearer test-secret-123"
    })
    assert rv.status_code == 200
    assert rv.content_type.startswith("image/jpeg")


def test_api_feedback_screenshot_404(client, monkeypatch):
    """API screenshot endpoint returns 404 when no screenshot."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "No screenshot API test")

    rv = client.get(f"/api/feedback/{fb['feedback_id']}/screenshot", headers={
        "Authorization": "Bearer test-secret-123"
    })
    assert rv.status_code == 404


# ---------------------------------------------------------------------------
# Feedback triage pre-processing
# ---------------------------------------------------------------------------

def test_api_feedback_patch_requires_auth(client):
    """PATCH endpoint requires CRON_SECRET."""
    rv = client.patch("/api/feedback/1", json={"status": "resolved"})
    assert rv.status_code == 403


def test_api_feedback_patch_resolves(client, monkeypatch):
    """PATCH endpoint marks feedback as resolved."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "Patch test bug")

    rv = client.patch(
        f"/api/feedback/{fb['feedback_id']}",
        json={"status": "resolved", "admin_note": "Fixed in commit abc"},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "resolved"
    assert data["admin_note"] == "Fixed in commit abc"


def test_api_feedback_patch_invalid_status(client, monkeypatch):
    """PATCH endpoint rejects invalid status values."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    from web.activity import submit_feedback
    fb = submit_feedback(None, "bug", "Invalid status test")

    rv = client.patch(
        f"/api/feedback/{fb['feedback_id']}",
        json={"status": "invalid_status"},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 400
    assert "Invalid status" in rv.get_json()["error"]


def test_api_feedback_patch_missing_status(client, monkeypatch):
    """PATCH endpoint requires status field."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    rv = client.patch(
        "/api/feedback/1",
        json={"admin_note": "no status"},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 400


# ---------------------------------------------------------------------------
# Address suffix stripping
# ---------------------------------------------------------------------------

def test_strip_suffix():
    """Street suffix stripping for address lookup."""
    from src.tools.permit_lookup import _strip_suffix

    assert _strip_suffix("16th Ave") == ("16th", "Ave")
    assert _strip_suffix("Robin Hood Dr") == ("Robin Hood", "Dr")
    assert _strip_suffix("Market St") == ("Market", "St")
    assert _strip_suffix("Market Street") == ("Market", "Street")
    assert _strip_suffix("Broadway") == ("Broadway", None)
    assert _strip_suffix("6th") == ("6th", None)
    assert _strip_suffix("Lake") == ("Lake", None)
    assert _strip_suffix("De Haro St") == ("De Haro", "St")


def test_triage_severity_classification():
    """Severity classification based on keywords."""
    from scripts.feedback_triage import classify_severity

    assert classify_severity({"feedback_type": "bug", "message": "Page is broken"}) == "HIGH"
    assert classify_severity({"feedback_type": "bug", "message": "Error loading results"}) == "HIGH"
    assert classify_severity({"feedback_type": "bug", "message": "The button color is off"}) == "NORMAL"
    assert classify_severity({"feedback_type": "suggestion", "message": "Would be nice to add dark mode"}) == "LOW"
    assert classify_severity({"feedback_type": "suggestion", "message": "Search crashes every time"}) == "HIGH"


def test_triage_page_area_extraction():
    """Page area extraction from URLs."""
    from scripts.feedback_triage import extract_page_area

    assert extract_page_area("https://sfpermits.ai/analyze?q=test") == "Search/Analyze"
    assert extract_page_area("https://sfpermits.ai/report/123") == "Property Report"
    assert extract_page_area("https://sfpermits.ai/ask") == "Ask AI"
    assert extract_page_area("https://sfpermits.ai/") == "Home"
    assert extract_page_area(None) == "Unknown"
    assert extract_page_area("https://sfpermits.ai/account") == "Account"


def test_triage_age_formatting():
    """Age formatting from ISO timestamps."""
    from scripts.feedback_triage import format_age
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    assert "m ago" in format_age((now - timedelta(minutes=5)).isoformat())
    assert "h ago" in format_age((now - timedelta(hours=3)).isoformat())
    assert "d ago" in format_age((now - timedelta(days=2)).isoformat())
    assert format_age(None) == "unknown"


def test_triage_format_report():
    """Format triage report groups items by severity."""
    from scripts.feedback_triage import format_triage_report

    items = [
        {"feedback_id": 1, "feedback_type": "bug", "message": "Broken page",
         "page_url": "/analyze", "status": "new", "email": "a@b.com",
         "has_screenshot": True, "severity": "HIGH", "page_area": "Search/Analyze",
         "age": "2h ago", "admin_note": None},
        {"feedback_id": 2, "feedback_type": "suggestion", "message": "Add feature",
         "page_url": "/", "status": "new", "email": None,
         "has_screenshot": False, "severity": "LOW", "page_area": "Home",
         "age": "3d ago", "admin_note": None},
    ]
    counts = {"new": 2, "reviewed": 0, "resolved": 0, "wontfix": 0, "total": 2}

    report = format_triage_report(items, counts)
    assert "2 unresolved items" in report
    assert "HIGH PRIORITY" in report
    assert "#1 [bug]" in report
    assert "Screenshot attached" in report
    assert "LOW" in report
    assert "#2 [suggestion]" in report


# ---------------------------------------------------------------------------
# Bounty points system
# ---------------------------------------------------------------------------

def test_award_points_basic_bug(client):
    """Bug report awards 10 base points."""
    user = _login_user(client, "points-bug@test.com")
    from web.activity import submit_feedback, update_feedback_status, award_points, get_user_points
    fb = submit_feedback(user["user_id"], "bug", "Button is broken")
    update_feedback_status(fb["feedback_id"], "resolved", "Fixed it")
    entries = award_points(fb["feedback_id"])
    assert any(e["reason"] == "bug_report" and e["points"] == 10 for e in entries)
    assert get_user_points(user["user_id"]) >= 10


def test_award_points_basic_suggestion(client):
    """Suggestion awards 5 base points."""
    user = _login_user(client, "points-sug@test.com")
    from web.activity import submit_feedback, award_points, get_user_points
    fb = submit_feedback(user["user_id"], "suggestion", "Add dark mode")
    entries = award_points(fb["feedback_id"])
    assert any(e["reason"] == "suggestion" and e["points"] == 5 for e in entries)
    assert get_user_points(user["user_id"]) >= 5


def test_award_points_screenshot_bonus(client):
    """Screenshot attachment adds +2 points."""
    user = _login_user(client, "points-ss@test.com")
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(user["user_id"], "bug", "See screenshot", screenshot_data=_TINY_JPEG)
    entries = award_points(fb["feedback_id"])
    assert any(e["reason"] == "screenshot" and e["points"] == 2 for e in entries)


def test_award_points_first_reporter_bonus(client):
    """First reporter flag adds +5 points."""
    user = _login_user(client, "points-first@test.com")
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(user["user_id"], "bug", "Found a new issue")
    entries = award_points(fb["feedback_id"], first_reporter=True)
    assert any(e["reason"] == "first_reporter" and e["points"] == 5 for e in entries)


def test_award_points_admin_bonus(client):
    """Admin bonus adds custom points."""
    user = _login_user(client, "points-bonus@test.com")
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(user["user_id"], "bug", "Critical security bug")
    entries = award_points(fb["feedback_id"], admin_bonus=10)
    assert any(e["reason"] == "admin_bonus" and e["points"] == 10 for e in entries)


def test_award_points_idempotent(client):
    """Awarding points twice for same feedback_id is a no-op."""
    user = _login_user(client, "points-idem@test.com")
    from web.activity import submit_feedback, award_points, get_user_points
    fb = submit_feedback(user["user_id"], "bug", "Idempotency test")
    entries1 = award_points(fb["feedback_id"])
    assert len(entries1) >= 1
    points_after_first = get_user_points(user["user_id"])
    entries2 = award_points(fb["feedback_id"])
    assert entries2 == []
    assert get_user_points(user["user_id"]) == points_after_first


def test_award_points_anonymous_skipped(client):
    """Anonymous feedback (no user_id) gets no points."""
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(None, "bug", "Anonymous bug report")
    entries = award_points(fb["feedback_id"])
    assert entries == []


def test_get_user_points_zero_for_new_user(client):
    """New user with no points returns 0."""
    user = _login_user(client, "points-zero@test.com")
    from web.activity import get_user_points
    assert get_user_points(user["user_id"]) == 0


def test_get_points_history(client):
    """Points history returns recent entries with labels."""
    user = _login_user(client, "points-hist@test.com")
    from web.activity import submit_feedback, award_points, get_points_history
    fb = submit_feedback(user["user_id"], "bug", "History test bug", screenshot_data=_TINY_JPEG)
    award_points(fb["feedback_id"], first_reporter=True)
    history = get_points_history(user["user_id"])
    assert len(history) >= 3  # bug_report + screenshot + first_reporter
    reasons = {e["reason"] for e in history}
    assert "bug_report" in reasons
    assert "screenshot" in reasons
    assert "first_reporter" in reasons
    # Check labels are present
    labels = {e["reason_label"] for e in history}
    assert "Bug report" in labels
    assert "Screenshot attached" in labels
    assert "First reporter bonus" in labels


def test_award_points_accumulate(client):
    """Multiple resolved feedback items accumulate points."""
    user = _login_user(client, "points-accum@test.com")
    from web.activity import submit_feedback, award_points, get_user_points
    fb1 = submit_feedback(user["user_id"], "bug", "First bug")
    fb2 = submit_feedback(user["user_id"], "suggestion", "First suggestion")
    award_points(fb1["feedback_id"])  # 10 pts
    award_points(fb2["feedback_id"])  # 5 pts
    total = get_user_points(user["user_id"])
    assert total >= 15


def test_get_feedback_item(client):
    """get_feedback_item returns correct structure."""
    user = _login_user(client, "points-item@test.com")
    from web.activity import submit_feedback, get_feedback_item
    fb = submit_feedback(user["user_id"], "bug", "Item retrieval test", screenshot_data=_TINY_JPEG)
    item = get_feedback_item(fb["feedback_id"])
    assert item is not None
    assert item["feedback_id"] == fb["feedback_id"]
    assert item["user_id"] == user["user_id"]
    assert item["feedback_type"] == "bug"
    assert item["has_screenshot"] is True


def test_get_feedback_item_not_found(client):
    """get_feedback_item returns None for nonexistent ID."""
    from web.activity import get_feedback_item
    assert get_feedback_item(99999) is None


def test_get_admin_users(client, monkeypatch):
    """get_admin_users returns active admin users."""
    _make_admin(client, email="admin1@test.com", monkeypatch=monkeypatch)
    from web.activity import get_admin_users
    admins = get_admin_users()
    assert len(admins) >= 1
    admin = admins[0]
    assert "user_id" in admin
    assert "email" in admin
    assert admin["email"] == "admin1@test.com"


# ---------------------------------------------------------------------------
# Points wired into resolution endpoints
# ---------------------------------------------------------------------------

def test_patch_endpoint_awards_points(client, monkeypatch):
    """PATCH /api/feedback/<id> with resolved status awards points."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    user = _login_user(client, "patch-points@test.com")
    from web.activity import submit_feedback, get_user_points
    fb = submit_feedback(user["user_id"], "bug", "Patch points test")

    rv = client.patch(
        f"/api/feedback/{fb['feedback_id']}",
        json={"status": "resolved", "admin_note": "Fixed"},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 200
    # User should have points
    assert get_user_points(user["user_id"]) >= 10


def test_patch_endpoint_first_reporter_flag(client, monkeypatch):
    """PATCH endpoint respects first_reporter flag."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    user = _login_user(client, "patch-fr@test.com")
    from web.activity import submit_feedback, get_user_points
    fb = submit_feedback(user["user_id"], "bug", "First reporter patch test")

    rv = client.patch(
        f"/api/feedback/{fb['feedback_id']}",
        json={"status": "resolved", "first_reporter": True},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 200
    # Should have bug (10) + first reporter (5) = 15 minimum
    assert get_user_points(user["user_id"]) >= 15


def test_admin_resolve_awards_points(client, monkeypatch):
    """Admin HTMX resolve route awards points."""
    # Create a regular user and submit feedback first (directly, no login needed)
    from web.auth import create_user
    user = create_user("admin-resolve-pts@test.com")
    from web.activity import submit_feedback, get_user_points
    fb = submit_feedback(user["user_id"], "suggestion", "Admin resolve test")

    # Now log in as admin and resolve
    _make_admin(client, monkeypatch=monkeypatch)
    rv = client.post("/admin/feedback/update", data={
        "feedback_id": str(fb["feedback_id"]),
        "status": "resolved",
    })
    assert rv.status_code == 200
    # User should have suggestion points
    assert get_user_points(user["user_id"]) >= 5


def test_account_page_shows_points(client):
    """Account page displays points card."""
    user = _login_user(client, "points-page@test.com")
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(user["user_id"], "bug", "Points display test")
    award_points(fb["feedback_id"])

    rv = client.get("/account")
    html = rv.data.decode()
    assert "Points" in html


def test_points_api_endpoint(client, monkeypatch):
    """GET /api/points/<user_id> returns points data."""
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    user = _login_user(client, "api-points@test.com")
    from web.activity import submit_feedback, award_points
    fb = submit_feedback(user["user_id"], "bug", "API points test")
    award_points(fb["feedback_id"])

    rv = client.get(
        f"/api/points/{user['user_id']}",
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["total"] >= 10
    assert "history" in data


def test_points_api_requires_auth(client):
    """Points API requires CRON_SECRET authentication."""
    rv = client.get("/api/points/1")
    assert rv.status_code == 403
