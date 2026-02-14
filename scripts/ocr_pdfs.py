#!/usr/bin/env python3
"""OCR scanned PDF information sheets from SF DBI.

Processes all PDFs that produced 0-byte text files during initial extraction.
Uses tesseract OCR via pytesseract + pdf2image.
"""

import os
import sys
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

# Scanned PDFs that need OCR (extracted 0 chars with pdfplumber)
SCANNED_PDFS = [
    "G-01", "G-07", "G-12", "G-13", "G-14", "G-17", "G-23",
    "DA-04", "DA-09", "DA-12", "DA-14", "DA-15", "DA-19",
    "FS-04", "FS-05", "FS-07", "FS-12", "FS-13",
    "S-04", "S-09"
]

PDF_DIR = Path("/tmp")
KNOWLEDGE_DIR = Path("/Users/timbrenneman/AIprojects/sf-permits-mcp/data/knowledge")

# Map file labels to output directories
SERIES_MAP = {
    "G": "tier2/G-series",
    "DA": "tier2/DA-series",
    "FS": "tier2/FS-series",
    "S": "tier2/S-series"
}


def get_output_path(label: str) -> Path:
    """Get the output .txt path for a given PDF label."""
    # Special case: G-13 goes to tier1
    if label == "G-13":
        return KNOWLEDGE_DIR / "tier1" / "G-13-raw-text.txt"

    series = label.split("-")[0]
    subdir = SERIES_MAP.get(series, "tier2")
    return KNOWLEDGE_DIR / subdir / f"{label}.txt"


def ocr_pdf(pdf_path: Path, label: str) -> tuple[str, int]:
    """OCR a single PDF and return (text, page_count)."""
    print(f"  Converting {label} to images...", flush=True)
    try:
        images = convert_from_path(str(pdf_path), dpi=300)
    except Exception as e:
        print(f"  ERROR converting {label}: {e}", flush=True)
        return "", 0

    print(f"  {len(images)} page(s), running OCR...", flush=True)

    all_text = []
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='eng')
        all_text.append(f"--- Page {i+1} ---\n{text}")
        if (i + 1) % 5 == 0:
            print(f"    Page {i+1}/{len(images)} done", flush=True)

    full_text = "\n\n".join(all_text)
    return full_text, len(images)


def main():
    print(f"OCR Processing {len(SCANNED_PDFS)} scanned PDFs", flush=True)
    print(f"PDF source: {PDF_DIR}", flush=True)
    print(f"Output: {KNOWLEDGE_DIR}", flush=True)
    print("=" * 60, flush=True)

    results = []
    total_chars = 0
    total_pages = 0

    for label in SCANNED_PDFS:
        pdf_path = PDF_DIR / f"{label}.pdf"
        output_path = get_output_path(label)

        if not pdf_path.exists():
            print(f"\n[SKIP] {label}: PDF not found at {pdf_path}", flush=True)
            results.append((label, "SKIP", 0, 0))
            continue

        print(f"\n[OCR] {label} ({pdf_path.stat().st_size // 1024}K)", flush=True)

        text, pages = ocr_pdf(pdf_path, label)

        if not text.strip():
            print(f"  WARNING: OCR produced no text for {label}", flush=True)
            results.append((label, "EMPTY", 0, pages))
            continue

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(text)

        char_count = len(text)
        total_chars += char_count
        total_pages += pages
        results.append((label, "OK", char_count, pages))
        print(f"  -> {output_path.name}: {char_count:,} chars, {pages} pages", flush=True)

    # Summary
    print("\n" + "=" * 60, flush=True)
    print("OCR RESULTS SUMMARY", flush=True)
    print("=" * 60, flush=True)

    ok_count = sum(1 for _, status, _, _ in results if status == "OK")
    skip_count = sum(1 for _, status, _, _ in results if status == "SKIP")
    empty_count = sum(1 for _, status, _, _ in results if status == "EMPTY")

    for label, status, chars, pages in results:
        status_icon = {"OK": "✅", "SKIP": "⏭️", "EMPTY": "⚠️"}.get(status, "❓")
        print(f"  {status_icon} {label:8s} | {status:5s} | {chars:>8,} chars | {pages} pages", flush=True)

    print(f"\nProcessed: {ok_count} OK, {skip_count} skipped, {empty_count} empty", flush=True)
    print(f"Total: {total_chars:,} characters from {total_pages} pages", flush=True)


if __name__ == "__main__":
    main()
