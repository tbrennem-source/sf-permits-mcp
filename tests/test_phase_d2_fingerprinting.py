"""Phase D2: Document Fingerprinting — unit + integration tests.

Covers:
- pdf_hash, pdf_hash_failed, structural_fingerprint columns migrated (DuckDB)
- SHA-256 stored in DB when pdf_data supplied to create_job()
- No hash / no failure when pdf_data=None
- hollow session guard: extract_structural_fingerprint([]) == []
- compute_overlap_score() weighted pair matching
- fingerprints_match() at/below 60% threshold
- Same PDF uploaded twice → same pdf_hash
- find_matching_job() Layer 1 exact hash priority
- Structural overlap ≥60% → match returned; <60% → None
- Cross-user jobs NOT linked
- metadata_matches() permit_number / address / filename fallbacks
- update_job_status() stores structural_fingerprint as JSON
"""

import hashlib
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── DuckDB backend fixture ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with fresh temp DB for each test."""
    db_path = str(tmp_path / "test_d2.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod

    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    import web.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


# ── helpers ────────────────────────────────────────────────────────


_FAKE_PDF = b"%PDF-1.4 fake content for hashing"
_FAKE_PDF2 = b"%PDF-1.4 different content for another file"


def _make_job(
    user_id: int = 1,
    filename: str = "plans.pdf",
    pdf_data: bytes | None = None,
) -> str:
    """Create a minimal plan_analysis_job and return its job_id."""
    from web.plan_jobs import create_job

    return create_job(
        user_id=user_id,
        filename=filename,
        file_size_mb=1.0,
        pdf_data=pdf_data,
    )


def _complete_job(job_id: str, structural_fingerprint: str | None = None) -> None:
    """Mark a job as completed (optionally with a fingerprint)."""
    from web.plan_jobs import update_job_status
    from datetime import datetime, timezone

    kwargs = {}
    if structural_fingerprint is not None:
        kwargs["structural_fingerprint"] = structural_fingerprint

    update_job_status(
        job_id,
        "completed",
        completed_at=datetime.now(timezone.utc),
        **kwargs,
    )


# ── migration: D2 columns ──────────────────────────────────────────


def test_pdf_hash_column_exists():
    """pdf_hash column should exist after schema init."""
    from src.db import query

    rows = query(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE table_name = 'plan_analysis_jobs' AND column_name = 'pdf_hash'"
    )
    assert rows, "pdf_hash column is missing from plan_analysis_jobs"


def test_pdf_hash_failed_column_exists():
    """pdf_hash_failed column should exist after schema init."""
    from src.db import query

    rows = query(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE table_name = 'plan_analysis_jobs' AND column_name = 'pdf_hash_failed'"
    )
    assert rows, "pdf_hash_failed column is missing from plan_analysis_jobs"


def test_structural_fingerprint_column_exists():
    """structural_fingerprint column should exist after schema init."""
    from src.db import query

    rows = query(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE table_name = 'plan_analysis_jobs' AND column_name = 'structural_fingerprint'"
    )
    assert rows, "structural_fingerprint column is missing from plan_analysis_jobs"


# ── SHA-256 hash at upload ─────────────────────────────────────────


def test_create_job_stores_pdf_hash():
    """create_job() with pdf_data stores sha256 hex in pdf_hash."""
    from src.db import query_one

    job_id = _make_job(pdf_data=_FAKE_PDF)
    row = query_one(
        "SELECT pdf_hash, pdf_hash_failed FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    assert row is not None
    expected = hashlib.sha256(_FAKE_PDF).hexdigest()
    assert row[0] == expected, f"Expected hash {expected!r}, got {row[0]!r}"
    assert row[1] is False  # pdf_hash_failed should be False


def test_create_job_no_pdf_data_no_hash():
    """create_job() without pdf_data stores NULL pdf_hash and pdf_hash_failed=FALSE."""
    from src.db import query_one

    job_id = _make_job(pdf_data=None)
    row = query_one(
        "SELECT pdf_hash, pdf_hash_failed FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    assert row is not None
    assert row[0] is None      # no hash
    assert row[1] is False     # not a failure — just no data


def test_same_pdf_produces_same_hash():
    """Two jobs with identical PDF bytes should have the same pdf_hash."""
    from src.db import query_one

    job_id_1 = _make_job(pdf_data=_FAKE_PDF, filename="v1.pdf")
    job_id_2 = _make_job(pdf_data=_FAKE_PDF, filename="v2.pdf")

    row1 = query_one("SELECT pdf_hash FROM plan_analysis_jobs WHERE job_id = %s", (job_id_1,))
    row2 = query_one("SELECT pdf_hash FROM plan_analysis_jobs WHERE job_id = %s", (job_id_2,))

    assert row1[0] is not None
    assert row1[0] == row2[0], "Same PDF bytes must produce identical pdf_hash"


def test_different_pdf_produces_different_hash():
    """Two jobs with different PDF bytes should have different pdf_hashes."""
    from src.db import query_one

    job_id_1 = _make_job(pdf_data=_FAKE_PDF, filename="a.pdf")
    job_id_2 = _make_job(pdf_data=_FAKE_PDF2, filename="b.pdf")

    row1 = query_one("SELECT pdf_hash FROM plan_analysis_jobs WHERE job_id = %s", (job_id_1,))
    row2 = query_one("SELECT pdf_hash FROM plan_analysis_jobs WHERE job_id = %s", (job_id_2,))

    assert row1[0] != row2[0], "Different PDF bytes must produce different pdf_hashes"


# ── compute_pdf_hash() unit tests ─────────────────────────────────


def test_compute_pdf_hash_returns_hex():
    """compute_pdf_hash returns a valid 64-char hex string."""
    from web.plan_fingerprint import compute_pdf_hash

    h = compute_pdf_hash(_FAKE_PDF)
    assert h is not None
    assert len(h) == 64
    assert h == hashlib.sha256(_FAKE_PDF).hexdigest()


def test_compute_pdf_hash_none_on_failure(monkeypatch):
    """compute_pdf_hash returns None when hashing raises (silent skip)."""
    from web import plan_fingerprint

    monkeypatch.setattr(plan_fingerprint.hashlib, "sha256", lambda b: (_ for _ in ()).throw(RuntimeError("injected")))
    result = plan_fingerprint.compute_pdf_hash(b"data")
    assert result is None


# ── extract_structural_fingerprint() unit tests ───────────────────


def test_extract_fingerprint_empty_returns_empty():
    """extract_structural_fingerprint([]) returns [] (hollow session guard)."""
    from web.plan_fingerprint import extract_structural_fingerprint

    assert extract_structural_fingerprint([]) == []


def test_extract_fingerprint_basic():
    """Extracts page_number and sheet_number from page extractions."""
    from web.plan_fingerprint import extract_structural_fingerprint

    extractions = [
        {"page_number": 1, "sheet_number": "A1.1"},
        {"page_number": 2, "sheet_number": "A2.0"},
        {"page_number": 3},  # no sheet_number
    ]
    fp = extract_structural_fingerprint(extractions)
    assert len(fp) == 3
    assert fp[0] == {"page_number": 1, "sheet_number": "A1.1"}
    assert fp[1] == {"page_number": 2, "sheet_number": "A2.0"}
    assert fp[2] == {"page_number": 3, "sheet_number": None}


def test_extract_fingerprint_sorted_by_page():
    """Output is sorted by page_number."""
    from web.plan_fingerprint import extract_structural_fingerprint

    extractions = [
        {"page_number": 3, "sheet_number": "S3.0"},
        {"page_number": 1, "sheet_number": "A1.1"},
        {"page_number": 2, "sheet_number": "A2.0"},
    ]
    fp = extract_structural_fingerprint(extractions)
    pages = [p["page_number"] for p in fp]
    assert pages == sorted(pages)


def test_extract_fingerprint_skips_missing_page_number():
    """Entries without page_number are skipped."""
    from web.plan_fingerprint import extract_structural_fingerprint

    extractions = [
        {"sheet_number": "A1.1"},  # no page_number
        {"page_number": 2, "sheet_number": "A2.0"},
    ]
    fp = extract_structural_fingerprint(extractions)
    assert len(fp) == 1
    assert fp[0]["page_number"] == 2


def test_extract_fingerprint_sheet_from_title_fallback():
    """_extract_sheet_number falls back to scanning 'title' for X#.# pattern."""
    from web.plan_fingerprint import extract_structural_fingerprint

    extractions = [
        {"page_number": 1, "title": "Architectural Plan A1.1 - Floor Plan"},
    ]
    fp = extract_structural_fingerprint(extractions)
    assert fp[0]["sheet_number"] == "A1.1"


