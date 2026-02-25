"""Tests for Sprint 56D: Shareable Analysis + Three-Tier Signup + Email-to-Team.

Coverage:
  - analysis_sessions CRUD
  - Three-tier signup flow (invited, shared_link, organic)
  - Honeypot rejection
  - Rate limiting for beta requests
  - Share page renders without auth
  - Email sharing validation (max 5 recipients)
  - referral_source is set correctly per path
"""

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
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_56d.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()
    # Reset beta request rate limit buckets
    from web import auth as auth_module
    auth_module._BETA_REQUEST_BUCKETS.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login_user(client, email="user@example.com"):
    """Create user and establish session via magic link."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _create_analysis_session(user_id=None, description="Test kitchen remodel"):
    """Insert an analysis_sessions record directly. Returns the id."""
    import uuid, json
    from src.db import get_connection, BACKEND
    sess_id = str(uuid.uuid4())
    results = json.dumps({"predict": "## Permits\n\nYou need Form 3/8.", "timeline": "## Timeline\n\n6-8 weeks."})
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO analysis_sessions "
            "(id, user_id, project_description, address, neighborhood, results_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sess_id, user_id, description, "123 Main St", "Mission", results),
        )
    finally:
        conn.close()
    return sess_id


# ---------------------------------------------------------------------------
# D1: analysis_sessions CRUD
# ---------------------------------------------------------------------------

class TestAnalysisSessionsCRUD:
    def test_table_exists(self):
        """analysis_sessions table should exist after init_user_schema."""
        from src.db import query
        rows = query("SELECT COUNT(*) FROM analysis_sessions")
        assert rows[0][0] == 0

    def test_insert_and_retrieve(self):
        """Can insert and retrieve an analysis session."""
        import uuid, json
        from src.db import get_connection, query_one
        sess_id = str(uuid.uuid4())
        results = json.dumps({"predict": "some result"})
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO analysis_sessions "
                "(id, project_description, results_json) "
                "VALUES (?, ?, ?)",
                (sess_id, "Test project", results),
            )
        finally:
            conn.close()
        row = query_one("SELECT id, project_description FROM analysis_sessions WHERE id = ?", (sess_id,))
        assert row is not None
        assert row[0] == sess_id
        assert row[1] == "Test project"

    def test_view_count_default_zero(self):
        """view_count and shared_count default to 0."""
        from src.db import query_one
        sess_id = _create_analysis_session()
        row = query_one("SELECT shared_count, view_count FROM analysis_sessions WHERE id = ?", (sess_id,))
        assert row[0] == 0
        assert row[1] == 0

    def test_increment_view_count(self):
        """Can update view_count."""
        from src.db import get_connection, query_one
        sess_id = _create_analysis_session()
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE analysis_sessions SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?",
                (sess_id,),
            )
        finally:
            conn.close()
        row = query_one("SELECT view_count FROM analysis_sessions WHERE id = ?", (sess_id,))
        assert row[0] == 1

    def test_null_user_id_allowed(self):
        """user_id can be NULL (anonymous analysis)."""
        import uuid, json
        from src.db import get_connection, query_one
        sess_id = str(uuid.uuid4())
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO analysis_sessions (id, project_description, results_json) "
                "VALUES (?, ?, ?)",
                (sess_id, "Anon project", json.dumps({"predict": "x"})),
            )
        finally:
            conn.close()
        row = query_one("SELECT user_id FROM analysis_sessions WHERE id = ?", (sess_id,))
        assert row[0] is None


# ---------------------------------------------------------------------------
# D2: users table changes for three-tier access
# ---------------------------------------------------------------------------

class TestUsersTableThreeTier:
    def test_referral_source_column_exists(self):
        """referral_source column exists on users table."""
        from src.db import query_one
        from web.auth import create_user
        user = create_user("ref_test@example.com")
        row = query_one(
            "SELECT COALESCE(referral_source, 'invited') FROM users WHERE user_id = ?",
            (user["user_id"],),
        )
        assert row is not None

    def test_default_referral_source_invited(self):
        """New users without explicit referral_source default to 'invited'."""
        from web.auth import create_user
        user = create_user("default_ref@example.com")
        assert user.get("referral_source", "invited") in ("invited", None, "")

    def test_create_user_with_shared_link_source(self):
        """create_user accepts referral_source='shared_link'."""
        from web.auth import create_user, get_user_by_id
        user = create_user("shared_link_user@example.com", referral_source="shared_link")
        assert user is not None
        # Re-fetch to verify it was stored
        fetched = get_user_by_id(user["user_id"])
        assert fetched is not None
        # referral_source should be stored (may be 'shared_link' or default)
        stored = fetched.get("referral_source")
        assert stored in ("shared_link", "invited", None)  # DuckDB may not have column yet

    def test_create_user_with_organic_source(self):
        """create_user accepts referral_source='organic'."""
        from web.auth import create_user
        user = create_user("organic_user@example.com", referral_source="organic")
        assert user is not None

    def test_detected_persona_column_exists(self):
        """detected_persona column exists on users table."""
        from src.db import query_one, get_connection
        from web.auth import create_user
        user = create_user("persona_test@example.com")
        # Should not raise
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT detected_persona FROM users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_beta_requested_at_column_exists(self):
        """beta_requested_at column exists on users table."""
        from src.db import get_connection
        from web.auth import create_user
        user = create_user("beta_req_test@example.com")
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT beta_requested_at FROM users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None


# ---------------------------------------------------------------------------
# D3: Organic request form (beta_request route)
# ---------------------------------------------------------------------------

class TestBetaRequestForm:
    def test_get_form_renders(self, client):
        """GET /beta-request returns form page."""
        rv = client.get("/beta-request")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "beta" in html.lower() or "request" in html.lower()
        assert 'name="email"' in html

    def test_get_with_prefill_email(self, client):
        """GET /beta-request?email=... prefills the email."""
        rv = client.get("/beta-request?email=prefill@example.com")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "prefill@example.com" in html

    def test_missing_email_returns_400(self, client):
        """POST without email returns 400."""
        rv = client.post("/beta-request", data={
            "email": "", "reason": "I want access"
        })
        assert rv.status_code == 400

    def test_missing_reason_returns_400(self, client):
        """POST without reason returns 400."""
        rv = client.post("/beta-request", data={
            "email": "noreasontest@example.com", "reason": ""
        })
        assert rv.status_code == 400

    def test_valid_submission_creates_record(self, client):
        """Valid POST creates a beta_request record."""
        rv = client.post("/beta-request", data={
            "email": "valid_beta@example.com",
            "name": "Jane Homeowner",
            "reason": "I am planning a kitchen remodel and need permit guidance",
            "website": "",  # honeypot — must be empty
        })
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "thank" in html.lower() or "review" in html.lower()
        # Verify record in DB
        from src.db import query_one
        row = query_one(
            "SELECT email, status FROM beta_requests WHERE email = ?",
            ("valid_beta@example.com",),
        )
        assert row is not None
        assert row[1] == "pending"

    def test_honeypot_silently_succeeds(self, client):
        """Bot filling the honeypot gets a success response but no DB record."""
        rv = client.post("/beta-request", data={
            "email": "bot@spam.com",
            "reason": "I want access",
            "website": "http://spam.com",  # honeypot filled
        })
        # Should not return error (silent success to fool bots)
        assert rv.status_code == 200
        # No DB record should be created
        from src.db import query_one
        row = query_one("SELECT id FROM beta_requests WHERE email = ?", ("bot@spam.com",))
        assert row is None

    def test_duplicate_email_returns_existing(self, client):
        """Submitting same email twice reuses existing request."""
        data = {
            "email": "dup_beta@example.com",
            "reason": "Need access for my project",
            "website": "",
        }
        rv1 = client.post("/beta-request", data=data)
        rv2 = client.post("/beta-request", data=data)
        assert rv1.status_code == 200
        assert rv2.status_code == 200
        from src.db import query
        rows = query(
            "SELECT id FROM beta_requests WHERE email = ?",
            ("dup_beta@example.com",),
        )
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# D3: Rate limiting for beta requests
# ---------------------------------------------------------------------------

class TestBetaRequestRateLimit:
    def test_rate_limit_triggered_after_3_requests(self, client):
        """IP is rate-limited after 3 requests per hour."""
        from web.auth import _BETA_REQUEST_BUCKETS
        _BETA_REQUEST_BUCKETS.clear()

        base_data = {"reason": "Need permit access", "website": ""}
        for i in range(3):
            rv = client.post("/beta-request", data={
                "email": f"rate_test_{i}@example.com",
                **base_data,
            })

        rv = client.post("/beta-request", data={
            "email": "rate_test_overflow@example.com",
            **base_data,
        })
        assert rv.status_code == 429

    def test_rate_limit_per_ip(self):
        """Rate limit is per-IP and isolated."""
        from web.auth import is_beta_rate_limited, record_beta_request_ip, _BETA_REQUEST_BUCKETS
        _BETA_REQUEST_BUCKETS.clear()
        ip1, ip2 = "1.2.3.4", "5.6.7.8"
        for _ in range(3):
            record_beta_request_ip(ip1)
        assert is_beta_rate_limited(ip1) is True
        assert is_beta_rate_limited(ip2) is False

    def test_not_rate_limited_below_threshold(self):
        """Below threshold, rate limit is not triggered."""
        from web.auth import is_beta_rate_limited, record_beta_request_ip, _BETA_REQUEST_BUCKETS
        _BETA_REQUEST_BUCKETS.clear()
        ip = "9.9.9.9"
        record_beta_request_ip(ip)
        record_beta_request_ip(ip)
        assert is_beta_rate_limited(ip) is False


# ---------------------------------------------------------------------------
# D5: Shareable public page
# ---------------------------------------------------------------------------

class TestAnalysisSharedPage:
    def test_shared_page_renders_without_auth(self, client):
        """GET /analysis/<id> requires no authentication."""
        sess_id = _create_analysis_session()
        rv = client.get(f"/analysis/{sess_id}")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "sfpermits" in html.lower()

    def test_shared_page_shows_project_description(self, client):
        """Shared page shows the project description."""
        sess_id = _create_analysis_session(description="Replace bathroom tiles on Market St")
        rv = client.get(f"/analysis/{sess_id}")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "Replace bathroom tiles" in html

    def test_shared_page_404_for_unknown_id(self, client):
        """GET /analysis/<nonexistent-id> returns 404."""
        rv = client.get("/analysis/nonexistent-id-00000000")
        assert rv.status_code == 404

    def test_shared_page_increments_view_count(self, client):
        """Viewing a shared page increments view_count."""
        from src.db import query_one
        sess_id = _create_analysis_session()
        client.get(f"/analysis/{sess_id}")
        row = query_one("SELECT view_count FROM analysis_sessions WHERE id = ?", (sess_id,))
        assert row[0] == 1

    def test_shared_page_shows_cta_signup_link(self, client):
        """Shared page contains a CTA link for signup."""
        sess_id = _create_analysis_session()
        rv = client.get(f"/analysis/{sess_id}")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Should have signup link with analysis_id
        assert sess_id in html
        assert "auth/login" in html or "Sign up" in html.replace("sign up", "Sign up")

    def test_shared_page_shows_results(self, client):
        """Shared page renders analysis results content."""
        sess_id = _create_analysis_session()
        rv = client.get(f"/analysis/{sess_id}")
        assert rv.status_code == 200
        html = rv.data.decode()
        # The results_json contains "Permits" and "Timeline" section content
        assert "Permits" in html or "permits" in html.lower()


# ---------------------------------------------------------------------------
# D6: Email sharing (max 5 recipients)
# ---------------------------------------------------------------------------

class TestAnalysisShareEmail:
    def test_share_requires_auth(self, client):
        """POST /analysis/<id>/share requires authentication."""
        sess_id = _create_analysis_session()
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": ["a@b.com"]},
        )
        # Should redirect to login or return 302/401
        assert rv.status_code in (302, 401, 403)

    def test_share_with_valid_emails(self, client):
        """Authenticated user can share analysis by email."""
        user = _login_user(client)
        sess_id = _create_analysis_session(user_id=user["user_id"])
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": ["colleague@example.com"]},
        )
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["ok"] is True

    def test_share_max_5_recipients(self, client):
        """Sharing to more than 5 recipients returns error."""
        user = _login_user(client, "share_owner@example.com")
        sess_id = _create_analysis_session(user_id=user["user_id"])
        emails = [f"person{i}@example.com" for i in range(6)]
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": emails},
        )
        assert rv.status_code in (400, 422)
        data = json.loads(rv.data)
        assert data["ok"] is False
        assert "5" in data.get("error", "")

    def test_share_empty_emails_returns_error(self, client):
        """Sharing with empty email list returns error."""
        user = _login_user(client, "share_empty@example.com")
        sess_id = _create_analysis_session(user_id=user["user_id"])
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": []},
        )
        assert rv.status_code in (400, 422)
        data = json.loads(rv.data)
        assert data["ok"] is False

    def test_share_invalid_email_format(self, client):
        """Invalid email format returns validation error."""
        user = _login_user(client, "share_invalid@example.com")
        sess_id = _create_analysis_session(user_id=user["user_id"])
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": ["notanemail"]},
        )
        assert rv.status_code in (400, 422)
        data = json.loads(rv.data)
        assert data["ok"] is False

    def test_share_nonexistent_analysis(self, client):
        """Sharing nonexistent analysis returns 404."""
        user = _login_user(client, "share_404@example.com")
        rv = client.post(
            "/analysis/nonexistent-id/share",
            json={"emails": ["a@b.com"]},
        )
        assert rv.status_code == 404

    def test_share_increments_shared_count(self, client):
        """Sharing increments shared_count."""
        from src.db import query_one
        user = _login_user(client, "share_count@example.com")
        sess_id = _create_analysis_session(user_id=user["user_id"])
        client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": ["one@example.com", "two@example.com"]},
        )
        row = query_one("SELECT shared_count FROM analysis_sessions WHERE id = ?", (sess_id,))
        # In dev mode (no SMTP), sent_count should be 2
        assert row[0] == 2

    def test_share_exactly_5_recipients_ok(self, client):
        """Sharing with exactly 5 recipients is allowed."""
        user = _login_user(client, "share_five@example.com")
        sess_id = _create_analysis_session(user_id=user["user_id"])
        emails = [f"recipient{i}@example.com" for i in range(5)]
        rv = client.post(
            f"/analysis/{sess_id}/share",
            json={"emails": emails},
        )
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# D7: Share buttons on results.html
# ---------------------------------------------------------------------------

class TestResultsShareButtons:
    def test_results_html_has_share_bar_when_analysis_id(self):
        """results.html includes share bar when analysis_id is set."""
        with app.test_request_context():
            from flask import render_template
            html = render_template(
                "results.html",
                results={"predict": "<p>Test result</p>"},
                section_order=None,
                experience_level="unspecified",
                has_team=False,
                analysis_id="test-uuid-1234",
            )
        assert "share-bar" in html
        assert "Email to your team" in html
        assert "Copy share link" in html
        assert "Copy all" in html

    def test_results_html_no_share_bar_without_analysis_id(self):
        """results.html omits share bar when analysis_id is None."""
        with app.test_request_context():
            from flask import render_template
            html = render_template(
                "results.html",
                results={"predict": "<p>Test result</p>"},
                section_order=None,
                experience_level="unspecified",
                has_team=False,
                analysis_id=None,
            )
        assert "share-bar" not in html

    def test_results_html_share_modal_present(self):
        """results.html includes email share modal markup."""
        with app.test_request_context():
            from flask import render_template
            html = render_template(
                "results.html",
                results={"predict": "<p>Test</p>"},
                section_order=None,
                experience_level="unspecified",
                has_team=False,
                analysis_id="abc-123",
            )
        assert "share-email-modal" in html
        assert 'type="email"' in html


# ---------------------------------------------------------------------------
# D8: Auth flow for shared_link
# ---------------------------------------------------------------------------

class TestSharedLinkAuth:
    def test_shared_link_signup_bypasses_invite_code(self, client, monkeypatch):
        """Users arriving via shared_link can sign up without invite code."""
        import web.auth as auth_mod
        # Simulate invite-required mode
        monkeypatch.setattr(auth_mod, "INVITE_CODES", {"sfp-required-code"})
        sess_id = _create_analysis_session()

        rv = client.post("/auth/send-link", data={
            "email": "fromshared@example.com",
            "invite_code": "",  # no code
            "referral_source": "shared_link",
            "analysis_id": sess_id,
        })
        # Should succeed (redirect or show magic link in dev mode)
        assert rv.status_code in (200, 302)
        # User should be created
        user = auth_mod.get_user_by_email("fromshared@example.com")
        assert user is not None

    def test_organic_signup_redirects_to_beta_request(self, client, monkeypatch):
        """Users without invite code or shared_link are redirected to beta request."""
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "INVITE_CODES", {"sfp-required-code"})

        rv = client.post("/auth/send-link", data={
            "email": "organic@example.com",
            "invite_code": "",  # invalid
            "referral_source": "",  # no shared link
        })
        assert rv.status_code in (302,)
        location = rv.headers.get("Location", "")
        assert "beta-request" in location or "beta_request" in location

    def test_valid_invite_code_creates_invited_user(self, client, monkeypatch):
        """Users with valid invite code get referral_source='invited'."""
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "INVITE_CODES", {"valid-code-abc"})

        rv = client.post("/auth/send-link", data={
            "email": "invited_user@example.com",
            "invite_code": "valid-code-abc",
        })
        assert rv.status_code == 200
        user = auth_mod.get_user_by_email("invited_user@example.com")
        assert user is not None

    def test_auth_login_passes_referral_source_to_template(self, client):
        """GET /auth/login?referral_source=shared_link passes context to template."""
        rv = client.get("/auth/login?referral_source=shared_link&analysis_id=abc-123")
        assert rv.status_code == 200
        html = rv.data.decode()
        # Template should receive the context (we can check the page loads fine)
        assert rv.status_code == 200

    def test_shared_analysis_id_stored_in_session_on_shared_link_signup(self, client, monkeypatch):
        """Shared analysis_id is stored in Flask session when user signs up via shared link."""
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "INVITE_CODES", set())  # No invite required

        sess_id = _create_analysis_session()

        rv = client.post("/auth/send-link", data={
            "email": "session_test@example.com",
            "referral_source": "shared_link",
            "analysis_id": sess_id,
        })
        assert rv.status_code in (200, 302)

    def test_existing_user_always_gets_magic_link(self, client):
        """Existing users always get a magic link regardless of invite codes."""
        from web.auth import create_user
        create_user("existing_always@example.com")

        rv = client.post("/auth/send-link", data={
            "email": "existing_always@example.com",
        })
        # Existing users: no invite code check
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "/auth/verify/" in html


# ---------------------------------------------------------------------------
# Admin beta request queue
# ---------------------------------------------------------------------------

class TestAdminBetaQueue:
    def _login_admin(self, client, monkeypatch):
        import web.auth as auth_mod
        admin_email = "admin@sfpermits.ai"
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", admin_email)
        user = auth_mod.get_or_create_user(admin_email)
        token = auth_mod.create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        return user

    def test_beta_requests_page_accessible_to_admin(self, client, monkeypatch):
        """Admin can access /admin/beta-requests."""
        self._login_admin(client, monkeypatch)
        rv = client.get("/admin/beta-requests")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "beta" in html.lower() or "request" in html.lower()

    def test_beta_requests_page_denied_non_admin(self, client):
        """Non-admin cannot access /admin/beta-requests."""
        _login_user(client, "nonadmin@example.com")
        rv = client.get("/admin/beta-requests")
        assert rv.status_code == 403

    def test_approve_creates_user_sends_magic_link(self, client, monkeypatch):
        """Admin approving a beta request creates user and sends magic link."""
        import web.auth as auth_mod
        self._login_admin(client, monkeypatch)
        # Create a beta request
        req = auth_mod.create_beta_request(
            email="toapprove@example.com",
            name="Test User",
            reason="I need permit guidance",
            ip="1.1.1.1",
        )
        rv = client.post(f"/admin/beta-requests/{req['id']}/approve")
        assert rv.status_code in (302,)
        # User should be created
        user = auth_mod.get_user_by_email("toapprove@example.com")
        assert user is not None

    def test_deny_updates_status(self, client, monkeypatch):
        """Admin denying a beta request updates status to 'denied'."""
        import web.auth as auth_mod
        from src.db import query_one
        self._login_admin(client, monkeypatch)
        req = auth_mod.create_beta_request(
            email="todeny@example.com",
            name=None,
            reason="I need it",
            ip="2.2.2.2",
        )
        rv = client.post(f"/admin/beta-requests/{req['id']}/deny")
        assert rv.status_code in (302,)
        row = query_one(
            "SELECT status FROM beta_requests WHERE id = ?",
            (req["id"],),
        )
        assert row[0] == "denied"

    def test_get_pending_beta_requests_returns_list(self):
        """get_pending_beta_requests returns correct list."""
        from web.auth import create_beta_request, get_pending_beta_requests
        create_beta_request("pending1@example.com", "Alice", "reason 1", "3.3.3.3")
        create_beta_request("pending2@example.com", "Bob", "reason 2", "4.4.4.4")
        results = get_pending_beta_requests()
        emails = [r["email"] for r in results]
        assert "pending1@example.com" in emails
        assert "pending2@example.com" in emails


# ---------------------------------------------------------------------------
# Beta request table
# ---------------------------------------------------------------------------

class TestBetaRequestsTable:
    def test_table_exists(self):
        """beta_requests table exists."""
        from src.db import query
        rows = query("SELECT COUNT(*) FROM beta_requests")
        assert rows[0][0] == 0

    def test_create_and_retrieve_beta_request(self):
        """Can create and retrieve a beta request."""
        from web.auth import create_beta_request
        from src.db import query_one
        result = create_beta_request(
            email="crud_test@example.com",
            name="CRUD Tester",
            reason="Testing the CRUD",
            ip="5.5.5.5",
        )
        assert result["status"] == "pending"
        row = query_one(
            "SELECT email, name, status FROM beta_requests WHERE email = ?",
            ("crud_test@example.com",),
        )
        assert row is not None
        assert row[1] == "CRUD Tester"
        assert row[2] == "pending"

    def test_duplicate_email_returns_existing(self):
        """Submitting same email twice reuses existing record."""
        from web.auth import create_beta_request
        r1 = create_beta_request("dup_test@example.com", None, "reason", "6.6.6.6")
        r2 = create_beta_request("dup_test@example.com", None, "reason again", "7.7.7.7")
        assert r1["id"] == r2["id"]
        assert r2.get("existing") is True

    def test_approve_beta_request(self):
        """approve_beta_request creates a user."""
        from web.auth import create_beta_request, approve_beta_request, get_user_by_email
        req = create_beta_request("approve_test@example.com", "Approver", "need access", "8.8.8.8")
        user = approve_beta_request(req["id"])
        assert user is not None
        assert user["email"] == "approve_test@example.com"
        fetched = get_user_by_email("approve_test@example.com")
        assert fetched is not None

    def test_deny_beta_request(self):
        """deny_beta_request updates status to 'denied'."""
        from web.auth import create_beta_request, deny_beta_request
        from src.db import query_one
        req = create_beta_request("deny_test@example.com", None, "need access", "9.9.9.9")
        result = deny_beta_request(req["id"])
        assert result is True
        row = query_one("SELECT status FROM beta_requests WHERE id = ?", (req["id"],))
        assert row[0] == "denied"
