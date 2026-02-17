#!/usr/bin/env python3
"""
Scrape Administrative Bulletins AB-093, AB-110, AB-112 from amlegal.com
using Playwright. Extracts clean text content, stripping navigation and boilerplate.
"""

import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


# Target ABs with their known URLs from previous successful downloads
AB_TARGETS = {
    "AB-093": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-95527#JD_AB-093",
        "title": "Implementation of Green Building Regulations",
    },
    "AB-110": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-96476#JD_AB-110",
        "title": "Building Façade Inspection and Maintenance",
    },
    "AB-112": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-100198#JD_AB-112",
        "title": "Implementation of All Electric New Construction Regulations",
    },
}

OUTPUT_DIR = Path("/Users/timbrenneman/AIprojects/sf-permits-mcp/data/knowledge/tier3")


def clean_ab_text(raw_text: str, ab_id: str) -> str:
    """
    Clean scraped text by:
    1. Finding the start of the actual AB content (NO. AB-XXX line)
    2. Finding where the next AB or footer begins
    3. Stripping excess whitespace
    """
    lines = raw_text.split("\n")

    # Find the start: look for "NO. AB-XXX" pattern
    ab_num = ab_id.replace("AB-", "")
    start_patterns = [
        f"NO. {ab_id}",
        f"NO. AB-{ab_num}",
        f"{ab_id} ",
    ]

    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        for pat in start_patterns:
            if stripped.startswith(pat):
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is None:
        # Fallback: look for the AB title pattern more broadly
        for i, line in enumerate(lines):
            if re.search(rf'AB[- ]?0?{ab_num}\b', line.strip()):
                start_idx = i
                break

    if start_idx is None:
        print(f"  WARNING: Could not find start of {ab_id} content, returning full text")
        start_idx = 0

    # Find the end: look for the next AB heading or the disclaimer/footer
    end_idx = len(lines)
    next_ab_pattern = re.compile(r'^(AB-\d{3}\s+\w|NO\.\s+AB-\d{3})')
    footer_patterns = [
        "Disclaimer: This Code of Ordinances",
        "Hosted by: American Legal Publishing",
        "Back to Code Library",
    ]

    for i in range(start_idx + 5, len(lines)):  # skip a few lines past start
        stripped = lines[i].strip()

        # Check for next AB
        if next_ab_pattern.match(stripped):
            # Make sure it's a different AB, not the same one referenced in text
            next_ab_match = re.search(r'AB-(\d{3})', stripped)
            if next_ab_match and next_ab_match.group(0) != ab_id:
                # Only treat as boundary if it looks like a heading (short line, followed by NO. pattern)
                # Look ahead to see if next few lines have the NO./DATE/SUBJECT pattern
                lookahead = "\n".join(lines[i:min(i+10, len(lines))])
                if "DATE" in lookahead and "SUBJECT" in lookahead:
                    end_idx = i
                    break

        # Check for footer
        for fp in footer_patterns:
            if stripped.startswith(fp):
                end_idx = i
                break
        if end_idx != len(lines):
            break

    # Extract the content
    content_lines = lines[start_idx:end_idx]

    # Clean up: remove excessive blank lines, normalize whitespace
    cleaned = []
    prev_blank = False
    for line in content_lines:
        stripped = line.strip()
        if not stripped:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            # Remove tab characters used for formatting, replace with spaces
            line_clean = stripped.replace("\t", "  ")
            cleaned.append(line_clean)
            prev_blank = False

    # Remove trailing blanks
    while cleaned and not cleaned[-1]:
        cleaned.pop()

    return "\n".join(cleaned)


def scrape_ab(page, ab_id: str, url: str) -> str:
    """Navigate to an AB page and extract the text content."""
    print(f"  Navigating to {url}")
    page.goto(url, wait_until="networkidle", timeout=60000)

    # Wait for the content area to be present
    # amlegal.com uses a content div - try multiple selectors
    content_selectors = [
        "#codebankContent",
        ".content-area",
        "#codebank",
        "main",
        "article",
        ".code-content",
    ]

    content_el = None
    for selector in content_selectors:
        try:
            el = page.query_selector(selector)
            if el:
                content_el = el
                print(f"  Found content using selector: {selector}")
                break
        except Exception:
            continue

    if content_el:
        raw_text = content_el.inner_text()
    else:
        # Fallback: get body text
        print(f"  WARNING: No content container found, using body text")
        raw_text = page.inner_text("body")

    print(f"  Raw text length: {len(raw_text)} chars")
    return raw_text


def main():
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        results = {}

        for ab_id, info in AB_TARGETS.items():
            print(f"\n{'='*60}")
            print(f"Scraping {ab_id}: {info['title']}")
            print(f"{'='*60}")

            try:
                raw_text = scrape_ab(page, ab_id, info["url"])
                cleaned = clean_ab_text(raw_text, ab_id)

                outfile = output_dir / f"{ab_id}.txt"
                outfile.write_text(cleaned, encoding="utf-8")

                print(f"  Cleaned text length: {len(cleaned)} chars")
                print(f"  Saved to: {outfile}")

                # Show first few lines for verification
                preview_lines = cleaned.split("\n")[:10]
                print(f"  Preview:")
                for line in preview_lines:
                    print(f"    | {line[:100]}")

                results[ab_id] = {
                    "status": "success",
                    "chars": len(cleaned),
                    "file": str(outfile),
                }

                # Brief pause between requests
                time.sleep(2)

            except Exception as e:
                print(f"  ERROR scraping {ab_id}: {e}")
                results[ab_id] = {"status": "error", "error": str(e)}

        browser.close()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for ab_id, result in results.items():
        if result["status"] == "success":
            print(f"  {ab_id}: OK - {result['chars']} chars -> {result['file']}")
        else:
            print(f"  {ab_id}: FAILED - {result['error']}")

    # Return non-zero if any failures
    if any(r["status"] != "success" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
