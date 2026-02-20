"""Phase D1: Close Project — unit + integration tests.

Covers:
- is_archived column auto-migrated (DuckDB)
- close_project() / reopen_project() functions
- get_user_jobs() filters archived by default; include_archived shows them
- POST /api/plan-jobs/<id>/close and /reopen return 200
- POST /api/plan-jobs/bulk-close returns 200
- cleanup_old_jobs() skips version_group members where any job is < 30d old
"""

import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── DuckDB backend fixture ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with fresh temp DB for each test."""
    db_path = str(tmp_path / "test_d1.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod

    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    # Initialize schema (creates plan_analysis_jobs + is_archived column)
    import web.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


# ── helpers ───────────────────────────────────────────────────────


def _make_job(user_id: int = 1, filename: str = "plans.pdf") -> str:
    """Create a minimal plan_analysis_job and return its job_id."""
    from web.plan_jobs import create_job

    return create_job(
        user_id=user_id,
        filename=filename,
        file_size_mb=1.0,
    )


def _make_job_aged(user_id: int, days_ago: int, version_group: str | None = None) -> str:
    """Create a job and back-date its created_at for cleanup tests."""
    from src.db import execute_write, BACKEND

    job_id = _make_job(user_id=user_id)

    if BACKEND == "duckdb":
        ts = f"CURRENT_TIMESTAMP - INTERVAL '{days_ago} days'"
        if version_group is not None:
            # version_group column added by D2; skip silently if absent
            try:
                execute_write(
                    f"UPDATE plan_analysis_jobs SET created_at = {ts}, "
                    f"version_group = %s WHERE job_id = %s",
                    (version_group, job_id),
                )
            except Exception:
                execute_write(
                    f"UPDATE plan_analysis_jobs SET created_at = {ts} WHERE job_id = %s",
                    (job_id,),
                )
        else:
            execute_write(
                f"UPDATE plan_analysis_jobs SET created_at = {ts} WHERE job_id = %s",
                (job_id,),
            )
    return job_id


# ── migration: is_archived column ────────────────────────────────


def test_is_archived_column_exists():
    """is_archived column should exist after schema init."""
    from src.db import query

    # DuckDB exposes column metadata via duckdb_columns()
    rows = query(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE table_name = 'plan_analysis_jobs' AND column_name = 'is_archived'"
    )
    assert rows, "is_archived column is missing from plan_analysis_jobs"


def test_is_archived_defaults_false():
    """Newly created jobs have is_archived=FALSE."""
    from src.db import query_one

    job_id = _make_job()
    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row is not None
    assert row[0] is False


# ── close_project / reopen_project ───────────────────────────────


def test_close_project_sets_archived():
    """close_project() sets is_archived=TRUE for given job_ids."""
    from web.plan_jobs import close_project
    from src.db import query_one

    job_id = _make_job(user_id=42)
    count = close_project([job_id], user_id=42)

    assert count == len([job_id])
    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row[0] is True


def test_close_project_idempotent():
    """Closing an already-closed project is a no-op (no error, still archived)."""
    from web.plan_jobs import close_project
    from src.db import query_one

    job_id = _make_job(user_id=42)
    close_project([job_id], user_id=42)
    close_project([job_id], user_id=42)  # second call — should not raise

    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row[0] is True


def test_reopen_project_clears_archived():
    """reopen_project() sets is_archived=FALSE."""
    from web.plan_jobs import close_project, reopen_project
    from src.db import query_one

    job_id = _make_job(user_id=99)
    close_project([job_id], user_id=99)
    reopen_project([job_id], user_id=99)

    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row[0] is False


def test_close_project_respects_ownership():
    """close_project() must not archive jobs belonging to another user."""
    from web.plan_jobs import close_project
    from src.db import query_one

    job_id = _make_job(user_id=1)
    close_project([job_id], user_id=999)  # wrong user

    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row[0] is False  # still open


def test_close_project_empty_list():
    """close_project([]) returns 0 without error."""
    from web.plan_jobs import close_project

    result = close_project([], user_id=1)
    assert result == 0


# ── get_user_jobs() archive filter ────────────────────────────────


def test_get_user_jobs_excludes_archived_by_default():
    """Archived jobs are absent from default get_user_jobs() response."""
    from web.plan_jobs import close_project, get_user_jobs

    active_id = _make_job(user_id=7)
    closed_id = _make_job(user_id=7, filename="old.pdf")
    close_project([closed_id], user_id=7)

    jobs = get_user_jobs(user_id=7)
    ids = [j["job_id"] for j in jobs]

    assert active_id in ids
    assert closed_id not in ids


def test_get_user_jobs_include_archived_shows_all():
    """include_archived=True returns both open and closed jobs."""
    from web.plan_jobs import close_project, get_user_jobs

    active_id = _make_job(user_id=7)
    closed_id = _make_job(user_id=7, filename="old.pdf")
    close_project([closed_id], user_id=7)

    jobs = get_user_jobs(user_id=7, include_archived=True)
    ids = [j["job_id"] for j in jobs]

    assert active_id in ids
    assert closed_id in ids


def test_get_user_jobs_returns_is_archived_field():
    """Jobs returned by get_user_jobs() include the is_archived field."""
    from web.plan_jobs import close_project, get_user_jobs

    job_id = _make_job(user_id=5)
    close_project([job_id], user_id=5)

    jobs = get_user_jobs(user_id=5, include_archived=True)
    job = next(j for j in jobs if j["job_id"] == job_id)
    assert "is_archived" in job
    assert job["is_archived"] is True


# ── cleanup_old_jobs() ─────────────────────────────────────────────


def test_cleanup_old_jobs_deletes_ancient_jobs():
    """Jobs older than N days are deleted."""
    from web.plan_jobs import cleanup_old_jobs

    old_id = _make_job_aged(user_id=1, days_ago=35)
    deleted = cleanup_old_jobs(days=30)

    assert deleted >= 1

    from src.db import query_one

    row = query_one(
        "SELECT job_id FROM plan_analysis_jobs WHERE job_id = %s", (old_id,)
    )
    assert row is None


def test_cleanup_old_jobs_preserves_recent_jobs():
    """Jobs within the threshold are not deleted."""
    from web.plan_jobs import cleanup_old_jobs

    recent_id = _make_job_aged(user_id=1, days_ago=5)
    cleanup_old_jobs(days=30)

    from src.db import query_one

    row = query_one(
        "SELECT job_id FROM plan_analysis_jobs WHERE job_id = %s", (recent_id,)
    )
    assert row is not None


def test_cleanup_old_jobs_skips_version_group_with_recent_member():
    """cleanup_old_jobs() skips the old job when its version_group has a recent member."""
    from web.plan_jobs import cleanup_old_jobs
    from src.db import execute_write, query_one

    # Add version_group column if it doesn't exist yet (pre-D2)
    try:
        execute_write("ALTER TABLE plan_analysis_jobs ADD COLUMN version_group TEXT")
    except Exception:
        pass  # already exists

    old_id = _make_job_aged(user_id=1, days_ago=35, version_group="grp-abc")
    _make_job_aged(user_id=1, days_ago=5, version_group="grp-abc")  # recent sibling

    deleted = cleanup_old_jobs(days=30)

    # Old job should survive because its group has a recent member
    row = query_one(
        "SELECT job_id FROM plan_analysis_jobs WHERE job_id = %s", (old_id,)
    )
    assert row is not None, "Old job in a protected version_group was incorrectly deleted"
    assert deleted == 0


def test_cleanup_old_jobs_deletes_orphan_old_group():
    """Entire version_group older than threshold is deleted (no recent member)."""
    from web.plan_jobs import cleanup_old_jobs
    from src.db import execute_write, query_one

    try:
        execute_write("ALTER TABLE plan_analysis_jobs ADD COLUMN version_group TEXT")
    except Exception:
        pass

    old_id1 = _make_job_aged(user_id=1, days_ago=40, version_group="grp-old")
    old_id2 = _make_job_aged(user_id=1, days_ago=35, version_group="grp-old")

    deleted = cleanup_old_jobs(days=30)

    assert deleted >= 2
    for jid in [old_id1, old_id2]:
        row = query_one(
            "SELECT job_id FROM plan_analysis_jobs WHERE job_id = %s", (jid,)
        )
        assert row is None


# ── HTTP endpoints ────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch):
    """Flask test client with rate limiting disabled, logged-in user injected."""
    from web.app import app as flask_app, _rate_buckets

    flask_app.config["TESTING"] = True
    _rate_buckets.clear()

    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = 1
        yield c

    _rate_buckets.clear()


def test_close_endpoint_returns_200(client):
    """POST /api/plan-jobs/<id>/close returns 200 with closed:true."""
    job_id = _make_job(user_id=1)
    resp = client.post(f"/api/plan-jobs/{job_id}/close")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["closed"] is True


def test_reopen_endpoint_returns_200(client):
    """POST /api/plan-jobs/<id>/reopen returns 200 with reopened:true."""
    from web.plan_jobs import close_project

    job_id = _make_job(user_id=1)
    close_project([job_id], user_id=1)

    resp = client.post(f"/api/plan-jobs/{job_id}/reopen")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reopened"] is True


def test_close_then_reopen_roundtrip(client):
    """Closing then reopening via HTTP leaves job unarchived."""
    from src.db import query_one

    job_id = _make_job(user_id=1)
    client.post(f"/api/plan-jobs/{job_id}/close")
    client.post(f"/api/plan-jobs/{job_id}/reopen")

    row = query_one(
        "SELECT is_archived FROM plan_analysis_jobs WHERE job_id = %s", (job_id,)
    )
    assert row[0] is False


def test_bulk_close_endpoint_returns_200(client):
    """POST /api/plan-jobs/bulk-close returns 200 with closed count."""
    job_id1 = _make_job(user_id=1, filename="a.pdf")
    job_id2 = _make_job(user_id=1, filename="b.pdf")

    resp = client.post(
        "/api/plan-jobs/bulk-close",
        json={"job_ids": [job_id1, job_id2]},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["closed"] == 2


def test_bulk_close_endpoint_missing_ids(client):
    """POST /api/plan-jobs/bulk-close with no job_ids returns 400."""
    resp = client.post("/api/plan-jobs/bulk-close", json={})
    assert resp.status_code == 400


def test_endpoints_require_auth():
    """Close/reopen endpoints return 401 when not logged in."""
    from web.app import app as flask_app, _rate_buckets

    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    job_id = _make_job(user_id=1)

    with flask_app.test_client() as c:
        assert c.post(f"/api/plan-jobs/{job_id}/close").status_code == 401
        assert c.post(f"/api/plan-jobs/{job_id}/reopen").status_code == 401
        assert (
            c.post("/api/plan-jobs/bulk-close", json={"job_ids": [job_id]}).status_code
            == 401
        )
