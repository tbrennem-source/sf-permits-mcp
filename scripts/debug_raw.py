#!/usr/bin/env python3
"""Debug: show the raw extracted text for AB-093."""

from playwright.sync_api import sync_playwright

url = "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-95527#JD_AB-093"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    # Wait for content to render
    page.wait_for_selector('#JD_AB-093', timeout=30000)
    page.wait_for_timeout(3000)

    result = page.evaluate("""
        () => {
            const startAnchor = document.querySelector('#JD_AB-093');
            const endAnchor = document.querySelector('#JD_AB-094');
            const range = document.createRange();
            range.setStartBefore(startAnchor);
            range.setEndBefore(endAnchor);
            const fragment = range.cloneContents();
            const div = document.createElement('div');
            div.appendChild(fragment);
            return div.innerText;
        }
    """)

    # Show first 2000 chars with repr to see exact formatting
    print("First 2000 chars (repr):")
    print(repr(result[:2000]))
    print()
    print("---")
    print("First 50 lines:")
    for i, line in enumerate(result.split("\n")[:50]):
        print(f"  [{i:3d}] {repr(line)}")

    browser.close()
