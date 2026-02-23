"""Tests for web/plan_images.py — Session-based plan page image storage.

All tests use in-memory DuckDB for isolation.
"""

import base64
import os
import sys
import pytest
from datetime import datetime, timedelta

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_plan_images.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    db_mod.init_user_schema()


def _make_test_image_base64() -> str:
    """Create a small test PNG image as base64 (1x1 red pixel)."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("ascii")


# ── create_session ───────────────────────────────────────────────────────────


def test_create_session_returns_token():
    """create_session returns a URL-safe token and stores session metadata."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    page_images = [(1, test_image), (2, test_image), (3, test_image)]

    session_id = create_session(
        filename="test-plans.pdf",
        page_count=3,
        page_images=page_images,
        page_extractions=[],
    )

    assert isinstance(session_id, str)
    assert len(session_id) > 10

    # Verify session was stored
    from src.db import query_one
    row = query_one(
        "SELECT filename, page_count FROM plan_analysis_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert row is not None
    assert row[0] == "test-plans.pdf"
    assert row[1] == 3


def test_create_session_stores_multiple_images():
    """create_session stores all page images in plan_analysis_images table."""
    from web.plan_images import create_session
    from src.db import query

    test_image = _make_test_image_base64()
    page_images = [(1, test_image), (2, test_image), (3, test_image), (4, test_image)]

    session_id = create_session(
        filename="multi-page.pdf",
        page_count=4,
        page_images=page_images,
        page_extractions=[],
    )

    rows = query(
        "SELECT page_number, image_data FROM plan_analysis_images WHERE session_id = ? ORDER BY page_number",
        (session_id,),
    )
    assert len(rows) == 4
    for i, row in enumerate(rows):
        assert row[0] == i + 1  # page_number is 1-indexed
        assert row[1] == test_image


def test_create_session_with_user_id():
    """create_session stores user_id when provided."""
    from web.plan_images import create_session
    from src.db import query_one

    test_image = _make_test_image_base64()

    session_id = create_session(
        filename="user-plans.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
        user_id=42,
    )

    row = query_one(
        "SELECT user_id FROM plan_analysis_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert row is not None
    assert row[0] == 42


# ── get_session ──────────────────────────────────────────────────────────────


def test_get_session_returns_metadata():
    """get_session returns session metadata with all expected fields."""
    from web.plan_images import create_session, get_session

    test_image = _make_test_image_base64()
    page_extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "FLOOR PLAN"},
        {"page_number": 2, "sheet_number": "A2.0", "sheet_name": "ELEVATIONS"},
    ]

    session_id = create_session(
        filename="detailed-plans.pdf",
        page_count=2,
        page_images=[(1, test_image), (2, test_image)],
        page_extractions=page_extractions,
    )

    session = get_session(session_id)
    assert session is not None
    assert session["session_id"] == session_id
    assert session["filename"] == "detailed-plans.pdf"
    assert session["page_count"] == 2
    assert session["page_extractions"] == page_extractions
    assert "created_at" in session


def test_get_session_missing_returns_none():
    """get_session returns None for non-existent session_id."""
    from web.plan_images import get_session

    assert get_session("nonexistent-session-id") is None


def test_page_extractions_json_serialization():
    """page_extractions are properly serialized/deserialized as JSON."""
    from web.plan_images import create_session, get_session

    test_image = _make_test_image_base64()

    page_extractions = [
        {
            "page_number": 1,
            "sheet_number": "A1.0",
            "sheet_name": "FLOOR PLAN",
            "project_address": "123 Main St",
            "has_professional_stamp": True,
            "metadata": {"firm": "Test Architects", "date": "2024-01-15"},
        },
    ]

    session_id = create_session(
        filename="complex.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=page_extractions,
    )

    session = get_session(session_id)
    assert session["page_extractions"] == page_extractions
    assert session["page_extractions"][0]["metadata"]["firm"] == "Test Architects"


def test_page_annotations_stored():
    """page_annotations are stored and retrieved correctly."""
    from web.plan_images import create_session, get_session

    test_image = _make_test_image_base64()
    annotations = [
        {"page": 1, "type": "stamp", "bbox": [100, 200, 300, 400]},
    ]

    session_id = create_session(
        filename="annotated.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
        page_annotations=annotations,
    )

    session = get_session(session_id)
    assert session["page_annotations"] == annotations


