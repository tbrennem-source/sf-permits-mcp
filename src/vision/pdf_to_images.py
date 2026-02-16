"""PDF-to-image conversion utilities for Claude Vision API.

Converts individual PDF pages to base64-encoded PNG images suitable
for sending to Claude's vision endpoint. Uses pdf2image (poppler)
for rendering.
"""

import base64
import logging
from io import BytesIO

from PIL import Image

logger = logging.getLogger(__name__)

# DPI for rendering — 150 balances quality vs size for title block reading.
# At 150 DPI, a 34"x22" Arch D sheet → ~5100x3300 px.
DEFAULT_DPI = 150

# Claude Vision auto-resizes to max 1568px on longest edge, so we
# pre-downsample to avoid sending unnecessarily large images.
MAX_DIMENSION = 1568


def _check_poppler() -> bool:
    """Check if poppler is installed (required by pdf2image)."""
    try:
        from pdf2image import convert_from_bytes  # noqa: F401
        return True
    except ImportError:
        return False


def pdf_page_to_base64(
    pdf_bytes: bytes,
    page_number: int,
    dpi: int = DEFAULT_DPI,
    max_dimension: int = MAX_DIMENSION,
) -> str:
    """Convert a single PDF page to a base64-encoded PNG string.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_number: 0-indexed page number.
        dpi: Rendering resolution.
        max_dimension: Max px on longest side (downsample if larger).

    Returns:
        Base64-encoded PNG image string (no ``data:`` prefix).

    Raises:
        ValueError: If page cannot be rendered.
        ImportError: If pdf2image/poppler is not installed.
    """
    from pdf2image import convert_from_bytes

    # pdf2image uses 1-indexed pages
    images = convert_from_bytes(
        pdf_bytes,
        dpi=dpi,
        first_page=page_number + 1,
        last_page=page_number + 1,
        fmt="png",
    )

    if not images:
        raise ValueError(f"Failed to render page {page_number}")

    img = images[0]

    # Downsample if needed
    w, h = img.size
    if max(w, h) > max_dimension:
        scale = max_dimension / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def pdf_pages_to_base64(
    pdf_bytes: bytes,
    page_numbers: list[int],
    dpi: int = DEFAULT_DPI,
) -> list[tuple[int, str]]:
    """Convert multiple PDF pages to base64 images.

    Processes one page at a time for memory safety.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_numbers: 0-indexed page numbers to convert.
        dpi: Rendering resolution.

    Returns:
        List of ``(page_number, base64_png)`` tuples.
    """
    results = []
    for pn in page_numbers:
        b64 = pdf_page_to_base64(pdf_bytes, pn, dpi)
        results.append((pn, b64))
    return results


def get_page_count(pdf_bytes: bytes) -> int:
    """Get total page count from PDF bytes without rendering."""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return len(reader.pages)