# ── compute_overlap_score() unit tests ────────────────────────────


def test_overlap_score_identical_fingerprints():
    """Two identical fingerprints should score 1.0."""
    from web.plan_fingerprint import compute_overlap_score

    fp = [
        {"page_number": 1, "sheet_number": "A1.1"},
        {"page_number": 2, "sheet_number": "A2.0"},
    ]
    assert compute_overlap_score(fp, fp) == 1.0


def test_overlap_score_no_overlap():
    """Completely different fingerprints should score 0.0."""
    from web.plan_fingerprint import compute_overlap_score

    fp_a = [{"page_number": 1, "sheet_number": "A1.1"}]
    fp_b = [{"page_number": 2, "sheet_number": "S2.0"}]
    assert compute_overlap_score(fp_a, fp_b) == 0.0


def test_overlap_score_empty_returns_zero():
    """Empty fingerprint returns 0.0."""
    from web.plan_fingerprint import compute_overlap_score

    assert compute_overlap_score([], [{"page_number": 1, "sheet_number": "A1.1"}]) == 0.0
    assert compute_overlap_score([{"page_number": 1, "sheet_number": "A1.1"}], []) == 0.0


def test_overlap_score_partial():
    """50% overlap with sheet_numbers present → score ~0.5."""
    from web.plan_fingerprint import compute_overlap_score

    fp_a = [
        {"page_number": 1, "sheet_number": "A1.1"},
        {"page_number": 2, "sheet_number": "A2.0"},
    ]
    fp_b = [
        {"page_number": 1, "sheet_number": "A1.1"},
        {"page_number": 3, "sheet_number": "S3.0"},
    ]
    score = compute_overlap_score(fp_a, fp_b)
    # 1 match (weight 1.0) / 3 total unique (weights 1+1+1=3) = 0.333...
    # Actually: matched_weight=1.0, total_weight = max(1,0)+max(1,1)+max(0,1)=1+1+1=3
    assert 0.3 < score < 0.4


