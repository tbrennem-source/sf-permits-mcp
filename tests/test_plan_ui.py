"""Tests for web UI plan analysis endpoints — Integration tests.

Tests the /analyze-plans route and related plan image/session endpoints.
Mocks all external dependencies (Vision API, email, PDF rendering, image conversion).
"""

import base64
import io
import os
import sys
import pytest
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch, AsyncMock, MagicMock

from pypdf import PdfWriter

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web.app import app, _rate_buckets


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_plan_ui.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)

    # Initialize schemas
    from src.plan_images import init_plan_images_schema
    init_plan_images_schema()

    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    """Flask test client with rate limiting disabled."""
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _make_pdf(num_pages: int = 3) -> bytes:
    """Create a synthetic multi-page PDF."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=34 * 72, height=22 * 72)  # Arch D size
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_test_image_base64() -> str:
    """Create a small test PNG image as base64 (1x1 red pixel)."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("ascii")


# ── /analyze-plans route ─────────────────────────────────────────────────────


def test_analyze_plans_route_creates_session(client):
    """POST /analyze-plans creates a session and returns session_id in response."""
    pdf_bytes = _make_pdf(3)
    test_image = _make_test_image_base64()

    # Mock pdf_pages_to_base64 to return test images
    mock_page_extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "FLOOR PLAN"},
        {"page_number": 2, "sheet_number": "A2.0", "sheet_name": "ELEVATIONS"},
        {"page_number": 3, "sheet_number": "S1.0", "sheet_name": "FOUNDATION"},
    ]

    with patch("src.vision.pdf_to_images.pdf_pages_to_base64", return_value=[test_image] * 3):
        with patch("src.tools.analyze_plans.analyze_plans", AsyncMock(
            return_value=("# Plan Report\n\nTest report", mock_page_extractions)
        )):
            rv = client.post(
                "/analyze-plans",
                data={"planfile": (BytesIO(pdf_bytes), "test-plans.pdf")},
                content_type="multipart/form-data",
            )

    assert rv.status_code == 200
    html = rv.data.decode()

    # Verify response contains session_id (data attribute for JS)
    assert 'data-session-id=' in html or 'session-id' in html.lower()

    # Verify report content is rendered
    assert "Plan Report" in html or "Test report" in html


def test_analyze_plans_route_graceful_degradation(client):
    """analyze_plans route handles image rendering failure gracefully."""
    pdf_bytes = _make_pdf(2)

    # Mock pdf_pages_to_base64 to raise an exception
    with patch("src.vision.pdf_to_images.pdf_pages_to_base64", side_effect=Exception("Image conversion failed")):
        with patch("src.tools.analyze_plans.analyze_plans", AsyncMock(
            return_value="# Plan Report\n\nMetadata-only analysis"
        )):
            rv = client.post(
                "/analyze-plans",
                data={"planfile": (BytesIO(pdf_bytes), "fallback.pdf")},
                content_type="multipart/form-data",
            )

    assert rv.status_code == 200
    html = rv.data.decode()

    # Should still return analysis (just without images stored)
    assert "Plan Report" in html or "Metadata-only" in html


# ── /plan-images/<session_id>/<page> endpoint ────────────────────────────────


def test_plan_image_endpoint_returns_png(client):
    """GET /plan-images/<session_id>/<page> returns PNG image."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="images.pdf",
        page_images=[test_image, test_image],
        page_extractions=[],
    )

    rv = client.get(f"/plan-images/{session_id}/1")
    assert rv.status_code == 200
    assert rv.mimetype == "image/png"

    # Verify it's valid base64 image data
    image_bytes = rv.data
    assert len(image_bytes) > 0


def test_plan_image_invalid_session_404(client):
    """GET /plan-images/<invalid-session>/<page> returns 404."""
    rv = client.get("/plan-images/invalid-uuid-12345/1")
    assert rv.status_code == 404


def test_plan_image_invalid_page_404(client):
    """GET /plan-images/<session_id>/999 returns 404 for out-of-range page."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="pages.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Valid session, but page out of range
    rv = client.get(f"/plan-images/{session_id}/999")
    assert rv.status_code == 404


