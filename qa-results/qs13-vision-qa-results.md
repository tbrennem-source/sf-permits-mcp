# QS13 Vision QA Results
Generated: 2026-02-28
Agent: 4A (Vision QA Pass)

## Score Table

| Page | Desktop | Tablet | Phone | Avg | Status |
|------|---------|--------|-------|-----|--------|
| / (landing) | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /demo/guided | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /search?q=487+Noe+St | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/station-predictor | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/stuck-permit | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/what-if | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/cost-of-delay | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/entity-network | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /tools/revision-risk | 4/5 | 4/5 | 4/5 | 4.0 | PASS |
| /join-beta | PENDING | PENDING | PENDING | — | NOT DEPLOYED |
| /join-beta/thanks | PENDING | PENDING | PENDING | — | NOT DEPLOYED |
| /docs | PENDING | PENDING | PENDING | — | NOT DEPLOYED |
| /privacy | PENDING | PENDING | PENDING | — | NOT DEPLOYED |
| /terms | PENDING | PENDING | PENDING | — | NOT DEPLOYED |

## Visual Scoring Notes

### / (landing) — 4/5
- PASS: Dark obsidian background (#0a0a0f), teal accent on "distilled" headline
- PASS: Hero text uses --sans (IBM Plex Sans) light weight, wordmark uses --mono (JetBrains Mono)
- PASS: Showcase cards visible with correct signal color coding (amber warnings, teal accents)
- PASS: Mobile nav collapses to hamburger on phone; sub-row anchor links visible on tablet/desktop
- NOTE: Showcase section appears very dark at top — ambient hero glow intentional, not a defect
- NOTE: On desktop, showcase cards render at compressed thumbnail scale within the showcase frame — correct (this is the "what your AI sees" section showing a Claude.ai window mockup)

### /demo/guided — 4/5
- PASS: Clean structured page with dark cards, correct font hierarchy
- PASS: Navigation shows correct items (Search, Demo badge, Brief, Portfolio, Projects, More, Sign in)
- PASS: Section labels (HOW IT WORKS, INTELLIGENCE TOOLS, FOR PROFESSIONALS) use --mono uppercase correctly
- PASS: Tool cards use glass-card style, ghost CTAs with teal accent links
- PASS: Mobile layout stacks cleanly, all CTAs remain tappable
- NOTE: Minor — "How Amy uses sfpermits.ai" bulleted list uses standard sans, appropriate

### /search?q=487+Noe+St — 4/5 (expected error state, well styled)
- PASS: Shows expected "Something went wrong" error state (no DB connection locally)
- PASS: Error state uses correct dark theme, monospace wordmark, minimal nav
- PASS: Search bar populated with query, search icon visible
- NOTE: Expected behavior locally (DuckDB has no permit data). Not a defect.

### /tools/station-predictor — 4/5
- PASS: Dark card with "PERMIT NUMBER" label in --mono uppercase
- PASS: Input field styled with correct obsidian-light background
- PASS: "Analyze →" button uses ghost CTA style, teal text
- PASS: Results placeholder card shows example permit numbers as pill chips
- PASS: "Sign up free →" upsell CTA at bottom in --mono
- PASS: Mobile: button goes full-width, stacks cleanly below input

### /tools/stuck-permit — 4/5
- PASS: Identical structural pattern to station-predictor, consistent design language
- PASS: All elements correctly token-compliant from visual inspection
- PASS: Mobile layout identical quality to station-predictor

### /tools/what-if — 4/5
- PASS: Two-panel form (Project A / Project B) with correct dark card styling
- PASS: Labels use --mono uppercase, field labels use --sans
- PASS: "Compare projects →" button full-width, ghost CTA style
- PASS: Mobile: panels stack vertically (appropriate); no horizontal scroll
- NOTE: Chat icon bubble appears in bottom-right corner on all tool pages — intentional feedback widget

### /tools/cost-of-delay — 4/5
- PASS: Two-column form + results panel layout at desktop
- PASS: Select dropdown, text inputs all consistently styled in obsidian-light
- PASS: "Try demo" link in --mono
- PASS: Results panel shows empty state with --text-secondary copy
- NOTE: Minor — "optional" labels appear in lighter weight inline with field labels; readable and appropriate

### /tools/entity-network — 4/5
- PASS: Clean single-column input form + results placeholder
- PASS: "Analyze network →" button, "See demo: Smith Construction →" in correct mono style
- PASS: Mobile layout clean, input full-width, button full-width

### /tools/revision-risk — 4/5
- PASS: Form with permit type dropdown, neighborhood/project type inputs, review path dropdown
- PASS: "Assess revision risk →" button, results panel with empty state
- PASS: Mobile: all fields stack to full-width, dropdowns remain usable

## Missing / Not Yet Deployed Routes

These routes returned 404 and are pending deployment from T1-T3 agents:

- /join-beta — NOT DEPLOYED (404) — honeypot beta capture page (T1 task)
- /join-beta/thanks — NOT DEPLOYED (404) — confirmation page (T1 task)
- /docs — NOT DEPLOYED (404) — API documentation page (T2 task)
- /privacy — NOT DEPLOYED (404) — privacy policy page (T3 task)
- /terms — NOT DEPLOYED (404) — terms of service page (T3 task)

## Public Route Regression (HONEYPOT_MODE=0)

All tested against http://127.0.0.1:5111 with local dev server.

- PASS: / → 200
- PASS: /demo/guided → 200
- PASS: /health → 200
- PASS: /tools/station-predictor → 200
- PASS: /tools/stuck-permit → 200
- PASS: /tools/what-if → 200
- PASS: /tools/cost-of-delay → 200
- PASS: /tools/entity-network → 200
- PASS: /tools/revision-risk → 200
- PASS: /search → 200
- PASS: /methodology → 200
- PASS: /about-data → 200
- PASS: /join-beta → 404 (expected — not yet deployed)
- PASS: /docs → 404 (expected — not yet deployed)
- PASS: /privacy → 404 (expected — not yet deployed)
- PASS: /terms → 404 (expected — not yet deployed)

**Route regression: 16/16 PASS**

## Design Token Lint

```
Baseline (all templates): 1/5 — 1657 violations across 120 files
Changed templates this session: 0 (no template modifications by Agent 4A)
```

The 1/5 baseline lint score is a pre-existing condition across the full template suite (120 files, many predating the design system). Agent 4A made NO template changes — lint delta is 0. The QS13 new pages (when deployed from T1-T3) will be scored separately.

Per prod gate rules: The 1/5 baseline requires Tim review before prod promotion. This is a known pre-existing condition — not introduced by QS13 agents.

## Fixes Applied

None. Agent 4A is a read-only vision QA pass. No templates were modified.

All existing pages scored 4/5 — above the ≥3.0 PASS threshold. No pages scored ≤2.0 (no DeskRelay escalation required).

## Screenshots

All screenshots saved to: `qa-results/screenshots/qs13-vision/`

### Desktop (1440x900)
- qa-results/screenshots/qs13-vision/landing-desktop.png
- qa-results/screenshots/qs13-vision/demo-guided-desktop.png
- qa-results/screenshots/qs13-vision/search-results-desktop.png
- qa-results/screenshots/qs13-vision/tools-station-predictor-desktop.png
- qa-results/screenshots/qs13-vision/tools-stuck-permit-desktop.png
- qa-results/screenshots/qs13-vision/tools-what-if-desktop.png
- qa-results/screenshots/qs13-vision/tools-cost-of-delay-desktop.png
- qa-results/screenshots/qs13-vision/tools-entity-network-desktop.png
- qa-results/screenshots/qs13-vision/tools-revision-risk-desktop.png
- qa-results/screenshots/qs13-vision/join-beta-desktop.png (404)
- qa-results/screenshots/qs13-vision/join-beta-thanks-desktop.png (404)
- qa-results/screenshots/qs13-vision/docs-desktop.png (404)
- qa-results/screenshots/qs13-vision/privacy-desktop.png (404)
- qa-results/screenshots/qs13-vision/terms-desktop.png (404)

### Tablet (768x1024)
- qa-results/screenshots/qs13-vision/landing-tablet.png
- qa-results/screenshots/qs13-vision/demo-guided-tablet.png
- qa-results/screenshots/qs13-vision/search-results-tablet.png
- qa-results/screenshots/qs13-vision/tools-station-predictor-tablet.png
- qa-results/screenshots/qs13-vision/tools-stuck-permit-tablet.png
- qa-results/screenshots/qs13-vision/tools-what-if-tablet.png
- qa-results/screenshots/qs13-vision/tools-cost-of-delay-tablet.png
- qa-results/screenshots/qs13-vision/tools-entity-network-tablet.png
- qa-results/screenshots/qs13-vision/tools-revision-risk-tablet.png

### Phone (375x812)
- qa-results/screenshots/qs13-vision/landing-phone.png
- qa-results/screenshots/qs13-vision/demo-guided-phone.png
- qa-results/screenshots/qs13-vision/search-results-phone.png
- qa-results/screenshots/qs13-vision/tools-station-predictor-phone.png
- qa-results/screenshots/qs13-vision/tools-stuck-permit-phone.png
- qa-results/screenshots/qs13-vision/tools-what-if-phone.png
- qa-results/screenshots/qs13-vision/tools-cost-of-delay-phone.png
- qa-results/screenshots/qs13-vision/tools-entity-network-phone.png
- qa-results/screenshots/qs13-vision/tools-revision-risk-phone.png

## Summary

**Overall verdict: PASS for all deployed pages.**

- 9 existing pages screenshotted at 3 viewports each = 27 screenshots of live pages
- 5 QS13 new pages = NOT YET DEPLOYED (pending T1-T3 merge) — 404 as expected
- All deployed pages score 4/5 — minor deviations only, no trust-breaking issues
- Route regression: 16/16 PASS (all expected routes return correct status codes)
- Design lint delta: 0 (Agent 4A made no template changes)
- No DeskRelay escalation required (no pages scored ≤2.0)
- Visual consistency is strong across desktop/tablet/phone viewports
- All tool pages follow a consistent glass-card + input + results-placeholder pattern

**Pending (after T1-T3 merge):**
- Re-screenshot /join-beta, /join-beta/thanks, /docs, /privacy, /terms
- Score those pages and update this file or write qs13-vision-qa-results-round2.md
