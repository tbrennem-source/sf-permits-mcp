"""Phase E2: Comparison Page — unit + integration tests.

Covers:
- comparison_json column exists in DuckDB after schema init
- match_comments(): token overlap, stamp threshold=1, position tiebreak
- match_comments(): new (no v1 match), resolved (no v2 match), unchanged
- compute_sheet_diff(): added / removed / unchanged sets
- compute_epr_diff(): only returns changed checks
- compute_comparison(): full structure with all required keys
- get_cached_comparison(): returns None when absent, stale when reprocessed
- store_comparison() / get_cached_comparison() round-trip
- GET /account/analyses/compare returns 200 with valid jobs
- GET /account/analyses/compare returns 403 when jobs belong to another user
- GET /account/analyses/compare returns 400 when jobs are not completed
- Cache invalidation: reprocessed v2 yields fresh comparison
- Cross-user access → 403
"""

import json
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── DuckDB backend fixture ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with fresh temp DB for each test."""
    db_path = str(tmp_path / "test_e2.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod

    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    import web.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


# ── helpers ────────────────────────────────────────────────────────

def _make_job(user_id=1, filename="plans.pdf", pdf_data=None):
    from web.plan_jobs import create_job
    return create_job(user_id=user_id, filename=filename, file_size_mb=1.0, pdf_data=pdf_data)


def _complete_job(job_id, structural_fingerprint=None, session_id=None):
    from web.plan_jobs import update_job_status
    kwargs = {"completed_at": datetime.now(timezone.utc)}
    if structural_fingerprint is not None:
        kwargs["structural_fingerprint"] = structural_fingerprint
    if session_id is not None:
        kwargs["session_id"] = session_id
    update_job_status(job_id, "completed", **kwargs)


_FP_A = [
    {"page_number": 1, "sheet_number": "A1.1"},
    {"page_number": 2, "sheet_number": "A2.0"},
    {"page_number": 3, "sheet_number": "S3.0"},
]
_FP_B = [
    {"page_number": 1, "sheet_number": "A1.1"},
    {"page_number": 2, "sheet_number": "A2.0"},
    {"page_number": 4, "sheet_number": "S4.0"},  # new
]

_ANNS_V1 = [
    {"type": "epr_issue", "label": "Missing stamp on cover sheet", "x": 80, "y": 10, "importance": "high", "page_number": 1},
    {"type": "epr_issue", "label": "Verify occupancy group", "x": 50, "y": 50, "importance": "medium", "page_number": 2},
    {"type": "stamp",     "label": "Architect stamp missing", "x": 85, "y": 5, "importance": "high", "page_number": 1},
]
_ANNS_V2 = [
    # "Missing stamp on cover sheet" → still present but lower importance = resolved
    {"type": "epr_issue", "label": "Stamp on cover sheet present", "x": 80, "y": 10, "importance": "low", "page_number": 1},
    # New issue not in v1
    {"type": "epr_issue", "label": "Add fire exit signage CBC 1013", "x": 30, "y": 70, "importance": "high", "page_number": 3},
]


# ── migration: comparison_json column ─────────────────────────────

def test_comparison_json_column_exists():
    """comparison_json column should exist after schema init."""
    from src.db import query
    rows = query(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE table_name = 'plan_analysis_jobs' AND column_name = 'comparison_json'"
    )
    assert rows, "comparison_json column missing from plan_analysis_jobs"


# ── match_comments() unit tests ────────────────────────────────────

def test_match_comments_resolved_when_lower_importance():
    """Annotation matched with 2 shared tokens and v2 importance is lower → status='resolved'."""
    from web.plan_compare import match_comments
    # "OCCUPANCY GROUP" shared tokens: OCCUPANCY, GROUP (= 2) → matches
    v1 = [{"type": "epr_issue", "label": "Verify occupancy group label", "x": 50, "y": 50, "importance": "high", "page_number": 1}]
    v2 = [{"type": "epr_issue", "label": "Confirm occupancy group",      "x": 50, "y": 50, "importance": "low",  "page_number": 1}]
    results = match_comments(v1, v2)
    # Exactly one result: matched pair (resolved because importance dropped)
    matched = [r for r in results if r["v1_label"] is not None and r["v2_label"] is not None]
    assert len(matched) == 1
    assert matched[0]["status"] == "resolved"


def test_match_comments_unchanged_same_importance():
    """Annotation matched and same importance → status='unchanged'."""
    from web.plan_compare import match_comments
    v1 = [{"type": "epr_issue", "label": "Verify occupancy group", "x": 50, "y": 50, "importance": "medium", "page_number": 2}]
    v2 = [{"type": "epr_issue", "label": "Confirm occupancy group designation", "x": 50, "y": 50, "importance": "medium", "page_number": 2}]
    results = match_comments(v1, v2)
    # "OCCUPANCY" and "GROUP" are shared tokens — should match
    assert len(results) == 1
    assert results[0]["status"] == "unchanged"


def test_match_comments_new_when_no_v1_match():
    """v2 annotation with no v1 counterpart → status='new'."""
    from web.plan_compare import match_comments
    v1 = []
    v2 = [{"type": "epr_issue", "label": "Add fire exit signage", "x": 30, "y": 70, "importance": "high", "page_number": 3}]
    results = match_comments(v1, v2)
    assert len(results) == 1
    assert results[0]["status"] == "new"
    assert results[0]["v1_label"] is None
    assert results[0]["v2_label"] == "Add fire exit signage"


def test_match_comments_resolved_when_absent_in_v2():
    """v1 annotation absent in v2 → status='resolved' (issue fixed)."""
    from web.plan_compare import match_comments
    v1 = [{"type": "epr_issue", "label": "Missing footer detail", "x": 10, "y": 90, "importance": "high", "page_number": 5}]
    v2 = []
    results = match_comments(v1, v2)
    assert len(results) == 1
    assert results[0]["status"] == "resolved"
    assert results[0]["v2_label"] is None


def test_match_comments_stamp_threshold_one():
    """stamp type uses threshold=1: a single shared token is sufficient."""
    from web.plan_compare import match_comments
    v1 = [{"type": "stamp", "label": "Architect stamp", "x": 85, "y": 5, "importance": "high", "page_number": 1}]
    # Only "STAMP" is shared → still matches because threshold=1 for stamp type
    v2 = [{"type": "stamp", "label": "Stamp present", "x": 85, "y": 5, "importance": "high", "page_number": 1}]
    results = match_comments(v1, v2)
    assert len(results) == 1
    assert results[0]["status"] in ("unchanged", "resolved")


def test_match_comments_type_bucketing():
    """Only annotations of the same type are compared (type-first bucketing)."""
    from web.plan_compare import match_comments
    v1 = [{"type": "epr_issue", "label": "Missing stamp", "x": 80, "y": 10, "importance": "high", "page_number": 1}]
    # Same words, but DIFFERENT type — should NOT match
    v2 = [{"type": "general_note", "label": "Missing stamp noted", "x": 80, "y": 10, "importance": "high", "page_number": 1}]
    results = match_comments(v1, v2)
    statuses = {r["status"] for r in results}
    # v1 has no v2 match (different type) → resolved
    # v2 has no v1 match (different type) → new
    assert "resolved" in statuses
    assert "new" in statuses


def test_match_comments_position_tiebreak():
    """When two v1 candidates pass token threshold, prefer nearest (x, y)."""
    from web.plan_compare import match_comments
    v1 = [
        {"type": "epr_issue", "label": "CBC 1006 occupancy load", "x": 20, "y": 20, "importance": "medium", "page_number": 1},
        {"type": "epr_issue", "label": "CBC 1006 occupancy load", "x": 80, "y": 80, "importance": "medium", "page_number": 2},
    ]
    # v2 annotation is near the first v1 (x=22, y=22)
    v2 = [{"type": "epr_issue", "label": "CBC 1006 occupancy load verify", "x": 22, "y": 22, "importance": "medium", "page_number": 1}]
    results = match_comments(v1, v2)
    # Should match with the near v1 (page_number=1), leaving page_number=2 unmatched
    matched = [r for r in results if r["v2_label"] is not None]
    assert len(matched) == 1
    assert matched[0]["page_number"] in (1, None)  # matched with page 1 candidate


# ── compute_sheet_diff() unit tests ───────────────────────────────

def test_sheet_diff_added():
    """Sheets in v2 but not v1 are 'added'."""
    from web.plan_compare import compute_sheet_diff
    v1_fp = [{"page_number": 1, "sheet_number": "A1.1"}]
    v2_fp = [{"page_number": 1, "sheet_number": "A1.1"}, {"page_number": 2, "sheet_number": "S2.0"}]
    diff = compute_sheet_diff(v1_fp, v2_fp)
    assert "S2.0" in diff["added"]
    assert "A1.1" in diff["unchanged"]
    assert diff["removed"] == []


def test_sheet_diff_removed():
    """Sheets in v1 but not v2 are 'removed'."""
    from web.plan_compare import compute_sheet_diff
    v1_fp = [{"page_number": 1, "sheet_number": "A1.1"}, {"page_number": 2, "sheet_number": "S2.0"}]
    v2_fp = [{"page_number": 1, "sheet_number": "A1.1"}]
    diff = compute_sheet_diff(v1_fp, v2_fp)
    assert "S2.0" in diff["removed"]
    assert "A1.1" in diff["unchanged"]
    assert diff["added"] == []


def test_sheet_diff_empty_fingerprints():
    """Both empty → all empty lists."""
    from web.plan_compare import compute_sheet_diff
    diff = compute_sheet_diff([], [])
    assert diff == {"added": [], "removed": [], "unchanged": []}


def test_sheet_diff_none_sheet_number_label():
    """Pages with sheet_number=None use 'p{page_number}' label."""
    from web.plan_compare import compute_sheet_diff
    v1_fp = [{"page_number": 5, "sheet_number": None}]
    v2_fp = [{"page_number": 5, "sheet_number": None}]
    diff = compute_sheet_diff(v1_fp, v2_fp)
    assert "p5" in diff["unchanged"]


# ── compute_epr_diff() unit tests ─────────────────────────────────

def test_epr_diff_returns_changes_only():
    """Only changed EPR check statuses are returned."""
    from web.plan_compare import compute_epr_diff
    v1_ext = [{"epr_checks": [{"check_id": "EPR-001", "status": "FAIL"}, {"check_id": "EPR-002", "status": "PASS"}]}]
    v2_ext = [{"epr_checks": [{"check_id": "EPR-001", "status": "PASS"}, {"check_id": "EPR-002", "status": "PASS"}]}]
    changes = compute_epr_diff(v1_ext, v2_ext)
    assert len(changes) == 1
    assert changes[0]["check_id"] == "EPR-001"
    assert changes[0]["v1_status"] == "FAIL"
    assert changes[0]["v2_status"] == "PASS"


def test_epr_diff_no_changes():
    """No changes → empty list."""
    from web.plan_compare import compute_epr_diff
    ext = [{"epr_checks": [{"check_id": "EPR-001", "status": "PASS"}]}]
    assert compute_epr_diff(ext, ext) == []


def test_epr_diff_empty_extractions():
    """Empty extractions → empty list."""
    from web.plan_compare import compute_epr_diff
    assert compute_epr_diff([], []) == []


# ── compute_comparison() integration ──────────────────────────────

def _make_job_dict(job_id, structural_fingerprint=None):
    return {
        "job_id": job_id,
        "user_id": 1,
        "filename": f"{job_id}.pdf",
        "completed_at": datetime.now(timezone.utc),
        "structural_fingerprint": json.dumps(structural_fingerprint) if structural_fingerprint else None,
        "pages_analyzed": 3,
        "property_address": "123 Main St",
        "permit_number": None,
    }

def _make_session_dict(page_extractions=None, page_annotations=None):
    return {
        "page_extractions": page_extractions or [],
        "page_annotations": page_annotations or [],
    }


def test_compute_comparison_required_keys():
    """compute_comparison() returns all required keys."""
    from web.plan_compare import compute_comparison
    job_a = _make_job_dict("a", _FP_A)
    job_b = _make_job_dict("b", _FP_B)
    sess_a = _make_session_dict(page_annotations=_ANNS_V1)
    sess_b = _make_session_dict(page_annotations=_ANNS_V2)

    result = compute_comparison(job_a, sess_a, job_b, sess_b)

    assert "computed_at" in result
    assert "job_a_id" in result
    assert "job_b_id" in result
    assert "comment_resolutions" in result
    assert "epr_changes" in result
    assert "sheet_diff" in result
    assert "summary" in result
    assert result["job_a_id"] == "a"
    assert result["job_b_id"] == "b"


def test_compute_comparison_summary_counts():
    """Summary counts are consistent with resolutions."""
    from web.plan_compare import compute_comparison
    job_a = _make_job_dict("a", _FP_A)
    job_b = _make_job_dict("b", _FP_B)
    sess_a = _make_session_dict(page_annotations=_ANNS_V1)
    sess_b = _make_session_dict(page_annotations=_ANNS_V2)

    result = compute_comparison(job_a, sess_a, job_b, sess_b)
    s = result["summary"]
    resolutions = result["comment_resolutions"]

    assert s["resolved"] == sum(1 for r in resolutions if r["status"] == "resolved")
    assert s["new"] == sum(1 for r in resolutions if r["status"] == "new")
    assert s["unchanged"] == sum(1 for r in resolutions if r["status"] == "unchanged")


def test_compute_comparison_sheet_diff_populated():
    """Sheet diff is computed from structural fingerprints."""
    from web.plan_compare import compute_comparison
    job_a = _make_job_dict("a", _FP_A)
    job_b = _make_job_dict("b", _FP_B)
    sess_a = _make_session_dict()
    sess_b = _make_session_dict()

    result = compute_comparison(job_a, sess_a, job_b, sess_b)
    sd = result["sheet_diff"]

    # S3.0 is in v1 but not v2 → removed
    assert "S3.0" in sd["removed"]
    # S4.0 is in v2 but not v1 → added
    assert "S4.0" in sd["added"]
    # A1.1, A2.0 are in both → unchanged
    assert "A1.1" in sd["unchanged"]
    assert "A2.0" in sd["unchanged"]


# ── Cache helpers ──────────────────────────────────────────────────

def test_get_cached_comparison_returns_none_when_absent():
    """get_cached_comparison returns None if no cache stored."""
    from web.plan_compare import get_cached_comparison
    job_id = _make_job()
    assert get_cached_comparison(job_id) is None


def test_store_and_retrieve_comparison():
    """store_comparison + get_cached_comparison round-trip."""
    from web.plan_compare import store_comparison, get_cached_comparison

    job_id = _make_job()
    _complete_job(job_id)

    payload = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "job_a_id": "x",
        "job_b_id": job_id,
        "comment_resolutions": [],
        "epr_changes": [],
        "sheet_diff": {"added": [], "removed": [], "unchanged": []},
        "summary": {"resolved": 0, "new": 0, "unchanged": 0, "sheets_added": 0, "sheets_removed": 0},
    }
    store_comparison(job_id, payload)

    cached = get_cached_comparison(job_id)
    assert cached is not None
    assert cached["job_a_id"] == "x"


def test_get_cached_comparison_stale_after_reprocess():
    """Cache is invalidated when job's completed_at is newer than computed_at."""
    from web.plan_compare import store_comparison, get_cached_comparison
    from src.db import execute_write

    job_id = _make_job()
    old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # Store a cache with old computed_at
    payload = {
        "computed_at": old_time.isoformat(),
        "job_a_id": "x",
        "job_b_id": job_id,
        "comment_resolutions": [],
        "epr_changes": [],
        "sheet_diff": {"added": [], "removed": [], "unchanged": []},
        "summary": {"resolved": 0, "new": 0, "unchanged": 0, "sheets_added": 0, "sheets_removed": 0},
    }
    store_comparison(job_id, payload)

    # Mark job completed AFTER the cache was built
    new_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    execute_write(
        "UPDATE plan_analysis_jobs SET status = 'completed', completed_at = %s WHERE job_id = %s",
        (new_time, job_id),
    )

    # Cache should be stale
    assert get_cached_comparison(job_id) is None