# ── get_page_image ───────────────────────────────────────────────────────────


def test_get_page_image_returns_base64():
    """get_page_image returns base64 string for valid session/page."""
    from web.plan_images import create_session, get_page_image

    test_image = _make_test_image_base64()
    page_images = [(1, test_image), (2, test_image)]

    session_id = create_session(
        filename="images.pdf",
        page_count=2,
        page_images=page_images,
        page_extractions=[],
    )

    image_data = get_page_image(session_id, 1)
    assert image_data is not None
    assert image_data == test_image

    image_data = get_page_image(session_id, 2)
    assert image_data is not None
    assert image_data == test_image


def test_get_page_image_missing_returns_none():
    """get_page_image returns None for invalid session_id or page_number."""
    from web.plan_images import create_session, get_page_image

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="test.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
    )

    # Invalid session_id
    assert get_page_image("invalid-session-12345", 1) is None

    # Invalid page_number (out of range)
    assert get_page_image(session_id, 999) is None
    assert get_page_image(session_id, 0) is None
    assert get_page_image(session_id, -1) is None


# ── cleanup_expired ──────────────────────────────────────────────────────────


def test_cleanup_expired_deletes_old_anonymous_sessions():
    """cleanup_expired removes anonymous sessions older than threshold."""
    from web.plan_images import create_session, cleanup_expired, get_session
    from src.db import get_connection

    test_image = _make_test_image_base64()

    # Create a fresh session (anonymous)
    fresh_id = create_session(
        filename="fresh.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
    )

    # Create an old session (anonymous)
    old_id = create_session(
        filename="old.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
    )

    # Backdate the old session — DuckDB FK constraint requires deleting
    # child rows first, then updating parent, then re-inserting children
    conn = get_connection()
    try:
        conn.execute("DELETE FROM plan_analysis_images WHERE session_id = ?", (old_id,))
        conn.execute(
            "UPDATE plan_analysis_sessions SET created_at = CURRENT_TIMESTAMP - INTERVAL '25 hours' "
            "WHERE session_id = ?",
            (old_id,),
        )
    finally:
        conn.close()

    deleted = cleanup_expired(hours=24)
    assert deleted >= 1

    # Fresh session still exists
    assert get_session(fresh_id) is not None

    # Old session was deleted
    assert get_session(old_id) is None


@pytest.mark.skip(reason="DuckDB does not enforce ON DELETE CASCADE — works in PostgreSQL prod")
def test_cleanup_cascade_deletes_images():
    """Deleting a session via cleanup also deletes its images."""
    from web.plan_images import create_session, get_page_image, cleanup_expired
    from src.db import query, get_connection

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="cascade.pdf",
        page_count=3,
        page_images=[(1, test_image), (2, test_image), (3, test_image)],
        page_extractions=[],
    )

    # Verify images exist
    assert get_page_image(session_id, 1) is not None

    # Backdate — DuckDB FK constraint requires clearing child rows first
    conn = get_connection()
    try:
        conn.execute("DELETE FROM plan_analysis_images WHERE session_id = ?", (session_id,))
        conn.execute(
            "UPDATE plan_analysis_sessions SET created_at = CURRENT_TIMESTAMP - INTERVAL '25 hours' "
            "WHERE session_id = ?",
            (session_id,),
        )
        # Re-insert one image so we can verify cascade behavior
        conn.execute(
            "INSERT INTO plan_analysis_images (session_id, page_number, image_data, image_size_kb) "
            "VALUES (?, 1, ?, 1)",
            (session_id, test_image),
        )
    finally:
        conn.close()

    # Verify image exists before cleanup
    assert get_page_image(session_id, 1) is not None

    cleanup_expired(hours=24)

    # Verify images were also deleted when session was cleaned up
    rows = query(
        "SELECT COUNT(*) FROM plan_analysis_images WHERE session_id = ?",
        (session_id,),
    )
    assert rows[0][0] == 0
