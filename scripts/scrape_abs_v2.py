#!/usr/bin/env python3
"""
Scrape Administrative Bulletins AB-093, AB-110, AB-112 from amlegal.com
using Playwright. Uses DOM range extraction between anchor elements for clean content.
"""

import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


# Target ABs with their known URLs
AB_TARGETS = {
    "AB-093": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-95527#JD_AB-093",
        "title": "Implementation of Green Building Regulations",
        "end_anchor": "JD_AB-094",  # Next AB on this page
    },
    "AB-110": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-96476#JD_AB-110",
        "title": "Building Facade Inspection and Maintenance",
        "end_anchor": "JD_AB-111",  # Next AB on this page
    },
    "AB-112": {
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-100198#JD_AB-112",
        "title": "Implementation of All Electric New Construction Regulations",
        "end_anchor": "JD_AB-113",  # Next AB on this page
    },
}

OUTPUT_DIR = Path("/Users/timbrenneman/AIprojects/sf-permits-mcp/data/knowledge/tier3")


def clean_text(raw_text: str, ab_id: str) -> str:
    """Clean the extracted text: normalize whitespace, trim the header line."""
    lines = raw_text.split("\n")

    # The first line is usually "AB-093  Implementation of Green Building..."
    # which is the section heading. We want to keep that.
    # Then find "NO. AB-XXX" which is the start of the formal bulletin

    cleaned = []
    prev_blank = False
    found_no = False

    for line in lines:
        stripped = line.strip()

        # Skip everything before "NO. AB-XXX" (the TOC heading line)
        if not found_no:
            if stripped.startswith(f"NO. {ab_id}") or stripped.startswith("NO. AB-"):
                found_no = True
            else:
                continue

        if not stripped:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            # Clean up tab/space formatting
            line_clean = stripped.replace("\t", "  ")
            cleaned.append(line_clean)
            prev_blank = False

    # Remove trailing blanks
    while cleaned and not cleaned[-1]:
        cleaned.pop()

    # Remove "Originally Signed by" duplicates and trailing metadata if present
    # Also remove the amlegal disclaimer at the end
    final_lines = []
    for line in cleaned:
        if line.startswith("Disclaimer: This Code of Ordinances"):
            break
        if line.startswith("Hosted by: American Legal Publishing"):
            break
        if line.startswith("Back to Code Library"):
            break
        final_lines.append(line)

    # Remove trailing blanks again
    while final_lines and not final_lines[-1]:
        final_lines.pop()

    return "\n".join(final_lines)


def extract_ab_content(page, ab_id: str, end_anchor: str) -> str:
    """
    Extract AB content using DOM range between the AB's anchor and the next AB's anchor.
    """
    start_anchor_id = f"JD_{ab_id}"

    # First, list all anchors on the page to verify
    anchors = page.evaluate("""
        (args) => {
            const anchors = document.querySelectorAll('a[id^="JD_AB-"]');
            return Array.from(anchors).map(a => a.id);
        }
    """, {})
    print(f"  Available anchors: {anchors}")

    # Extract text between the two anchors using DOM Range
    result = page.evaluate("""
        (args) => {
            const startId = args.startId;
            const endId = args.endId;

            const startAnchor = document.querySelector('#' + startId);
            if (!startAnchor) return {error: 'Start anchor not found: ' + startId};

            const endAnchor = document.querySelector('#' + endId);

            const range = document.createRange();
            range.setStartBefore(startAnchor);

            if (endAnchor) {
                range.setEndBefore(endAnchor);
            } else {
                // No end anchor - go to the end of the parent section
                // Find the section container
                let section = startAnchor.closest('.Section') || startAnchor.closest('[id^="section-"]');
                if (section) {
                    range.setEndAfter(section);
                } else {
                    // Last resort: get everything after start in the codecontent
                    const codecontent = document.querySelector('#codecontent');
                    if (codecontent) {
                        range.setEndAfter(codecontent);
                    } else {
                        return {error: 'Could not determine end boundary'};
                    }
                }
            }

            const fragment = range.cloneContents();
            const div = document.createElement('div');
            div.appendChild(fragment);
            return {text: div.innerText, length: div.innerText.length};
        }
    """, {"startId": start_anchor_id, "endId": end_anchor})

    if "error" in result:
        raise RuntimeError(result["error"])

    print(f"  Extracted {result['length']} chars via DOM range")
    return result["text"]


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
                print(f"  Navigating to {info['url']}")
                page.goto(info["url"], wait_until="networkidle", timeout=60000)

                # Wait a moment for React to fully render
                page.wait_for_timeout(2000)

                raw_text = extract_ab_content(page, ab_id, info["end_anchor"])
                cleaned = clean_text(raw_text, ab_id)

                outfile = output_dir / f"{ab_id}.txt"
                outfile.write_text(cleaned, encoding="utf-8")

                print(f"  Cleaned text length: {len(cleaned)} chars")
                print(f"  Saved to: {outfile}")

                # Show first and last few lines for verification
                all_lines = cleaned.split("\n")
                print(f"  First 8 lines:")
                for line in all_lines[:8]:
                    print(f"    | {line[:120]}")
                print(f"  ...")
                print(f"  Last 5 lines:")
                for line in all_lines[-5:]:
                    print(f"    | {line[:120]}")

                results[ab_id] = {
                    "status": "success",
                    "chars": len(cleaned),
                    "file": str(outfile),
                }

                # Brief pause between requests
                time.sleep(2)

            except Exception as e:
                print(f"  ERROR scraping {ab_id}: {e}")
                import traceback
                traceback.print_exc()
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

    if any(r["status"] != "success" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