# ── HTTP endpoint tests ────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    """Flask test client with rate limiting disabled, user 1 logged in."""
    from web.app import app as flask_app, _rate_buckets
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = 1
        yield c
    _rate_buckets.clear()


def test_compare_route_200_with_valid_jobs(client):
    """GET /account/analyses/compare returns 200 for two completed same-user jobs."""
    from web.plan_images import create_session

    # Create both jobs and their sessions
    job_a_id = _make_job(user_id=1, filename="v1.pdf")
    sess_a_id = create_session(filename="v1.pdf", page_count=2,
                                page_extractions=[], page_images=[], user_id=1)
    _complete_job(job_a_id, structural_fingerprint=json.dumps(_FP_A), session_id=sess_a_id)

    job_b_id = _make_job(user_id=1, filename="v2.pdf")
    sess_b_id = create_session(filename="v2.pdf", page_count=2,
                                page_extractions=[], page_images=[], user_id=1)
    _complete_job(job_b_id, structural_fingerprint=json.dumps(_FP_B), session_id=sess_b_id)

    resp = client.get(f"/account/analyses/compare?a={job_a_id}&b={job_b_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Compare" in html


def test_compare_route_403_cross_user(client):
    """GET /account/analyses/compare returns 403 when a job belongs to another user."""
    job_a_id = _make_job(user_id=1, filename="v1.pdf")
    _complete_job(job_a_id)

    job_b_id = _make_job(user_id=99, filename="v2.pdf")  # different user
    _complete_job(job_b_id)

    resp = client.get(f"/account/analyses/compare?a={job_a_id}&b={job_b_id}")
    assert resp.status_code == 403


def test_compare_route_400_missing_params(client):
    """GET /account/analyses/compare returns 400 when a or b is missing."""
    job_id = _make_job(user_id=1)
    _complete_job(job_id)
    assert client.get(f"/account/analyses/compare?a={job_id}").status_code == 400
    assert client.get(f"/account/analyses/compare?b={job_id}").status_code == 400


def test_compare_route_400_job_not_completed(client):
    """GET /account/analyses/compare returns 400 when jobs are not completed."""
    job_a_id = _make_job(user_id=1, filename="v1.pdf")
    job_b_id = _make_job(user_id=1, filename="v2.pdf")
    # Neither is marked completed
    resp = client.get(f"/account/analyses/compare?a={job_a_id}&b={job_b_id}")
    assert resp.status_code == 400


def test_compare_route_redirect_when_not_logged_in():
    """GET /account/analyses/compare redirects to login when not authenticated."""
    from web.app import app as flask_app, _rate_buckets
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        resp = c.get("/account/analyses/compare?a=x&b=y")
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "").lower()
