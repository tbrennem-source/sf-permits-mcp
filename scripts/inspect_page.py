#!/usr/bin/env python3
"""Inspect the amlegal.com page structure to find the right content selectors."""

from playwright.sync_api import sync_playwright

url = "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-95527#JD_AB-093"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    page = context.new_page()
    page.goto(url, wait_until="networkidle", timeout=60000)

    # Try to find what elements contain the AB content
    # First, dump all element IDs that contain "AB" or "JD"
    ids = page.evaluate("""
        () => {
            const els = document.querySelectorAll('[id]');
            return Array.from(els)
                .map(e => ({id: e.id, tag: e.tagName, className: e.className}))
                .filter(e => e.id.includes('AB') || e.id.includes('JD') || e.id.includes('code'));
        }
    """)
    print("Elements with AB/JD/code IDs:")
    for item in ids[:30]:
        print(f"  {item['tag']}#{item['id']} class={item['className'][:80]}")

    # Look at the main content containers
    containers = page.evaluate("""
        () => {
            const selectors = [
                '#codebankContent', '.content-area', '#codebank',
                'main', 'article', '.code-content', '#content',
                '.chunk-content', '.code-chunk', '#codebankMain',
                '.codebank', '#codeContent'
            ];
            return selectors.map(s => {
                const el = document.querySelector(s);
                return {
                    selector: s,
                    found: !!el,
                    tag: el ? el.tagName : null,
                    childCount: el ? el.children.length : 0,
                    textLen: el ? el.innerText.length : 0
                };
            });
        }
    """)
    print("\nContainer search:")
    for c in containers:
        print(f"  {c['selector']}: found={c['found']}, tag={c['tag']}, children={c['childCount']}, textLen={c['textLen']}")

    # Find the actual content structure
    structure = page.evaluate("""
        () => {
            const body = document.body;
            function describeEl(el, depth=0) {
                if (depth > 3) return [];
                const results = [];
                for (const child of el.children) {
                    const info = {
                        tag: child.tagName,
                        id: child.id || '',
                        class: child.className ? child.className.toString().substring(0, 80) : '',
                        textLen: child.innerText ? child.innerText.length : 0,
                        childCount: child.children.length,
                    };
                    results.push({...info, depth});
                    if (child.children.length > 0 && child.children.length < 20 && depth < 3) {
                        results.push(...describeEl(child, depth + 1));
                    }
                }
                return results;
            }
            return describeEl(body);
        }
    """)
    print("\nPage structure (top levels):")
    for item in structure[:60]:
        indent = "  " * (item['depth'] + 1)
        id_str = f"#{item['id']}" if item['id'] else ""
        class_str = f".{item['class'].split()[0]}" if item['class'] else ""
        print(f"{indent}{item['tag']}{id_str}{class_str} children={item['childCount']} text={item['textLen']}")

    # Look for the specific AB-093 anchor/heading
    ab_elements = page.evaluate("""
        () => {
            // Find elements that directly contain "AB-093" text
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                { acceptNode: (node) => node.textContent.includes('NO. AB-093') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT }
            );
            const results = [];
            while (walker.nextNode()) {
                const node = walker.currentNode;
                const parent = node.parentElement;
                results.push({
                    tag: parent.tagName,
                    id: parent.id || '',
                    className: parent.className ? parent.className.toString().substring(0, 80) : '',
                    parentTag: parent.parentElement ? parent.parentElement.tagName : '',
                    parentId: parent.parentElement ? parent.parentElement.id : '',
                    text: node.textContent.trim().substring(0, 100)
                });
            }
            return results;
        }
    """)
    print("\nElements containing 'NO. AB-093':")
    for item in ab_elements:
        print(f"  {item['tag']}#{item['id']} .{item['className']} parent={item['parentTag']}#{item['parentId']}")
        print(f"    text: {item['text']}")

    browser.close()
