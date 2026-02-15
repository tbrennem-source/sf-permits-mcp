"""Tests for user accounts, authentication, impersonation, and watch list."""

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
    db_path = str(tmp_path / "test_auth.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Reset cached backend detection in db module
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    # Reset schema init flag in auth module
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    # Init schema
    db_mod.init_user_schema()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


def _login_user(client, email="test@example.com"):
    """Helper: create user and magic-link session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _make_admin(email="admin@example.com", monkeypatch=None):
    """Helper: create an admin user."""
    import web.auth as auth_mod
    if monkeypatch:
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", email)
    else:
        auth_mod.ADMIN_EMAIL = email
    return auth_mod.get_or_create_user(email)


# ---------------------------------------------------------------------------
# Auth: login page
# ---------------------------------------------------------------------------

def test_login_page_loads(client):
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "magic link" in html.lower()
    assert 'name="email"' in html


# ---------------------------------------------------------------------------
# Auth: send magic link
# ---------------------------------------------------------------------------

def test_send_link_new_user(client):
    rv = client.post("/auth/send-link", data={"email": "new@example.com"})
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "/auth/verify/" in html  # dev mode shows link
    from web.auth import get_user_by_email
    user = get_user_by_email("new@example.com")
    assert user is not None
    assert user["email"] == "new@example.com"


def test_send_link_existing_user(client):
    from web.auth import create_user
    create_user("existing@example.com")
    rv = client.post("/auth/send-link", data={"email": "existing@example.com"})
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "/auth/verify/" in html


def test_send_link_invalid_email(client):
    rv = client.post("/auth/send-link", data={"email": "notanemail"})
    assert rv.status_code == 400


# ---------------------------------------------------------------------------
# Auth: verify token
# ---------------------------------------------------------------------------

def test_verify_valid_token(client):
    from web.auth import create_user, create_magic_token
    user = create_user("verify@example.com")
    token = create_magic_token(user["user_id"])
    rv = client.get(f"/auth/verify/{token}", follow_redirects=False)
    assert rv.status_code == 302  # redirect to /
    # Session should be set
    with client.session_transaction() as sess:
        assert sess["user_id"] == user["user_id"]
        assert sess["email"] == "verify@example.com"


def test_verify_expired_token(client):
    from web.auth import create_user, create_magic_token
    from src.db import get_connection
    user = create_user("expired@example.com")
    token = create_magic_token(user["user_id"])
    # Manually expire the token
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE auth_tokens SET expires_at = '2020-01-01' WHERE token = ?",
            (token,),
        )
    finally:
        conn.close()
    rv = client.get(f"/auth/verify/{token}")
    assert rv.status_code == 400
    html = rv.data.decode()
    assert "expired" in html.lower() or "invalid" in html.lower()


def test_verify_used_token(client):
    from web.auth import create_user, create_magic_token
    user = create_user("used@example.com")
    token = create_magic_token(user["user_id"])
    # Use it once
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    # Try again — should fail
    rv = client.get(f"/auth/verify/{token}")
    assert rv.status_code == 400


def test_verify_nonexistent_token(client):
    rv = client.get("/auth/verify/bogus-token-12345")
    assert rv.status_code == 400


# ---------------------------------------------------------------------------
# Auth: logout
# ---------------------------------------------------------------------------

def test_logout(client):
    _login_user(client)
    with client.session_transaction() as sess:
        assert "user_id" in sess
    rv = client.post("/auth/logout", follow_redirects=False)
    assert rv.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ---------------------------------------------------------------------------
# Auth: session persistence
# ---------------------------------------------------------------------------

def test_session_persists_across_requests(client):
    _login_user(client, "persist@example.com")
    rv = client.get("/")
    html = rv.data.decode()
    assert "persist@example.com" in html
    assert "Sign in" not in html


def test_anonymous_sees_sign_in(client):
    rv = client.get("/")
    html = rv.data.decode()
    assert "Sign in" in html


# ---------------------------------------------------------------------------
# Admin impersonation
# ---------------------------------------------------------------------------

def test_impersonate_as_admin(client, monkeypatch):
    admin = _make_admin("admin@test.com", monkeypatch)
    # Login as admin
    from web.auth import create_magic_token
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    # Create target user
    from web.auth import create_user
    target = create_user("target@test.com")
    # Impersonate
    rv = client.post("/auth/impersonate", data={"target_email": "target@test.com"},
                     follow_redirects=False)
    assert rv.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == target["user_id"]
        assert sess["impersonating"] == "target@test.com"
        assert sess["admin_user_id"] == admin["user_id"]


def test_impersonate_as_non_admin(client):
    _login_user(client, "regular@test.com")
    rv = client.post("/auth/impersonate", data={"target_email": "someone@test.com"})
    assert rv.status_code == 403


def test_stop_impersonate(client, monkeypatch):
    admin = _make_admin("admin2@test.com", monkeypatch)
    from web.auth import create_magic_token, create_user
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    create_user("target2@test.com")
    client.post("/auth/impersonate", data={"target_email": "target2@test.com"})
    # Stop
    rv = client.post("/auth/stop-impersonate", follow_redirects=False)
    assert rv.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == admin["user_id"]
        assert "impersonating" not in sess


def test_admin_email_retroactive(client, monkeypatch):
    """User created before ADMIN_EMAIL is set still gets admin when env var matches."""
    import web.auth as auth_mod
    # Create user with no ADMIN_EMAIL set — should NOT be admin
    monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", None)
    user = auth_mod.create_user("retroactive-admin@test.com")
    assert not user["is_admin"]

    # Now set ADMIN_EMAIL to match — user should dynamically become admin
    monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", "retroactive-admin@test.com")
    user2 = auth_mod.get_user_by_email("retroactive-admin@test.com")
    assert user2["is_admin"]


# ---------------------------------------------------------------------------
# Watch list: add/remove
# ---------------------------------------------------------------------------

def test_watch_add_logged_in(client):
    _login_user(client)
    rv = client.post("/watch/add", data={
        "watch_type": "permit",
        "permit_number": "202401019876",
        "label": "Test permit",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Watching" in html


def test_watch_add_not_logged_in(client):
    rv = client.post("/watch/add", data={
        "watch_type": "permit",
        "permit_number": "202401019876",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Sign in" in html


def test_watch_remove(client):
    user = _login_user(client)
    from web.auth import add_watch
    watch = add_watch(user["user_id"], "permit", permit_number="123456789")
    rv = client.post("/watch/remove", data={"watch_id": str(watch["watch_id"])})
    assert rv.status_code == 200
    from web.auth import get_watches
    watches = get_watches(user["user_id"])
    assert len(watches) == 0


def test_watch_duplicate_idempotent(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    w1 = add_watch(user["user_id"], "permit", permit_number="999999999")
    w2 = add_watch(user["user_id"], "permit", permit_number="999999999")
    assert w1["watch_id"] == w2["watch_id"]
    watches = get_watches(user["user_id"])
    assert len(watches) == 1


# ---------------------------------------------------------------------------
# Watch list: all 5 types
# ---------------------------------------------------------------------------

def test_watch_permit(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    add_watch(user["user_id"], "permit", permit_number="202401010001")
    watches = get_watches(user["user_id"])
    assert len(watches) == 1
    assert watches[0]["watch_type"] == "permit"


def test_watch_address(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    add_watch(user["user_id"], "address", street_number="123", street_name="Main")
    watches = get_watches(user["user_id"])
    assert len(watches) == 1
    assert watches[0]["watch_type"] == "address"


def test_watch_parcel(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    add_watch(user["user_id"], "parcel", block="3512", lot="001")
    watches = get_watches(user["user_id"])
    assert len(watches) == 1
    assert watches[0]["watch_type"] == "parcel"


def test_watch_entity(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    add_watch(user["user_id"], "entity", entity_id=12345)
    watches = get_watches(user["user_id"])
    assert len(watches) == 1
    assert watches[0]["watch_type"] == "entity"


def test_watch_neighborhood(client):
    user = _login_user(client)
    from web.auth import add_watch, get_watches
    add_watch(user["user_id"], "neighborhood", neighborhood="Mission")
    watches = get_watches(user["user_id"])
    assert len(watches) == 1
    assert watches[0]["watch_type"] == "neighborhood"


# ---------------------------------------------------------------------------
# Account page
# ---------------------------------------------------------------------------

def test_account_page_logged_in(client):
    user = _login_user(client, "acct@example.com")
    from web.auth import add_watch
    add_watch(user["user_id"], "permit", permit_number="111111111", label="My project")
    rv = client.get("/account")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "acct@example.com" in html
    assert "My project" in html
    assert "Watch List" in html


def test_account_page_not_logged_in(client):
    rv = client.get("/account", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers["Location"]


# ---------------------------------------------------------------------------
# Header: auth state rendering
# ---------------------------------------------------------------------------

def test_header_shows_email_when_logged_in(client):
    _login_user(client, "header@example.com")
    rv = client.get("/")
    html = rv.data.decode()
    assert "header@example.com" in html
    assert "Logout" in html


def test_header_shows_sign_in_when_anonymous(client):
    rv = client.get("/")
    html = rv.data.decode()
    assert "Sign in" in html
    assert "Logout" not in html


# ---------------------------------------------------------------------------
# Invite codes
# ---------------------------------------------------------------------------

def test_invite_code_not_required_by_default(client):
    """When INVITE_CODES is empty, signup is open."""
    import web.auth as auth_mod
    assert not auth_mod.invite_required()
    rv = client.post("/auth/send-link", data={"email": "open@example.com"})
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "/auth/verify/" in html


def test_invite_code_required_blocks_new_user(client, monkeypatch):
    """When invite codes are set, new users must provide one."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"disco-penguin-7f3a", "turbo-walrus-a1b2"})
    rv = client.post("/auth/send-link", data={"email": "blocked@example.com"})
    assert rv.status_code == 403
    html = rv.data.decode()
    assert "invite code" in html.lower()


def test_invite_code_required_bad_code(client, monkeypatch):
    """Wrong invite code is rejected."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"disco-penguin-7f3a"})
    rv = client.post("/auth/send-link", data={
        "email": "wrong@example.com",
        "invite_code": "bad-code-0000",
    })
    assert rv.status_code == 403


def test_invite_code_required_valid_code(client, monkeypatch):
    """Valid invite code allows new user creation."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"disco-penguin-7f3a"})
    rv = client.post("/auth/send-link", data={
        "email": "invited@example.com",
        "invite_code": "disco-penguin-7f3a",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "/auth/verify/" in html
    # Check user was created with the invite code stored
    user = auth_mod.get_user_by_email("invited@example.com")
    assert user is not None
    assert user["invite_code"] == "disco-penguin-7f3a"


def test_existing_user_skips_invite_code(client, monkeypatch):
    """Existing users can log in without an invite code even when required."""
    import web.auth as auth_mod
    # Create user first (before invite codes are enabled)
    auth_mod.create_user("existing@example.com")
    # Now enable invite codes
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"disco-penguin-7f3a"})
    rv = client.post("/auth/send-link", data={"email": "existing@example.com"})
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "/auth/verify/" in html


def test_login_page_shows_invite_field_when_required(client, monkeypatch):
    """Login page shows invite code field when codes are configured."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"some-code-1234"})
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert 'name="invite_code"' in html
    assert "invite code" in html.lower()


def test_login_page_hides_invite_field_when_open(client):
    """Login page hides invite code field when signup is open."""
    import web.auth as auth_mod
    assert not auth_mod.invite_required()
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert 'name="invite_code"' not in html


def test_validate_invite_code_function(monkeypatch):
    """Direct test of validate_invite_code helper."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"turbo-walrus-a1b2", "mega-sloth-c3d4"})
    assert auth_mod.validate_invite_code("turbo-walrus-a1b2") is True
    assert auth_mod.validate_invite_code("mega-sloth-c3d4") is True
    assert auth_mod.validate_invite_code("wrong-code-0000") is False
    assert auth_mod.validate_invite_code("") is False
    assert auth_mod.validate_invite_code("  turbo-walrus-a1b2  ") is True  # strips whitespace


def test_validate_invite_code_open_signup(monkeypatch):
    """When no codes configured, any code (or empty) is accepted."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", set())
    assert auth_mod.validate_invite_code("anything") is True
    assert auth_mod.validate_invite_code("") is True


# ---------------------------------------------------------------------------
# Admin: send invite
# ---------------------------------------------------------------------------

def test_send_invite_as_admin(client, monkeypatch):
    """Admin can send an invite email (dev mode logs it)."""
    import web.auth as auth_mod
    admin = _make_admin("admin-invite@test.com", monkeypatch)
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"team-test-code-1234"})

    from web.auth import create_magic_token
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)

    rv = client.post("/admin/send-invite", data={
        "to_email": "friend@example.com",
        "invite_code": "team-test-code-1234",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "friend@example.com" in html
    assert "team-test-code-1234" in html


def test_send_invite_non_admin_forbidden(client, monkeypatch):
    """Non-admin users cannot send invites."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"some-code-5678"})

    _login_user(client, "regular@test.com")
    rv = client.post("/admin/send-invite", data={
        "to_email": "someone@example.com",
        "invite_code": "some-code-5678",
    })
    assert rv.status_code == 403


def test_send_invite_bad_code_rejected(client, monkeypatch):
    """Admin cannot send an invalid invite code."""
    import web.auth as auth_mod
    admin = _make_admin("admin-bad@test.com", monkeypatch)
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"real-code-abcd"})

    from web.auth import create_magic_token
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)

    rv = client.post("/admin/send-invite", data={
        "to_email": "friend@example.com",
        "invite_code": "fake-code-0000",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "invalid" in html.lower() or "error" in html.lower()


def test_send_invite_bad_email_rejected(client, monkeypatch):
    """Admin cannot send to an invalid email."""
    import web.auth as auth_mod
    admin = _make_admin("admin-email@test.com", monkeypatch)
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"real-code-efgh"})

    from web.auth import create_magic_token
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)

    rv = client.post("/admin/send-invite", data={
        "to_email": "notanemail",
        "invite_code": "real-code-efgh",
    })
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "invalid" in html.lower() or "error" in html.lower()


def test_account_shows_invite_codes_for_admin(client, monkeypatch):
    """Admin account page shows invite code dropdown."""
    import web.auth as auth_mod
    admin = _make_admin("admin-codes@test.com", monkeypatch)
    monkeypatch.setattr(auth_mod, "INVITE_CODES", {"team-abc-1234", "friends-xyz-5678"})

    from web.auth import create_magic_token
    token = create_magic_token(admin["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)

    rv = client.get("/account")
    html = rv.data.decode()
    assert "Send Invite" in html
    assert "team-abc-1234" in html
    assert "friends-xyz-5678" in html
