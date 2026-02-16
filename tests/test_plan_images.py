"""Tests for src/plan_images.py — Session-based plan page image storage.

All tests use in-memory DuckDB for isolation. Mocks are used for PDF processing.
"""

import base64
import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

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

    # Import after monkeypatch
    from src.plan_images import init_plan_images_schema
    init_plan_images_schema()


def _make_test_image_base64() -> str:
    """Create a small test PNG image as base64 (1x1 red pixel)."""
    # PNG format: 1x1 red pixel (minimal valid PNG, ~68 bytes)
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("ascii")


# ── create_session ───────────────────────────────────────────────────────────


def test_create_session_returns_uuid():
    """create_session returns a valid UUID and stores session metadata."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    page_images = [test_image, test_image, test_image]  # 3 pages

    session_id = create_session(
        filename="test-plans.pdf",
        page_images=page_images,
        page_extractions=[],
    )

    # Verify UUID format (36 chars with hyphens)
    assert len(session_id) == 36
    assert session_id.count("-") == 4

    # Verify session was stored
    from src.db import query_one
    row = query_one(
        "SELECT filename, page_count FROM plan_sessions WHERE session_id = %s",
        (session_id,),
    )
    assert row is not None
    assert row[0] == "test-plans.pdf"
    assert row[1] == 3


def test_create_session_stores_multiple_images():
    """create_session stores all page images in plan_images table."""
    from src.plan_images import create_session
    from src.db import query

    test_image = _make_test_image_base64()
    page_images = [test_image, test_image, test_image, test_image]  # 4 pages

    session_id = create_session(
        filename="multi-page.pdf",
        page_images=page_images,
        page_extractions=[],
    )

    # Verify all images were stored
    rows = query(
        "SELECT page_number, image_data FROM plan_images WHERE session_id = %s ORDER BY page_number",
        (session_id,),
    )
    assert len(rows) == 4
    for i, row in enumerate(rows):
        assert row[0] == i + 1  # page_number is 1-indexed
        assert row[1] == test_image


# ── get_session ──────────────────────────────────────────────────────────────


def test_get_session_returns_metadata():
    """get_session returns session metadata with all expected fields."""
    from src.plan_images import create_session, get_session

    test_image = _make_test_image_base64()
    page_extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "FLOOR PLAN"},
        {"page_number": 2, "sheet_number": "A2.0", "sheet_name": "ELEVATIONS"},
    ]

    session_id = create_session(
        filename="detailed-plans.pdf",
        page_images=[test_image, test_image],
        page_extractions=page_extractions,
    )

    session = get_session(session_id)
    assert session is not None
    assert session["session_id"] == session_id
    assert session["filename"] == "detailed-plans.pdf"
    assert session["page_count"] == 2
    assert session["page_extractions"] == page_extractions
    assert "created_at" in session
    assert isinstance(session["created_at"], str)  # ISO timestamp


def test_page_extractions_json_serialization():
    """page_extractions are properly serialized/deserialized as JSON."""
    from src.plan_images import create_session, get_session

    test_image = _make_test_image_base64()

    # Complex nested structure
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
        page_images=[test_image],
        page_extractions=page_extractions,
    )

    session = get_session(session_id)
    assert session["page_extractions"] == page_extractions
    # Verify nested dict preserved
    assert session["page_extractions"][0]["metadata"]["firm"] == "Test Architects"


# ── get_page_image ───────────────────────────────────────────────────────────


def test_get_page_image_returns_base64():
    """get_page_image returns base64 string for valid session/page."""
    from src.plan_images import create_session, get_page_image

    test_image = _make_test_image_base64()
    page_images = [test_image, test_image]

    session_id = create_session(
        filename="images.pdf",
        page_images=page_images,
        page_extractions=[],
    )

    # Retrieve page 1
    image_data = get_page_image(session_id, 1)
    assert image_data is not None
    assert image_data == test_image

    # Retrieve page 2
    image_data = get_page_image(session_id, 2)
    assert image_data is not None
    assert image_data == test_image


def test_get_page_image_missing_returns_none():
    """get_page_image returns None for invalid session_id or page_number."""
    from src.plan_images import create_session, get_page_image

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="test.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Invalid session_id
    assert get_page_image("invalid-uuid-12345", 1) is None

    # Invalid page_number (out of range)
    assert get_page_image(session_id, 999) is None
    assert get_page_image(session_id, 0) is None
    assert get_page_image(session_id, -1) is None


# ── cleanup_expired ──────────────────────────────────────────────────────────


def test_cleanup_expired_deletes_old_sessions():
    """cleanup_expired removes sessions older than 24 hours."""
    from src.plan_images import create_session, cleanup_expired, get_session
    from src.db import execute_write

    test_image = _make_test_image_base64()

    # Create a fresh session
    fresh_id = create_session(
        filename="fresh.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Create an old session (manually set created_at to 25 hours ago)
    old_id = create_session(
        filename="old.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Backdate the old session
    old_timestamp = datetime.utcnow() - timedelta(hours=25)
    execute_write(
        "UPDATE plan_sessions SET created_at = %s WHERE session_id = %s",
        (old_timestamp, old_id),
    )

    # Run cleanup
    deleted = cleanup_expired(max_age_hours=24)
    assert deleted >= 1

    # Verify fresh session still exists
    assert get_session(fresh_id) is not None

    # Verify old session was deleted
    assert get_session(old_id) is None


def test_session_cascade_deletes_images():
    """Deleting a session also deletes its images via CASCADE."""
    from src.plan_images import create_session, get_page_image
    from src.db import execute_write, query

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="cascade.pdf",
        page_images=[test_image, test_image, test_image],
        page_extractions=[],
    )

    # Verify images exist
    assert get_page_image(session_id, 1) is not None
    assert get_page_image(session_id, 2) is not None

    # Manually delete session
    execute_write(
        "DELETE FROM plan_sessions WHERE session_id = %s",
        (session_id,),
    )

    # Verify images were also deleted (CASCADE constraint)
    rows = query(
        "SELECT COUNT(*) FROM plan_images WHERE session_id = %s",
        (session_id,),
    )
    assert rows[0][0] == 0