def test_overlap_score_none_sheet_weight_half():
    """Pages with sheet_number=None contribute weight 0.5."""
    from web.plan_fingerprint import compute_overlap_score

    # Both have page 1 with no sheet_number → weight 0.5 match
    fp_a = [{"page_number": 1, "sheet_number": None}]
    fp_b = [{"page_number": 1, "sheet_number": None}]
    score = compute_overlap_score(fp_a, fp_b)
    # matched_weight = 0.5, total_weight = 0.5 → score = 1.0
    assert score == 1.0


def test_overlap_score_none_vs_named_no_match():
    """Page with sheet_number=None does NOT match the same page with a sheet_number."""
    from web.plan_fingerprint import compute_overlap_score

    fp_a = [{"page_number": 1, "sheet_number": "A1.1"}]
    fp_b = [{"page_number": 1, "sheet_number": None}]
    # Different keys: (1, "A1.1") vs (1, None) → no overlap
    score = compute_overlap_score(fp_a, fp_b)
    assert score == 0.0


# ── fingerprints_match() unit tests ───────────────────────────────


def test_fingerprints_match_above_threshold():
    """fingerprints_match returns True when overlap >= 60%."""
    from web.plan_fingerprint import fingerprints_match

    fp = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 11)]
    # 8 matching out of 10 total = 80%
    fp_b = fp[:8] + [
        {"page_number": 11, "sheet_number": "S11.0"},
        {"page_number": 12, "sheet_number": "S12.0"},
    ]
    assert fingerprints_match(fp, fp_b)


