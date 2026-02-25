---
name: qa-mobile
description: "Tests sfpermits.ai at mobile and tablet viewports using Playwright. Checks layout, overflow, navigation, and form usability at 375px and 768px. Invoke for any sprint QA pass covering responsive behavior."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# QA Agent: Mobile Viewport Testing

## Purpose
Verify that all major pages render correctly at phone (375px) and tablet (768px) widths with no horizontal overflow, functional navigation, and usable forms.

## When to Use
- After any sprint touching templates, CSS, or layout
- As part of RELAY QA loop when responsive behavior is relevant
- After a deploy when visual regression on mobile is a concern

## Viewports
- **Phone**: 375 x 812 (iPhone SE/X size)
- **Tablet**: 768 x 1024 (iPad portrait)

## Checks

All checks use Playwright headless Chromium with explicit viewport configuration via `browser.new_context(viewport={"width": W, "height": H})`.

### Phone (375px) Checks

#### P1. Landing Page — No Horizontal Overflow
- Load `/` at 375x812
- PASS if: `document.body.scrollWidth <= 375` (no horizontal scrollbar), page content fits within viewport
- FAIL if: horizontal overflow detected, content clipped or hidden requiring horizontal scroll

#### P2. Landing Page — Above-the-Fold Content Visible
- Screenshot full page at 375x812
- PASS if: headline/value prop and at least one CTA visible in first 812px of height
- FAIL if: critical content pushed below fold

#### P3. Search Form Usable on Phone
- On `/` or `/search`, tap search input at 375px
- PASS if: input receives focus, keyboard would activate, no z-index or overlay blocking it
- FAIL if: input not tappable, covered by other element

#### P4. Navigation Works on Phone
- At 375px, check mobile navigation (hamburger menu or collapsed nav)
- PASS if: nav is accessible (hamburger opens menu, or nav links visible), no broken toggle
- FAIL if: nav is completely inaccessible, toggle broken, links invisible

#### P5. Morning Brief — No Overflow
- Load `/brief` at 375px (requires auth — use test-login if TESTING=1 is available, skip if not)
- PASS if: content fits within 375px width, tables or cards scroll vertically not horizontally
- FAIL if: fixed-width tables break layout, content overflows

#### P6. Search Results Readable at Phone
- Submit a search and view results at 375px
- PASS if: each result card is readable, text not truncated to the point of being useless, links tappable
- FAIL if: result cards overflow, text completely cut off, links too small to tap

### Tablet (768px) Checks

#### T1. Landing Page — No Horizontal Overflow
- Load `/` at 768x1024
- PASS if: `document.body.scrollWidth <= 768`
- FAIL if: horizontal overflow detected

#### T2. Landing Page — Layout Appropriate for Tablet
- Screenshot at 768x1024
- PASS if: content uses available space (not a narrow phone-width column centered with huge margins, unless that's intentional design)
- FAIL if: layout is clearly broken (overlapping elements, text running off edge)

#### T3. Admin Dashboard at Tablet
- Load `/admin/dashboard` at 768px (skip if no admin access)
- PASS if: dashboard sections visible, no overflow, data tables scroll horizontally if needed (not the page)
- FAIL if: layout broken, critical sections hidden

#### T4. Plan Analysis Upload at Tablet
- Load `/analyze-plans` at 768px
- PASS if: upload interface visible and usable
- FAIL if: upload form broken or inaccessible

### Screenshots (required for all checks)

Save screenshots for each viewport/page combination:
- `qa-results/screenshots/[session-id]/mobile/phone-landing.png`
- `qa-results/screenshots/[session-id]/mobile/phone-search-results.png`
- `qa-results/screenshots/[session-id]/mobile/phone-nav.png`
- `qa-results/screenshots/[session-id]/mobile/tablet-landing.png`
- `qa-results/screenshots/[session-id]/mobile/tablet-admin.png`

Use `page.screenshot(path=..., full_page=True)` for full-page captures.

## Tools
- Playwright headless Chromium with explicit viewport settings
- `browser.new_context(viewport={"width": W, "height": H})` for each viewport
- JavaScript `document.body.scrollWidth` evaluation for overflow detection
- Screenshots saved to `qa-results/screenshots/[session-id]/mobile/`

## Overflow Detection Script

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for width, height, label in [(375, 812, "phone"), (768, 1024, "tablet")]:
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.goto(BASE_URL)
        scroll_width = page.evaluate("document.body.scrollWidth")
        overflow = scroll_width > width
        print(f"{label}: scrollWidth={scroll_width}, overflow={overflow}")
        page.screenshot(path=f"qa-results/screenshots/{SESSION_ID}/mobile/{label}-landing.png", full_page=True)
        context.close()
    browser.close()
```

## Output Format

Write results to `qa-results/[session-id]-mobile-qa.md`:

```
# Mobile QA Results — [date]

| # | Viewport | Check | Status | Notes |
|---|----------|-------|--------|-------|
| P1 | 375px | No horizontal overflow | PASS | scrollWidth=375 |
| P2 | 375px | Above-fold content | PASS | |
...

Screenshots: qa-results/screenshots/[session-id]/mobile/
```

Mark each check PASS, FAIL, or SKIP (with reason for SKIP).
Any FAIL triggers a RELAY loop fix attempt (max 3 tries, then BLOCKED).

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
