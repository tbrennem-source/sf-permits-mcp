#!/usr/bin/env python3
"""Deeper inspection of AB content structure on amlegal.com."""

from playwright.sync_api import sync_playwright

url = "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-95527#JD_AB-093"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    page = context.new_page()
    page.goto(url, wait_until="networkidle", timeout=60000)

    # Look at #codecontent structure
    info = page.evaluate("""
        () => {
            const cc = document.querySelector('#codecontent');
            if (!cc) return {found: false};

            // Get direct children structure
            const children = [];
            for (const child of cc.children) {
                children.push({
                    tag: child.tagName,
                    id: child.id || '',
                    className: child.className ? child.className.toString().substring(0, 100) : '',
                    childCount: child.children.length,
                    textLen: child.innerText ? child.innerText.length : 0
                });
            }
            return {found: true, childCount: cc.children.length, children: children.slice(0, 20)};
        }
    """)
    print("codecontent structure:")
    print(f"  Found: {info['found']}, children: {info.get('childCount', 0)}")
    for c in info.get('children', []):
        print(f"  {c['tag']}#{c['id']} .{c['className']} children={c['childCount']} text={c['textLen']}")

    # Look at what's around JD_AB-093 anchor
    ab_context = page.evaluate("""
        () => {
            const anchor = document.querySelector('#JD_AB-093');
            if (!anchor) return {found: false};

            // Walk up to find the containing section
            let parent = anchor.parentElement;
            const parents = [];
            while (parent && parent !== document.body) {
                parents.push({
                    tag: parent.tagName,
                    id: parent.id || '',
                    className: parent.className ? parent.className.toString().substring(0, 100) : '',
                    textLen: parent.innerText ? parent.innerText.length : 0
                });
                parent = parent.parentElement;
            }

            // Get siblings of the anchor's parent container
            const container = anchor.parentElement;
            const siblings = [];
            let el = container;
            // Go back 2 siblings
            for (let i = 0; i < 2 && el.previousElementSibling; i++) {
                el = el.previousElementSibling;
            }
            // Now go forward
            for (let i = 0; i < 10 && el; i++) {
                siblings.push({
                    tag: el.tagName,
                    id: el.id || '',
                    className: el.className ? el.className.toString().substring(0, 100) : '',
                    childCount: el.children.length,
                    textPreview: el.innerText ? el.innerText.substring(0, 120).replace(/\\n/g, ' | ') : ''
                });
                el = el.nextElementSibling;
            }

            return {
                found: true,
                anchorTag: anchor.tagName,
                anchorParent: parents[0],
                parents: parents,
                siblings: siblings
            };
        }
    """)
    print("\nJD_AB-093 context:")
    print(f"  Found: {ab_context['found']}")
    if ab_context['found']:
        print(f"  Anchor tag: {ab_context['anchorTag']}")
        print(f"  Parents:")
        for p_info in ab_context.get('parents', [])[:5]:
            print(f"    {p_info['tag']}#{p_info['id']} .{p_info['className']} text={p_info['textLen']}")
        print(f"  Siblings around anchor:")
        for s in ab_context.get('siblings', []):
            print(f"    {s['tag']}#{s['id']} .{s['className']} children={s['childCount']}")
            print(f"      text: {s['textPreview'][:120]}")

    # Try to extract just the AB-093 content section
    # Find the content between JD_AB-093 and JD_AB-094 anchors
    ab_text = page.evaluate("""
        () => {
            const startAnchor = document.querySelector('#JD_AB-093');
            const endAnchor = document.querySelector('#JD_AB-094');
            if (!startAnchor) return {found: false, error: 'no start anchor'};

            // Collect all elements between the two anchors
            let el = startAnchor.parentElement;
            const texts = [];
            let charCount = 0;

            while (el && charCount < 500) {
                const text = el.innerText || '';
                texts.push(text.substring(0, 200));
                charCount += text.length;
                el = el.nextElementSibling;
                if (el && el.querySelector && el.querySelector('#JD_AB-094')) break;
                if (el && el.id === 'JD_AB-094') break;
            }

            return {
                found: true,
                textCount: texts.length,
                preview: texts.slice(0, 5)
            };
        }
    """)
    print("\nAB-093 content extraction attempt:")
    print(f"  {ab_text}")

    # Better approach: extract all text from between anchors using a range
    range_text = page.evaluate("""
        () => {
            const startAnchor = document.querySelector('#JD_AB-093');
            const endAnchor = document.querySelector('#JD_AB-094');
            if (!startAnchor || !endAnchor) return {error: 'anchors not found'};

            const range = document.createRange();
            range.setStartBefore(startAnchor);
            range.setEndBefore(endAnchor);

            const fragment = range.cloneContents();
            const div = document.createElement('div');
            div.appendChild(fragment);

            return {
                text: div.innerText.substring(0, 1000),
                fullLen: div.innerText.length
            };
        }
    """)
    print("\nRange-based extraction:")
    print(f"  Full length: {range_text.get('fullLen', 'N/A')}")
    print(f"  Preview: {range_text.get('text', range_text.get('error', 'unknown'))[:500]}")

    browser.close()
