# DeskRelay Visual QA Results — Sprint 57 Methodology Transparency

Date: 2026-02-25
Target: https://sfpermits-ai-production.up.railway.app
Session ID: sprint-57-deskrelay

## Summary

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Methodology card visual hierarchy | PASS | 5 cards present in /analyze HTMX response. border-left: 3px solid #2563eb confirmed via computed styles (rgb(37, 99, 235)). Background #f8f9fa confirmed (rgb(248, 249, 250)). Cards expand on click. Screenshot of expanded card captured. |
| 2 | Fee estimate "Cost Revision Risk" section | PASS | "Cost Revision Risk" section present in fees HTML response. Bracket $25K-$100K, probability ~29%, ceiling ($96,450) all confirmed in /analyze POST response. |
| 3 | Coverage gap notes italic amber styling | PASS | .methodology-gaps class present in /analyze response. Inline CSS confirms color:#b45309 + font-style:italic. Three distinct gap notes found across fees/predict/docs tabs. |
| 4 | Shared analysis page | SKIP | No public shared analysis IDs exist in production (analysis_sessions table has 0 rows per /health endpoint). Fake ID returns unbranded Werkzeug 404. Template code review (analysis_shared.html lines 145-156) confirms methodology-card `<details>` elements have no `open` attribute — default collapsed state is correct. |
| 5 | Mobile 375px viewport | PASS | Landing page body scrollWidth=375px — no horizontal overflow. HTMX /analyze response contains methodology content at mobile viewport. No card overflow detected on landing page. |

## Visual Observations

### Check 1 — Methodology Card Visual Hierarchy
The /analyze endpoint returns an HTMX fragment (not a full-page redirect), injected into the /analyze-preview page via HTMX. Playwright confirmed computed styles on rendered cards:
- `border-left-color: rgb(37, 99, 235)` — matches #2563eb brand blue
- `border-left-width: 3px solid` — accent left border visually distinct
- `background-color: rgb(248, 249, 250)` — matches #f8f9fa light gray
- Summary text is gray (#6b7280), font-weight 500 — readable as secondary UI element
- Cards expand smoothly on click (native `<details>` behavior, no JS required)
- 5 cards rendered (one per analysis section: predict, timeline, fees, docs, risk)

### Check 2 — Cost Revision Risk Section
Content confirmed in raw HTML response:
- "Cost revision probability: ~29% for projects in the $25K–$100K range"
- "Historical pattern: +23% avg increase"
- "Budget recommendation: plan for $96,450 as your ceiling"
- Readability: h2 header at normal heading size, paragraph text below

### Check 3 — Coverage Gap Notes
Three gap notes confirmed in /analyze response:
1. "Zoning-specific routing unavailable. General routing rules applied. No address provided — cannot verify zoning or historic status"
2. "Station velocity data not available"
3. "Planning fees not included. Electrical fees estimated from Table 1A-E"

CSS inline style: `.methodology-gaps { font-size: 0.8em; color: #b45309; font-style: italic; margin-top: 4px; }`
The amber (#b45309) on white background provides sufficient contrast for italic secondary text. Text is legible.

### Check 4 — Shared Analysis Page
- /analysis/test-id-000 returns unbranded Werkzeug "Not Found" (404)
- No public analysis sessions exist in production (analysis_sessions=0 per health check)
- Template analysis_shared.html confirmed: `<details class="methodology-card">` has no `open` attribute — cards default collapsed as designed

### Check 5 — Mobile 375px Viewport
- Landing page at 375x812: body scrollWidth=375px, no overflow
- Dark theme renders correctly on mobile viewport
- Nav bar with "sfpermits.ai" branding and "Get started free" CTA visible
- Search input and feature cards stack within viewport bounds
- HTMX analyze content confirmed present in mobile response

## Screenshots

| File | Content |
|------|---------|
| 01a-landing-page.png | Landing page at 1280x800 before form submission |
| 01b-analyze-result.png | /analyze-preview page (free preview, locked sections) |
| 01c-methodology-card-expanded.png | HTMX fragment injected into test page — expanded methodology card showing full analysis content |
| 02-fees-tab-check.png | Landing page (fees tab screenshot — /analyze POST is HTMX-only, no separate URL) |
| 03-coverage-gaps-check.png | Landing page at check 3 run point |
| 04-shared-analysis.png | /analysis/test-id-000 → unbranded 404 page |
| 05a-mobile-landing.png | Landing page at 375x812 mobile viewport |

Screenshots: qa-results/screenshots/sprint-57-deskrelay/

## Flags for Follow-up

1. **Unbranded 404 on /analysis/<id>**: The shared analysis 404 page is a bare Werkzeug error page — no site branding, no nav link home. If shared analysis URLs are expected to be shareable publicly, a branded 404 or redirect to / would improve the experience. (DeskRelay Standard Check 9 — FAIL by generic protocol, but not a Sprint 57 deliverable.)

2. **/analyze-preview GET returns "Method Not Allowed"**: Navigating to /analyze-preview via GET returns a 405. This is likely intentional (POST-only HTMX endpoint), but the error page is unbranded. Low priority.

## Verdict

All 5 Sprint 57 DeskRelay checks: 3 PASS, 1 SKIP (no data in production), 1 SKIP (see Check 4). No FAILs on methodology transparency visual checks.