def test_fingerprints_match_below_threshold():
    """fingerprints_match returns False when overlap < 60%."""
    from web.plan_fingerprint import fingerprints_match

    fp_a = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 6)]
    fp_b = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(4, 11)]
    # Overlap: pages 4,5 match = 2 matching / 10 total unique = 20%
    assert not fingerprints_match(fp_a, fp_b)


def test_fingerprints_match_exactly_at_threshold():
    """fingerprints_match returns True at exactly 60%."""
    from web.plan_fingerprint import compute_overlap_score, fingerprints_match, OVERLAP_THRESHOLD

    # Construct fingerprints with exactly 60% overlap
    fp_a = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 6)]   # 5 pages
    fp_b = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 4)]   # first 3 match
    # 3 matching / (5 + 3 - 3) = 3/5 = 0.6 → exactly at threshold
    # Actually it's 3 match, 5 total unique → 3/5 = 0.60
    score = compute_overlap_score(fp_a, fp_b)
    assert abs(score - 0.6) < 0.01
    assert fingerprints_match(fp_a, fp_b)  # >= 60% should pass


# ── metadata_matches() unit tests ─────────────────────────────────


def test_metadata_matches_by_permit_number():
    """metadata_matches returns True when permit numbers match (case-insensitive)."""
    from web.plan_fingerprint import metadata_matches

    a = {"permit_number": "202401234567", "property_address": None, "filename": "a.pdf"}
    b = {"permit_number": "202401234567", "property_address": None, "filename": "b.pdf"}
    assert metadata_matches(a, b)


def test_metadata_matches_by_address():
    """metadata_matches returns True when addresses match (case-insensitive)."""
    from web.plan_fingerprint import metadata_matches

    a = {"permit_number": None, "property_address": "123 Main St", "filename": "a.pdf"}
    b = {"permit_number": None, "property_address": "123 MAIN ST", "filename": "b.pdf"}
    assert metadata_matches(a, b)


def test_metadata_matches_by_filename():
    """metadata_matches returns True when normalised filenames match."""
    from web.plan_fingerprint import metadata_matches

    a = {"permit_number": None, "property_address": None, "filename": "My_Plans_V2.pdf"}
    b = {"permit_number": None, "property_address": None, "filename": "My Plans V2.pdf"}
    assert metadata_matches(a, b)


def test_metadata_no_match():
    """metadata_matches returns False when nothing matches."""
    from web.plan_fingerprint import metadata_matches

    a = {"permit_number": "111", "property_address": "1 A St", "filename": "a.pdf"}
    b = {"permit_number": "222", "property_address": "2 B St", "filename": "b.pdf"}
    assert not metadata_matches(a, b)


# ── update_job_status stores structural_fingerprint ───────────────


def test_update_job_status_stores_fingerprint():
    """update_job_status() with structural_fingerprint saves JSON to DB."""
    from web.plan_jobs import update_job_status
    from src.db import query_one
    from datetime import datetime, timezone

    job_id = _make_job()
    fp = [{"page_number": 1, "sheet_number": "A1.1"}]
    fp_json = json.dumps(fp)

    update_job_status(
        job_id,
        "completed",
        completed_at=datetime.now(timezone.utc),
        structural_fingerprint=fp_json,
    )

    row = query_one(
        "SELECT structural_fingerprint FROM plan_analysis_jobs WHERE job_id = %s",
        (job_id,),
    )
    assert row is not None
    assert row[0] == fp_json


# ── find_matching_job() integration tests ─────────────────────────


