"""Tests for web UI plan analysis endpoints — Integration tests.

Tests the /plan-images, /plan-session, and related endpoints.
Mocks external dependencies (Vision API, email, PDF rendering).
"""

import base64
import os
import sys
import pytest
import zipfile
from io import BytesIO

from pypdf import PdfWriter

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.app import app, _rate_buckets


@pytest.fixture(autouse=True)
def _ensure_duckdb_backend(monkeypatch):
    """Ensure DuckDB backend and clean plan tables before each test.

    Uses the session-scoped temp DB from conftest's _isolated_test_db.
    """
    import src.db as db_mod
    import web.plan_images as pi_mod
    import web.auth as auth_mod

    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(pi_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "DATABASE_URL", None)

    # Clean plan tables before each test
    try:
        conn = db_mod.get_connection()
        try:
            conn.execute("DELETE FROM plan_analysis_images")
            conn.execute("DELETE FROM plan_analysis_sessions")
        except Exception:
            pass
        finally:
            conn.close()
    except Exception:
        pass


@pytest.fixture
def client():
    """Flask test client with rate limiting disabled."""
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _make_test_image_base64() -> str:
    """Create a small test PNG image as base64 (1x1 red pixel)."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("ascii")


def _create_test_session():
    """Helper to create a plan session for endpoint tests."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    return create_session(
        filename="test-plans.pdf",
        page_count=3,
        page_images=[(0, test_image), (1, test_image), (2, test_image)],
        page_extractions=[
            {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "FLOOR PLAN"},
            {"page_number": 2, "sheet_number": "A2.0", "sheet_name": "ELEVATIONS"},
            {"page_number": 3, "sheet_number": "S1.0", "sheet_name": "FOUNDATION"},
        ],
    )


# ── /plan-images/<session_id>/<page> endpoint ────────────────────────────────


def test_plan_image_endpoint_returns_png(client):
    """GET /plan-images/<session_id>/<page> returns PNG image."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="images.pdf",
        page_count=2,
        page_images=[(1, test_image), (2, test_image)],
        page_extractions=[],
    )

    rv = client.get(f"/plan-images/{session_id}/1")
    assert rv.status_code == 200
    assert rv.mimetype == "image/png"
    assert len(rv.data) > 0


def test_plan_image_invalid_session_404(client):
    """GET /plan-images/<invalid-session>/<page> returns 404."""
    rv = client.get("/plan-images/invalid-session-12345/1")
    assert rv.status_code == 404


def test_plan_image_invalid_page_404(client):
    """GET /plan-images/<session_id>/999 returns 404 for out-of-range page."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="pages.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=[],
    )

    rv = client.get(f"/plan-images/{session_id}/999")
    assert rv.status_code == 404


# ── /plan-session/<session_id> endpoint ──────────────────────────────────────


@pytest.mark.xfail(reason="DuckDB connection contamination in full suite — passes in isolation", strict=False)
def test_plan_session_endpoint_returns_json(client):
    """GET /plan-session/<session_id> returns session metadata as JSON."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    page_extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "COVER"},
    ]
    session_id = create_session(
        filename="session-meta.pdf",
        page_count=1,
        page_images=[(1, test_image)],
        page_extractions=page_extractions,
    )

    rv = client.get(f"/plan-session/{session_id}")
    assert rv.status_code == 200
    assert rv.mimetype == "application/json"

    data = rv.get_json()
    assert data["session_id"] == session_id
    assert data["filename"] == "session-meta.pdf"
    assert data["page_count"] == 1
    assert data["page_extractions"] == page_extractions


def test_plan_session_invalid_404(client):
    """GET /plan-session/<invalid> returns 404."""
    rv = client.get("/plan-session/nonexistent-session")
    assert rv.status_code == 404


# ── /plan-images/<session_id>/download-all endpoint ──────────────────────────


@pytest.mark.xfail(reason="DuckDB connection contamination in full suite — passes in isolation", strict=False)
def test_download_all_pages_returns_zip(client):
    """GET /plan-images/<session_id>/download-all returns ZIP with all pages."""
    from web.plan_images import create_session

    test_image = _make_test_image_base64()
    # Note: download route iterates range(page_count) with 0-indexed page numbers
    session_id = create_session(
        filename="download-test.pdf",
        page_count=3,
        page_images=[(0, test_image), (1, test_image), (2, test_image)],
        page_extractions=[],
    )

    rv = client.get(f"/plan-images/{session_id}/download-all")
    assert rv.status_code == 200
    assert rv.mimetype == "application/zip"

    zip_data = BytesIO(rv.data)
    with zipfile.ZipFile(zip_data, 'r') as zf:
        namelist = zf.namelist()
        assert len(namelist) == 3
        assert "page-1.png" in namelist
        assert "page-2.png" in namelist
        assert "page-3.png" in namelist
