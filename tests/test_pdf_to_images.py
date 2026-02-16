"""Tests for vision/pdf_to_images.py — PDF-to-image conversion utilities.

Tests page count, base64 output, downsampling, and error handling.
Uses synthetic PDFs created with pypdf. No external PDFs required.
"""

import base64
import sys
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

from pypdf import PdfWriter
from PIL import Image

from src.vision.pdf_to_images import (
    pdf_page_to_base64,
    pdf_pages_to_base64,
    get_page_count,
    DEFAULT_DPI,
    MAX_DIMENSION,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_pdf(num_pages: int = 3) -> bytes:
    """Create a synthetic multi-page PDF."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=34 * 72, height=22 * 72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _fake_convert(pdf_bytes, dpi=150, first_page=1, last_page=1, fmt="png"):
    """Mock pdf2image.convert_from_bytes — returns a small PIL image."""
    img = Image.new("RGB", (800, 600), color="white")
    return [img]


def _fake_convert_large(pdf_bytes, dpi=150, first_page=1, last_page=1, fmt="png"):
    """Mock returning an oversized image."""
    img = Image.new("RGB", (3000, 2000), color="white")
    return [img]


def _fake_convert_empty(pdf_bytes, dpi=150, first_page=1, last_page=1, fmt="png"):
    """Mock returning no images (page not found)."""
    return []


@pytest.fixture
def mock_pdf2image():
    """Install a mock pdf2image module so convert_from_bytes can be imported."""
    mock_mod = MagicMock()
    mock_mod.convert_from_bytes = _fake_convert
    with patch.dict(sys.modules, {"pdf2image": mock_mod}):
        yield mock_mod


# ── get_page_count ───────────────────────────────────────────────────────────


def test_page_count_single():
    """Single-page PDF returns 1."""
    pdf = _make_pdf(1)
    assert get_page_count(pdf) == 1


def test_page_count_multi():
    """Multi-page PDF returns correct count."""
    pdf = _make_pdf(7)
    assert get_page_count(pdf) == 7


def test_page_count_empty_pdf():
    """PDF with no pages returns 0."""
    writer = PdfWriter()
    buf = BytesIO()
    writer.write(buf)
    assert get_page_count(buf.getvalue()) == 0


# ── pdf_page_to_base64 ──────────────────────────────────────────────────────


def test_page_to_base64_returns_valid_base64(mock_pdf2image):
    """Output is valid base64 that decodes to PNG bytes."""
    mock_pdf2image.convert_from_bytes = _fake_convert
    pdf = _make_pdf(1)
    b64 = pdf_page_to_base64(pdf, 0)
    assert isinstance(b64, str)
    assert len(b64) > 0
    raw = base64.b64decode(b64)
    assert raw[:4] == b"\x89PNG"


def test_page_to_base64_downsample(mock_pdf2image):
    """Large images are downsampled to MAX_DIMENSION."""
    mock_pdf2image.convert_from_bytes = _fake_convert_large
    pdf = _make_pdf(1)
    b64 = pdf_page_to_base64(pdf, 0)
    raw = base64.b64decode(b64)
    img = Image.open(BytesIO(raw))
    assert max(img.size) <= MAX_DIMENSION


def test_page_to_base64_invalid_page(mock_pdf2image):
    """Invalid page number raises ValueError."""
    mock_pdf2image.convert_from_bytes = _fake_convert_empty
    pdf = _make_pdf(1)
    with pytest.raises(ValueError, match="Failed to render"):
        pdf_page_to_base64(pdf, 99)


# ── pdf_pages_to_base64 ─────────────────────────────────────────────────────


def test_pages_to_base64_multi(mock_pdf2image):
    """Multiple pages produce correct (page_num, base64) tuples."""
    mock_pdf2image.convert_from_bytes = _fake_convert
    pdf = _make_pdf(5)
    results = pdf_pages_to_base64(pdf, [0, 2, 4])
    assert len(results) == 3
    assert results[0][0] == 0
    assert results[1][0] == 2
    assert results[2][0] == 4
    for pn, b64 in results:
        assert isinstance(b64, str)
        assert len(b64) > 0


def test_pages_to_base64_empty_list(mock_pdf2image):
    """Empty page list produces empty results."""
    mock_pdf2image.convert_from_bytes = _fake_convert
    pdf = _make_pdf(3)
    results = pdf_pages_to_base64(pdf, [])
    assert results == []
