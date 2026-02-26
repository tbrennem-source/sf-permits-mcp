"""Tests for Sprint 61B: Team Seed — projects + project_members + auto-create + auto-join.

Coverage:
  - Schema: projects and project_members tables created by init_user_schema
  - _create_project: creates project + owner membership
  - _create_project: returns None when address/block/lot all null
  - _get_or_create_project: dedup on block+lot
  - _get_or_create_project: adds existing user as member
  - _get_or_create_project: creates new project when no parcel match
  - _get_or_create_project: returns None when no address/parcel
  - _auto_join_project: joins project on signup via shared analysis
  - _auto_join_project: returns None when analysis has no project_id
  - _auto_join_project: idempotent (no duplicate members)
  - GET /projects returns 200 for logged-in user
  - GET /projects redirects to login when not logged in
  - GET /projects shows empty state when user has no projects
  - GET /projects shows project cards for user's projects
  - GET /project/<id> returns 200 for project member
  - GET /project/<id> returns 403 for non-member
  - GET /project/<id> returns 404 for missing project
  - POST /project/<id>/join returns ok=True for logged-in user
  - POST /project/<id>/join is idempotent
  - POST /project/<id>/join returns 401 when not logged in
  - POST /project/<id>/join returns 404 for missing project
  - POST /project/<id>/invite returns 403 for non-owner
  - POST /project/<id>/invite returns 400 for invalid email
  - analysis_shared page: join banner visible for non-member
  - analysis_shared page: no join banner when no project_id
  - analysis_shared page: member link shown for project member
  - analysis_sessions: project_id column persisted on /analyze save
  - nav: Projects link present in nav for logged-in users
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with a temp database for test isolation."""
    db_path = str(tmp_path / "test_61b.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()
    # Reset projects Blueprint table flag so each test gets fresh DDL
    import web.projects as proj_mod
    monkeypatch.setattr(proj_mod, "_TABLES_INITIALIZED", False)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="user@test.com"):
    """Create user and log in via magic token. Returns user dict."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _get_conn():
    from src.db import get_connection
    return get_connection()


def _insert_analysis(user_id=None, address="456 Valencia St", block=None, lot=None, project_id=None):
    """Insert an analysis_sessions row. Returns session_id."""
    from src.db import get_connection
    sess_id = str(uuid.uuid4())
    results = json.dumps({"predict": "## Permits needed"})
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO analysis_sessions "
            "(id, user_id, project_description, address, results_json, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [sess_id, user_id, "Kitchen remodel", address, results, project_id],
        )
    finally:
        conn.close()
    return sess_id


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_projects_table_exists(self):
        conn = _get_conn()
        try:
            result = conn.execute("SELECT COUNT(*) FROM projects").fetchone()
            assert result[0] == 0
        finally:
            conn.close()

    def test_project_members_table_exists(self):
        conn = _get_conn()
        try:
            result = conn.execute("SELECT COUNT(*) FROM project_members").fetchone()
            assert result[0] == 0
        finally:
            conn.close()

    def test_analysis_sessions_has_project_id_column(self):
        """analysis_sessions must have project_id column after schema init."""
        conn = _get_conn()
        try:
            conn.execute("INSERT INTO analysis_sessions (id, project_description, results_json, project_id) VALUES ('x1', 'test', '{}', NULL)")
            row = conn.execute("SELECT project_id FROM analysis_sessions WHERE id = 'x1'").fetchone()
            assert row[0] is None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# _create_project tests
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_creates_project_with_address(self):
        from web.projects import _create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("creator@test.com")
        pid = _create_project("123 Main St", "3512", "001", "Mission", user["user_id"])
        assert pid is not None
        conn = _get_conn()
        try:
            row = conn.execute("SELECT id, address, block, lot FROM projects WHERE id = ?", [pid]).fetchone()
            assert row is not None
            assert row[1] == "123 Main St"
            assert row[2] == "3512"
            assert row[3] == "001"
        finally:
            conn.close()

    def test_creates_owner_membership(self):
        from web.projects import _create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("ownertest@test.com")
        pid = _create_project("789 Market St", None, None, None, user["user_id"])
        assert pid is not None
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                [pid, user["user_id"]],
            ).fetchone()
            assert row is not None
            assert row[0] == "owner"
        finally:
            conn.close()

    def test_returns_none_when_no_address_or_parcel(self):
        from web.projects import _create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("empty@test.com")
        pid = _create_project(None, None, None, None, user["user_id"])
        assert pid is None


# ---------------------------------------------------------------------------
# _get_or_create_project tests
# ---------------------------------------------------------------------------

class TestGetOrCreateProject:
    def test_creates_new_project_when_no_match(self):
        from web.projects import _get_or_create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("new@test.com")
        pid = _get_or_create_project("100 First St", "1111", "002", "SoMa", user["user_id"])
        assert pid is not None
        conn = _get_conn()
        try:
            row = conn.execute("SELECT id FROM projects WHERE id = ?", [pid]).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_deduplicates_by_block_lot(self):
        from web.projects import _get_or_create_project
        from web.auth import get_or_create_user
        user1 = get_or_create_user("u1@test.com")
        user2 = get_or_create_user("u2@test.com")
        pid1 = _get_or_create_project("200 Second Ave", "2222", "003", "Castro", user1["user_id"])
        pid2 = _get_or_create_project("200 Second Ave", "2222", "003", "Castro", user2["user_id"])
        assert pid1 == pid2  # same project returned for same parcel

    def test_adds_second_user_as_member_on_dedup(self):
        from web.projects import _get_or_create_project
        from web.auth import get_or_create_user
        user1 = get_or_create_user("owner2@test.com")
        user2 = get_or_create_user("member2@test.com")
        pid = _get_or_create_project("300 Third Blvd", "3333", "004", "Noe Valley", user1["user_id"])
        _get_or_create_project("300 Third Blvd", "3333", "004", "Noe Valley", user2["user_id"])
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT user_id FROM project_members WHERE project_id = ?", [pid]
            ).fetchall()
            user_ids = {r[0] for r in rows}
            assert user1["user_id"] in user_ids
            assert user2["user_id"] in user_ids
        finally:
            conn.close()

    def test_returns_none_when_no_address_or_parcel(self):
        from web.projects import _get_or_create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("nobody@test.com")
        pid = _get_or_create_project(None, None, None, None, user["user_id"])
        assert pid is None

    def test_no_dedup_without_both_block_and_lot(self):
        """Without both block and lot, creates a new project instead of deduplicating."""
        from web.projects import _get_or_create_project
        from web.auth import get_or_create_user
        user = get_or_create_user("partial@test.com")
        pid1 = _get_or_create_project("400 Fourth", "4444", None, "Mission", user["user_id"])
        pid2 = _get_or_create_project("400 Fourth", "4444", None, "Mission", user["user_id"])
        # Without lot, dedup doesn't fire — two separate projects
        assert pid1 != pid2


# ---------------------------------------------------------------------------
# _auto_join_project tests
# ---------------------------------------------------------------------------

class TestAutoJoinProject:
    def test_joins_project_on_shared_link_signup(self):
        from web.projects import _create_project, _auto_join_project
        from web.auth import get_or_create_user
        owner = get_or_create_user("projowner@test.com")
        new_user = get_or_create_user("newcomer@test.com")
        pid = _create_project("500 Fifth Ave", "5555", "005", "Haight", owner["user_id"])
        sess_id = _insert_analysis(user_id=owner["user_id"], project_id=pid)
        result = _auto_join_project(new_user["user_id"], sess_id)
        assert result == pid
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                [pid, new_user["user_id"]],
            ).fetchone()
            assert row is not None
        finally:
            conn.close()

    def test_returns_none_when_analysis_has_no_project(self):
        from web.projects import _auto_join_project
        from web.auth import get_or_create_user
        user = get_or_create_user("noproject@test.com")
        sess_id = _insert_analysis(user_id=user["user_id"], project_id=None)
        result = _auto_join_project(user["user_id"], sess_id)
        assert result is None

    def test_returns_none_for_nonexistent_analysis(self):
        from web.projects import _auto_join_project
        from web.auth import get_or_create_user
        user = get_or_create_user("ghost@test.com")
        result = _auto_join_project(user["user_id"], "nonexistent-id")
        assert result is None

    def test_idempotent_join(self):
        """Calling _auto_join_project twice does not create duplicate members."""
        from web.projects import _create_project, _auto_join_project
        from web.auth import get_or_create_user
        owner = get_or_create_user("idempotent_owner@test.com")
        joiner = get_or_create_user("joiner@test.com")
        pid = _create_project("600 Sixth", "6666", "006", "Tenderloin", owner["user_id"])
        sess_id = _insert_analysis(user_id=owner["user_id"], project_id=pid)
        _auto_join_project(joiner["user_id"], sess_id)
        _auto_join_project(joiner["user_id"], sess_id)
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM project_members WHERE project_id = ? AND user_id = ?",
                [pid, joiner["user_id"]],
            ).fetchone()
            assert rows[0] == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# GET /projects route tests
# ---------------------------------------------------------------------------

class TestProjectsList:
    def test_redirects_to_login_when_not_logged_in(self, client):
        resp = client.get("/projects")
        assert resp.status_code in (301, 302)

    def test_returns_200_for_logged_in_user(self, client):
        _login(client, "listuser@test.com")
        resp = client.get("/projects")
        assert resp.status_code == 200

    def test_shows_empty_state_when_no_projects(self, client):
        _login(client, "emptyprojects@test.com")
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert b"No projects yet" in resp.data

    def test_shows_project_cards(self, client):
        user = _login(client, "withprojects@test.com")
        from web.projects import _create_project
        _create_project("123 Test St", "9999", "099", "Mission", user["user_id"])
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert b"123 Test St" in resp.data


# ---------------------------------------------------------------------------
# GET /project/<id> route tests
# ---------------------------------------------------------------------------

class TestProjectDetail:
    def test_returns_200_for_member(self, client):
        user = _login(client, "detailmember@test.com")
        from web.projects import _create_project
        pid = _create_project("detail addr", "7777", "007", "Sunset", user["user_id"])
        resp = client.get(f"/project/{pid}")
        assert resp.status_code == 200

    def test_returns_404_for_missing_project(self, client):
        _login(client, "notfound@test.com")
        resp = client.get("/project/nonexistent-id-xyz")
        assert resp.status_code == 404

    def test_returns_403_for_non_member(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("projectowner@test.com")
        from web.projects import _create_project
        pid = _create_project("owner addr", "8888", "008", "Richmond", owner["user_id"])
        _login(client, "outsider@test.com")
        resp = client.get(f"/project/{pid}")
        assert resp.status_code == 403

    def test_shows_members_in_detail(self, client):
        user = _login(client, "showmembers@test.com")
        from web.projects import _create_project
        pid = _create_project("member addr", "1234", "010", "SoMa", user["user_id"])
        resp = client.get(f"/project/{pid}")
        assert resp.status_code == 200
        assert b"showmembers@test.com" in resp.data


# ---------------------------------------------------------------------------
# POST /project/<id>/join route tests
# ---------------------------------------------------------------------------

class TestProjectJoin:
    def test_join_returns_ok_true(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("joinowner@test.com")
        from web.projects import _create_project
        pid = _create_project("join addr", "2345", "011", "Nob Hill", owner["user_id"])
        _login(client, "joiner2@test.com")
        resp = client.post(f"/project/{pid}/join", content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True

    def test_join_is_idempotent(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("idem_owner@test.com")
        from web.projects import _create_project
        pid = _create_project("idem addr", "3456", "012", "Hayes Valley", owner["user_id"])
        user = _login(client, "idem_joiner@test.com")
        client.post(f"/project/{pid}/join", content_type="application/json")
        resp = client.post(f"/project/{pid}/join", content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True

    def test_join_returns_401_when_not_logged_in(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("auth401owner@test.com")
        from web.projects import _create_project
        pid = _create_project("auth addr", "4567", "013", "Excelsior", owner["user_id"])
        resp = client.post(f"/project/{pid}/join", content_type="application/json")
        assert resp.status_code == 401

    def test_join_returns_404_for_missing_project(self, client):
        _login(client, "join404@test.com")
        resp = client.post("/project/does-not-exist/join", content_type="application/json")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /project/<id>/invite route tests
# ---------------------------------------------------------------------------

class TestProjectInvite:
    def test_returns_403_for_non_owner(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("inviteowner@test.com")
        from web.projects import _create_project, _get_or_create_project
        pid = _create_project("invite addr", "5678", "014", "Pacific Heights", owner["user_id"])
        # Log in as a member (not owner)
        member = _login(client, "invitemember@test.com")
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'member')",
                [pid, member["user_id"]],
            )
        finally:
            conn.close()
        resp = client.post(
            f"/project/{pid}/invite",
            json={"email": "someone@test.com"},
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_returns_400_for_invalid_email(self, client):
        user = _login(client, "inviteowner2@test.com")
        from web.projects import _create_project
        pid = _create_project("invite2 addr", "6789", "015", "Chinatown", user["user_id"])
        resp = client.post(
            f"/project/{pid}/invite",
            json={"email": "not-an-email"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_returns_401_when_not_logged_in(self, client):
        from web.auth import get_or_create_user
        owner = get_or_create_user("inv401owner@test.com")
        from web.projects import _create_project
        pid = _create_project("inv401 addr", "7890", "016", "Sunset", owner["user_id"])
        resp = client.post(
            f"/project/{pid}/invite",
            json={"email": "x@test.com"},
            content_type="application/json",
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# analysis_shared page: join button visibility
# ---------------------------------------------------------------------------

class TestAnalysisSharedJoinButton:
    def test_join_banner_visible_for_non_member(self, client):
        """Logged-in user who is NOT a project member sees Join banner."""
        from web.auth import get_or_create_user
        owner = get_or_create_user("shareowner@test.com")
        from web.projects import _create_project
        pid = _create_project("shared addr", "8901", "017", "Portola", owner["user_id"])
        sess_id = _insert_analysis(user_id=owner["user_id"], project_id=pid)
        _login(client, "nonmember@test.com")
        resp = client.get(f"/analysis/{sess_id}")
        assert resp.status_code == 200
        assert b"join-banner" in resp.data

    def test_no_join_banner_when_no_project(self, client):
        """Analysis with no project_id shows no join banner."""
        from web.auth import get_or_create_user
        owner = get_or_create_user("noprojowner@test.com")
        sess_id = _insert_analysis(user_id=owner["user_id"], project_id=None)
        _login(client, "viewer@test.com")
        resp = client.get(f"/analysis/{sess_id}")
        assert resp.status_code == 200
        assert b"join-banner" not in resp.data

    def test_member_link_shown_for_project_member(self, client):
        """Logged-in user who IS a project member sees 'View project' link."""
        user = _login(client, "alreadymember@test.com")
        from web.projects import _create_project
        pid = _create_project("member addr", "9012", "018", "Bayview", user["user_id"])
        sess_id = _insert_analysis(user_id=user["user_id"], project_id=pid)
        resp = client.get(f"/analysis/{sess_id}")
        assert resp.status_code == 200
        assert b"View project" in resp.data


# ---------------------------------------------------------------------------
# Nav: Projects link
# ---------------------------------------------------------------------------

class TestNavProjectsLink:
    def test_projects_link_in_nav_for_logged_in_user(self, client):
        """Projects link appears in nav for authenticated users."""
        _login(client, "navtest@test.com")
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert b'href="/projects"' in resp.data