def test_find_matching_job_layer1_exact_hash():
    """Layer 1: exact hash match returns the matching job_id immediately."""
    from web.plan_fingerprint import find_matching_job

    # Create first job with PDF, mark completed
    job_id_1 = _make_job(user_id=1, pdf_data=_FAKE_PDF, filename="v1.pdf")
    _complete_job(job_id_1)

    # Create second job with same PDF
    job_id_2 = _make_job(user_id=1, pdf_data=_FAKE_PDF, filename="v2.pdf")
    _complete_job(job_id_2)

    current_hash = hashlib.sha256(_FAKE_PDF).hexdigest()

    # Create a third job (the "current" one) — same PDF
    job_id_3 = _make_job(user_id=1, pdf_data=_FAKE_PDF, filename="v3.pdf")

    match = find_matching_job(
        user_id=1,
        current_job_id=job_id_3,
        current_fp=[],
        current_hash=current_hash,
        filename="v3.pdf",
        property_address=None,
        permit_number=None,
    )
    # Should match job_id_1 or job_id_2 (whichever is newest — job_id_2)
    assert match in (job_id_1, job_id_2)


def test_find_matching_job_layer2_structural_overlap():
    """Layer 2: structural overlap >= 60% returns a match."""
    from web.plan_fingerprint import find_matching_job

    # Base fingerprint: 10 pages
    fp_base = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 11)]
    fp_json = json.dumps(fp_base)

    job_id_1 = _make_job(user_id=1, filename="orig.pdf")
    _complete_job(job_id_1, structural_fingerprint=fp_json)

    # Current job has 8/10 matching pages = 80% overlap
    fp_current = fp_base[:8] + [
        {"page_number": 11, "sheet_number": "S11.0"},
        {"page_number": 12, "sheet_number": "S12.0"},
    ]

    job_id_2 = _make_job(user_id=1, filename="revised.pdf")
    match = find_matching_job(
        user_id=1,
        current_job_id=job_id_2,
        current_fp=fp_current,
        current_hash=None,
        filename="revised.pdf",
        property_address=None,
        permit_number=None,
    )
    assert match == job_id_1


def test_find_matching_job_layer2_below_threshold_no_match():
    """Layer 2: structural overlap < 60% returns None."""
    from web.plan_fingerprint import find_matching_job

    # Fingerprint A: pages 1-5
    fp_a = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(1, 6)]
    job_id_1 = _make_job(user_id=1, filename="orig.pdf")
    _complete_job(job_id_1, structural_fingerprint=json.dumps(fp_a))

    # Current job has pages 4-10 — only 2 matching out of 10 unique = 20%
    fp_current = [{"page_number": i, "sheet_number": f"A{i}.0"} for i in range(4, 11)]

    job_id_2 = _make_job(user_id=1, filename="other.pdf")
    match = find_matching_job(
        user_id=1,
        current_job_id=job_id_2,
        current_fp=fp_current,
        current_hash=None,
        filename="other.pdf",
        property_address=None,
        permit_number=None,
    )
    assert match is None


def test_find_matching_job_no_cross_user_linking():
    """find_matching_job() must NOT link jobs across different user accounts."""
    from web.plan_fingerprint import find_matching_job

    # User 1 has a completed job with the same PDF
    job_id_user1 = _make_job(user_id=1, pdf_data=_FAKE_PDF, filename="plans.pdf")
    _complete_job(job_id_user1)

    # User 2 uploads the same PDF
    job_id_user2 = _make_job(user_id=2, pdf_data=_FAKE_PDF, filename="plans.pdf")
    current_hash = hashlib.sha256(_FAKE_PDF).hexdigest()

    match = find_matching_job(
        user_id=2,
        current_job_id=job_id_user2,
        current_fp=[],
        current_hash=current_hash,
        filename="plans.pdf",
        property_address=None,
        permit_number=None,
    )
    # Must return None — no cross-user linking
    assert match is None


def test_find_matching_job_no_match_returns_none():
    """find_matching_job() returns None when no candidates exist."""
    from web.plan_fingerprint import find_matching_job

    job_id = _make_job(user_id=1, filename="unique.pdf")
    match = find_matching_job(
        user_id=1,
        current_job_id=job_id,
        current_fp=[],
        current_hash=None,
        filename="unique.pdf",
        property_address=None,
        permit_number=None,
    )
    assert match is None
