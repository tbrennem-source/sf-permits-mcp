#!/usr/bin/env python3
"""Download and extract text from SF DBI Administrative Bulletins."""

import json
import os
import re
import sys
import time
import tempfile
from pathlib import Path

import pdfplumber
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("data/knowledge/tier3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Priority ABs we want
PRIORITY_ABS = ["AB-004", "AB-005", "AB-032", "AB-093", "AB-110", "AB-112"]

# Known direct PDF URLs from web search results
KNOWN_URLS = {
    "AB-110": "https://media.api.sf.gov/documents/AB-110_with_Attachments.pdf",
}

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF using pdfplumber."""
    text_parts = []
    page_count = 0
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        print(f"  Error extracting text: {e}", flush=True)
    return "\n\n".join(text_parts), page_count


def download_pdf_with_playwright(page, url, save_path):
    """Download a PDF using playwright navigation."""
    try:
        print(f"  Downloading from: {url}", flush=True)
        response = page.goto(url, wait_until="networkidle", timeout=30000)
        if response and response.status == 200:
            content = response.body()
            if len(content) > 500 and content[:5] == b'%PDF-':
                with open(save_path, 'wb') as f:
                    f.write(content)
                print(f"  Downloaded {len(content)} bytes", flush=True)
                return True
            else:
                print(f"  Response doesn't look like a PDF ({len(content)} bytes, starts with {content[:20]})", flush=True)
        else:
            status = response.status if response else "no response"
            print(f"  Failed with status: {status}", flush=True)
    except Exception as e:
        print(f"  Download error: {e}", flush=True)
    return False


def try_media_api_patterns(page, ab_num, save_path):
    """Try various media.api.sf.gov URL patterns."""
    # Extract just the number part (e.g., "004" from "AB-004")
    num = ab_num.split("-")[1]
    num_no_leading_zeros = str(int(num))

    patterns = [
        f"https://media.api.sf.gov/documents/{ab_num}.pdf",
        f"https://media.api.sf.gov/documents/AB-{num_no_leading_zeros}.pdf",
        f"https://media.api.sf.gov/documents/{ab_num}_with_Attachments.pdf",
        f"https://media.api.sf.gov/documents/AB_{num}.pdf",
        f"https://media.api.sf.gov/documents/AB{num}.pdf",
    ]

    for url in patterns:
        if download_pdf_with_playwright(page, url, save_path):
            return True
    return False


def try_sfgov_legacy_patterns(page, ab_num, save_path):
    """Try legacy sfdbi.org/sfgov.org URL patterns."""
    num = ab_num.split("-")[1]
    num_no_leading_zeros = str(int(num))

    patterns = [
        f"https://sfdbi.org/sites/default/files/{ab_num}.pdf",
        f"https://sfdbi.org/sites/default/files/FileCenter/Documents/{ab_num}.pdf",
        f"https://www.sfgov.org/sfc/sites/default/files/ESIP/FileCenter/Documents/{ab_num}.pdf",
        f"https://sfdbi.org/Modules/ShowDocument.aspx?documentid={num_no_leading_zeros}",
    ]

    for url in patterns:
        if download_pdf_with_playwright(page, url, save_path):
            return True
    return False


def scrape_sf_gov_for_ab_links(page):
    """Navigate sf.gov DBI page and extract AB links."""
    print("\n=== Scraping sf.gov for Administrative Bulletin links ===", flush=True)
    found_urls = {}

    # First warm up on sf.gov homepage
    print("Warming up browser on sf.gov...", flush=True)
    page.goto("https://sf.gov", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    # Try the DBI main page
    urls_to_try = [
        "https://www.sf.gov/departments--department-building-inspection",
        "https://www.sf.gov/building-inspection-division",
        "https://www.sf.gov/resource/2022/information-sheets-dbi",
    ]

    for url in urls_to_try:
        print(f"\nChecking: {url}", flush=True)
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Look for all links containing "AB-" or "administrative-bulletin"
            links = page.query_selector_all("a[href]")
            for link in links:
                href = link.get_attribute("href")
                if href and ("AB-" in href or "ab-" in href or "administrative-bulletin" in href):
                    text = link.inner_text().strip()
                    for ab in PRIORITY_ABS:
                        num = ab.split("-")[1]
                        if ab in href or ab in text or f"AB-{int(num)}" in text or f"AB-{int(num)}" in href:
                            if not href.startswith("http"):
                                href = "https://www.sf.gov" + href if href.startswith("/") else href
                            found_urls[ab] = href
                            print(f"  Found {ab}: {href}", flush=True)
        except Exception as e:
            print(f"  Error on {url}: {e}", flush=True)

    return found_urls


def scrape_amlegal_for_ab_links(page):
    """Navigate amlegal code library and extract AB content/links."""
    print("\n=== Scraping amlegal.com for Administrative Bulletin links ===", flush=True)
    found_urls = {}

    try:
        page.goto("https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-93809",
                   wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Get all links on the page
        links = page.query_selector_all("a[href]")
        for link in links:
            href = link.get_attribute("href")
            text = link.inner_text().strip()
            if href:
                for ab in PRIORITY_ABS:
                    num = ab.split("-")[1]
                    # Match AB-004 or AB-4 patterns
                    if (ab in text or f"AB-{int(num):d}" in text or
                        ab.lower() in text.lower() or
                        ab in href or f"ab-{int(num)}" in href.lower()):
                        if not href.startswith("http"):
                            href = "https://codelibrary.amlegal.com" + href
                        found_urls[ab] = href
                        print(f"  Found {ab}: {text} -> {href}", flush=True)

        if not found_urls:
            print("  No matching links found on amlegal index page", flush=True)
            # Print first 20 links for debugging
            for i, link in enumerate(links[:30]):
                href = link.get_attribute("href")
                text = link.inner_text().strip()
                if text and "AB" in text.upper():
                    print(f"    Link {i}: '{text}' -> {href}", flush=True)

    except Exception as e:
        print(f"  Error: {e}", flush=True)

    return found_urls


def extract_amlegal_text(page, url, ab_num):
    """Extract text content from an amlegal.com AB page."""
    print(f"  Extracting text from amlegal page: {url}", flush=True)
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Try to get the main content
        content_el = page.query_selector("#content-main") or page.query_selector(".content") or page.query_selector("main")
        if content_el:
            text = content_el.inner_text()
            return text
        else:
            # Fallback: get body text
            text = page.inner_text("body")
            return text
    except Exception as e:
        print(f"  Error extracting from amlegal: {e}", flush=True)
    return ""


def main():
    results = {"success": [], "failed": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Phase 1: Scrape for links
        sf_gov_urls = scrape_sf_gov_for_ab_links(page)
        amlegal_urls = scrape_amlegal_for_ab_links(page)

        # Merge known URLs
        all_urls = {**KNOWN_URLS}
        all_urls.update(sf_gov_urls)
        # Don't override PDF URLs with amlegal HTML URLs
        for ab, url in amlegal_urls.items():
            if ab not in all_urls:
                all_urls[ab] = url

        print(f"\n=== Found URLs for {len(all_urls)}/{len(PRIORITY_ABS)} ABs ===", flush=True)
        for ab, url in sorted(all_urls.items()):
            print(f"  {ab}: {url}", flush=True)

        # Phase 2: Download and extract each AB
        print("\n=== Downloading and extracting ABs ===", flush=True)

        for ab_num in PRIORITY_ABS:
            print(f"\n--- Processing {ab_num} ---", flush=True)
            output_path = OUTPUT_DIR / f"{ab_num}.txt"

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            text = ""
            page_count = 0
            source = ""

            try:
                # Strategy 1: Try known/found direct PDF URL
                if ab_num in all_urls and all_urls[ab_num].endswith('.pdf'):
                    url = all_urls[ab_num]
                    if download_pdf_with_playwright(page, url, tmp_path):
                        text, page_count = extract_text_from_pdf(tmp_path)
                        source = url

                # Strategy 2: Try media.api.sf.gov patterns
                if not text:
                    print(f"  Trying media.api.sf.gov URL patterns...", flush=True)
                    if try_media_api_patterns(page, ab_num, tmp_path):
                        text, page_count = extract_text_from_pdf(tmp_path)
                        source = "media.api.sf.gov pattern"

                # Strategy 3: Try legacy sfgov patterns
                if not text:
                    print(f"  Trying legacy sfgov URL patterns...", flush=True)
                    if try_sfgov_legacy_patterns(page, ab_num, tmp_path):
                        text, page_count = extract_text_from_pdf(tmp_path)
                        source = "sfgov legacy pattern"

                # Strategy 4: Try amlegal HTML page
                if not text and ab_num in amlegal_urls:
                    url = amlegal_urls[ab_num]
                    text = extract_amlegal_text(page, url, ab_num)
                    if text:
                        page_count = 0  # Not a PDF
                        source = url

                # Strategy 5: Try amlegal known URL patterns
                if not text:
                    # Try constructed amlegal URLs
                    num = ab_num.split("-")[1]
                    amlegal_base = "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-"
                    # These are known node IDs from search results
                    known_amlegal_ids = {
                        "AB-004": "61052",
                        "AB-005": "61095",
                    }
                    if ab_num in known_amlegal_ids:
                        amlegal_url = amlegal_base + known_amlegal_ids[ab_num]
                        text = extract_amlegal_text(page, amlegal_url, ab_num)
                        if text:
                            source = amlegal_url

                if text and len(text.strip()) > 100:
                    output_path.write_text(text)
                    char_count = len(text)
                    print(f"  SUCCESS: {page_count} pages, {char_count} chars -> {output_path}", flush=True)
                    results["success"].append({
                        "id": ab_num,
                        "pages": page_count,
                        "chars": char_count,
                        "source": source,
                        "path": str(output_path)
                    })
                else:
                    print(f"  FAILED: Could not find or extract {ab_num}", flush=True)
                    results["failed"].append({"id": ab_num, "error": "No text extracted"})

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        browser.close()

    # Print summary
    print("\n" + "="*60, flush=True)
    print("DOWNLOAD SUMMARY", flush=True)
    print("="*60, flush=True)
    print(f"\nSuccessful: {len(results['success'])}/{len(PRIORITY_ABS)}", flush=True)
    for item in results["success"]:
        print(f"  {item['id']}: {item['pages']} pages, {item['chars']:,} chars", flush=True)
    if results["failed"]:
        print(f"\nFailed: {len(results['failed'])}/{len(PRIORITY_ABS)}", flush=True)
        for item in results["failed"]:
            print(f"  {item['id']}: {item['error']}", flush=True)

    # Save results JSON
    results_path = OUTPUT_DIR / "download_results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {results_path}", flush=True)

    return results


if __name__ == "__main__":
    main()