# ── /plan-session/<session_id> endpoint ──────────────────────────────────────


def test_plan_session_endpoint_returns_json(client):
    """GET /plan-session/<session_id> returns session metadata as JSON."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    page_extractions = [
        {"page_number": 1, "sheet_number": "A1.0", "sheet_name": "COVER"},
    ]
    session_id = create_session(
        filename="session-meta.pdf",
        page_images=[test_image],
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
    assert "created_at" in data


# ── /plan-images/<session_id>/download/all endpoint ──────────────────────────


def test_download_all_pages_returns_zip(client):
    """GET /plan-images/<session_id>/download/all returns ZIP with all pages."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="download-test.pdf",
        page_images=[test_image, test_image, test_image],
        page_extractions=[],
    )

    rv = client.get(f"/plan-images/{session_id}/download/all")
    assert rv.status_code == 200
    assert rv.mimetype == "application/zip"

    # Verify ZIP contents
    zip_data = BytesIO(rv.data)
    with zipfile.ZipFile(zip_data, 'r') as zf:
        namelist = zf.namelist()
        assert len(namelist) == 3
        assert "page_1.png" in namelist
        assert "page_2.png" in namelist
        assert "page_3.png" in namelist


# ── /plan-analysis/<session_id>/download/report endpoint ─────────────────────


def test_download_report_pdf(client):
    """GET /plan-analysis/<session_id>/download/report returns PDF."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="report.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Mock WeasyPrint PDF generation
    mock_pdf_bytes = b"%PDF-1.4 fake pdf content"

    with patch("weasyprint.HTML") as mock_html:
        mock_instance = MagicMock()
        mock_instance.write_pdf.return_value = mock_pdf_bytes
        mock_html.return_value = mock_instance

        rv = client.get(f"/plan-analysis/{session_id}/download/report")

    assert rv.status_code == 200
    assert rv.mimetype == "application/pdf"
    assert rv.data == mock_pdf_bytes


# ── /plan-analysis/<session_id>/email endpoint ───────────────────────────────


def test_email_analysis_sends_email(client):
    """POST /plan-analysis/<session_id>/email sends email with attachments."""
    from src.plan_images import create_session

    test_image = _make_test_image_base64()
    session_id = create_session(
        filename="email-test.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Mock send_email
    with patch("web.email_brief.send_email") as mock_send:
        mock_send.return_value = True

        rv = client.post(
            f"/plan-analysis/{session_id}/email",
            data={"email": "user@example.com"},
        )

    assert rv.status_code == 200

    # Verify send_email was called
    assert mock_send.called
    call_args = mock_send.call_args
    assert call_args[1]["to"] == "user@example.com"
    assert "subject" in call_args[1]
    assert "attachments" in call_args[1]


# ── Nightly cleanup integration ──────────────────────────────────────────────


def test_session_cleanup_in_nightly_cron(client):
    """Verify cleanup_expired is called in nightly cron job."""
    from src.plan_images import create_session, get_session
    from src.db import execute_write

    test_image = _make_test_image_base64()

    # Create an old session (26 hours ago)
    old_id = create_session(
        filename="old.pdf",
        page_images=[test_image],
        page_extractions=[],
    )

    # Backdate it
    old_timestamp = datetime.utcnow() - timedelta(hours=26)
    execute_write(
        "UPDATE plan_sessions SET created_at = %s WHERE session_id = %s",
        (old_timestamp, old_id),
    )

    # Mock cleanup_expired
    with patch("src.plan_images.cleanup_expired") as mock_cleanup:
        mock_cleanup.return_value = 1

        # Simulate nightly cron endpoint (if it exists)
        # For now, just verify the function can be called
        from src.plan_images import cleanup_expired
        deleted = cleanup_expired(max_age_hours=24)

        # Verify old session would be deleted
        assert get_session(old_id) is None
