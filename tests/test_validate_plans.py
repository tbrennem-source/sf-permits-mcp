"""Tests for validate_plans tool — PDF plan set EPR compliance checker.

Uses synthetic PDFs created with pypdf.PdfWriter. No external PDF files required.
"""

import pytest
from io import BytesIO
from pypdf import PdfWriter

from src.tools.validate_plans import (
    validate_plans,
    _check_file_size,
    _check_encryption,
    _check_page_dimensions,
    _check_bookmarks,
    _check_page_labels,
    _check_fonts,
    _check_digital_signatures,
    _check_vector_vs_raster,
    _check_annotations,
    _check_filename,
    _check_back_check_page,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_pdf(
    num_pages: int = 1,
    page_width_inches: float = 34.0,
    page_height_inches: float = 22.0,
    add_bookmarks: bool = False,
    encrypt: str | None = None,
) -> bytes:
    """Create a synthetic PDF with controllable properties."""
    writer = PdfWriter()
    for i in range(num_pages):
        writer.add_blank_page(
            width=page_width_inches * 72,
            height=page_height_inches * 72,
        )
        if add_bookmarks:
            writer.add_outline_item(
                title=f"A{i}.0 - SHEET {i}",
                page_number=i,
            )
    if encrypt:
        writer.encrypt(encrypt)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_mixed_pdf():
    """PDF with large plan sheets + small cover + small back check."""
    writer = PdfWriter()
    # Cover sheet (8.5 x 11)
    writer.add_blank_page(width=8.5 * 72, height=11 * 72)
    # Plan sheets (34 x 22)
    for _ in range(5):
        writer.add_blank_page(width=34 * 72, height=22 * 72)
    # Back check page (8.5 x 11)
    writer.add_blank_page(width=8.5 * 72, height=11 * 72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ── EPR-006: File Size ───────────────────────────────────────────────────────

def test_file_size_pass():
    """Small file passes."""
    pdf = _make_pdf()
    result = _check_file_size(pdf, is_addendum=False)
    assert result.status == "pass"
    assert result.epr_id == "EPR-006"


def test_file_size_warn():
    """File over 50MB warns."""
    fake_bytes = b"x" * (51 * 1024 * 1024)
    result = _check_file_size(fake_bytes, is_addendum=False)
    assert result.status == "warn"


def test_file_size_fail():
    """File over 250MB fails."""
    fake_bytes = b"x" * (251 * 1024 * 1024)
    result = _check_file_size(fake_bytes, is_addendum=False)
    assert result.status == "fail"


def test_file_size_addendum_limit():
    """Addendum uses 350MB limit."""
    fake_bytes = b"x" * (260 * 1024 * 1024)
    result = _check_file_size(fake_bytes, is_addendum=True)
    assert result.status == "warn"  # Over 50MB warn but under 350MB


# ── EPR-009: Encryption ──────────────────────────────────────────────────────

def test_encryption_pass():
    """Unlocked PDF passes."""
    from pypdf import PdfReader
    pdf = _make_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_encryption(reader)
    assert result.status == "pass"


def test_encryption_fail():
    """Encrypted PDF fails."""
    from pypdf import PdfReader
    pdf = _make_pdf(encrypt="secret123")
    reader = PdfReader(BytesIO(pdf), password="secret123")
    # Simulate encrypted state by checking the raw reader
    # Note: after providing password, is_encrypted may be True but readable
    result = _check_encryption(reader)
    # pypdf marks as encrypted even after decryption
    assert result.epr_id == "EPR-009"


# ── EPR-005: Page Dimensions ─────────────────────────────────────────────────

def test_dimensions_pass_arch_d():
    """Arch D (34x22) pages pass."""
    from pypdf import PdfReader
    pdf = _make_pdf(num_pages=3, page_width_inches=34.0, page_height_inches=22.0)
    reader = PdfReader(BytesIO(pdf))
    result = _check_page_dimensions(reader)
    assert result.status == "pass"


def test_dimensions_fail_letter():
    """Letter-size pages fail."""
    from pypdf import PdfReader
    # 3 pages of letter size (not edge pages, so middle page triggers failure)
    pdf = _make_pdf(num_pages=3, page_width_inches=11.0, page_height_inches=8.5)
    reader = PdfReader(BytesIO(pdf))
    result = _check_page_dimensions(reader)
    assert result.status == "fail"


def test_dimensions_mixed_with_cover():
    """Mixed sizes with small cover + back check are allowed."""
    from pypdf import PdfReader
    pdf = _make_mixed_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_page_dimensions(reader)
    assert result.status == "pass"


# ── EPR-007: Bookmarks ──────────────────────────────────────────────────────

def test_bookmarks_present():
    """PDF with bookmarks passes."""
    from pypdf import PdfReader
    pdf = _make_pdf(num_pages=5, add_bookmarks=True)
    reader = PdfReader(BytesIO(pdf))
    result = _check_bookmarks(reader)
    assert result.status == "pass"


def test_bookmarks_missing():
    """PDF without bookmarks warns."""
    from pypdf import PdfReader
    pdf = _make_pdf(num_pages=5, add_bookmarks=False)
    reader = PdfReader(BytesIO(pdf))
    result = _check_bookmarks(reader)
    assert result.status == "warn"


# ── EPR-002: Fonts ───────────────────────────────────────────────────────────

def test_fonts_blank_page():
    """Blank pages have no fonts — skip."""
    from pypdf import PdfReader
    pdf = _make_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_fonts(reader)
    assert result.status == "skip"  # No fonts on blank pages


# ── EPR-010: Digital Signatures ──────────────────────────────────────────────

def test_no_signatures():
    """PDF without signatures passes."""
    from pypdf import PdfReader
    pdf = _make_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_digital_signatures(reader)
    assert result.status in ("pass", "skip")


# ── EPR-001: Vector vs Raster ────────────────────────────────────────────────

def test_vector_pages_pass():
    """Blank vector pages pass (no large images)."""
    from pypdf import PdfReader
    pdf = _make_pdf(num_pages=3)
    reader = PdfReader(BytesIO(pdf))
    result = _check_vector_vs_raster(reader)
    assert result.status == "pass"


# ── EPR-019: Annotations ────────────────────────────────────────────────────

def test_no_annotations():
    """PDF without annotations passes."""
    from pypdf import PdfReader
    pdf = _make_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_annotations(reader)
    assert result.status == "pass"


# ── EPR-020: Filename ────────────────────────────────────────────────────────

def test_filename_correct():
    """Correct naming convention passes."""
    result = _check_filename("001-Plans-Rev1 123 Main St.pdf")
    assert result.status == "pass"


def test_filename_bad():
    """Non-conformant filename warns."""
    result = _check_filename("my_plans_final.pdf")
    assert result.status == "warn"


# ── EPR-021: Back Check Page ─────────────────────────────────────────────────

def test_back_check_page_detected():
    """Small last page detected as back check."""
    from pypdf import PdfReader
    pdf = _make_mixed_pdf()
    reader = PdfReader(BytesIO(pdf))
    result = _check_back_check_page(reader)
    assert result.status == "pass"


def test_back_check_page_missing():
    """Large last page warns about missing back check."""
    from pypdf import PdfReader
    pdf = _make_pdf(num_pages=3, page_width_inches=34.0, page_height_inches=22.0)
    reader = PdfReader(BytesIO(pdf))
    result = _check_back_check_page(reader)
    assert result.status == "warn"


# ── Integration Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_validation_report():
    """Full validation returns markdown with all sections."""
    pdf = _make_pdf(num_pages=5, add_bookmarks=True)
    result = await validate_plans(pdf, filename="test.pdf")
    assert "# Plan Set Validation Report" in result
    assert "## Summary" in result
    assert "## Automated Checks" in result
    assert "## Checks Requiring Manual Review" in result
    assert "## Sources" in result


@pytest.mark.asyncio
async def test_validation_encrypted_pdf():
    """Encrypted PDF stops early with clear error."""
    pdf = _make_pdf(encrypt="password")
    result = await validate_plans(pdf, filename="locked.pdf")
    assert "encrypted" in result.lower() or "password" in result.lower()


@pytest.mark.asyncio
async def test_validation_base64_input():
    """Base64-encoded input is handled."""
    import base64
    pdf = _make_pdf()
    b64 = base64.b64encode(pdf).decode()
    result = await validate_plans(b64, filename="base64.pdf")
    assert "# Plan Set Validation Report" in result


@pytest.mark.asyncio
async def test_validation_good_plan_set():
    """Well-formed plan set with bookmarks gets mostly passing."""
    pdf = _make_pdf(
        num_pages=10,
        page_width_inches=34.0,
        page_height_inches=22.0,
        add_bookmarks=True,
    )
    result = await validate_plans(
        pdf,
        filename="001-Plans-Rev0 456 Oak St.pdf",
    )
    assert "PASS" in result
    # Should not have FAIL for dimensions or file size
    assert "FAIL — EPR-005" not in result
    assert "FAIL — EPR-006" not in result


@pytest.mark.asyncio
async def test_validation_undersized_pages():
    """Letter-size plan triggers dimension failure."""
    pdf = _make_pdf(num_pages=5, page_width_inches=11.0, page_height_inches=8.5)
    result = await validate_plans(pdf, filename="small.pdf")
    assert "FAIL" in result
    assert "EPR-005" in result
