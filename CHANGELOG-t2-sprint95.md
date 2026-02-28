# Sprint 95 T2 — Search Result UX Fixes

## What was fixed

### ISO Timestamp → Human-Readable Dates
- Added `_fmt_date()` helper in `src/tools/permit_lookup.py` that converts any ISO date
  (including `2025-04-28T12:53:40.000`) to `Apr 28, 2025` format
- Applied to all date fields in `_format_permit_list`, `_format_permit_detail`, activity
  summary section, `_format_addenda`, `_format_planning_records`, `_format_boiler_permits`

### Mixed-Case Permit Types → Title Case
- Added `_title_permit_type()` helper in `src/tools/permit_lookup.py` that normalizes
  permit type strings to Title Case (e.g., `"otc alterations permit"` → `"Otc Alterations Permit"`)
- Applied to all `permit_type_definition` rendering in the main table, detail view, and activity sections
- Status field also title-cased in table output (`"issued"` → `"Issued"`)

### Cost Field "—" → Explanatory Note
- When any permit in a list has no cost estimate, a footnote is added below the table:
  *"Cost shows — for permit types where SF DBI does not require a cost estimate (e.g., electrical, plumbing, and mechanical permits)."*
- Footnote only appears when needed; suppressed when all permits have costs

### Template-Level Jinja2 Filters
- Added `format_date` Jinja2 filter to `web/app.py` for ISO → human-readable date in templates
- Added `title_permit` Jinja2 filter to `web/app.py` for title-casing permit types in templates
- Applied `| format_date` to `routing_latest_date` in `web/templates/search_results.html`
- Applied `| title_permit` to `latest_permit_type` in `web/templates/search_results.html`

## Files changed
- `src/tools/permit_lookup.py` — added helpers, applied to all formatter functions
- `web/app.py` — added `format_date` and `title_permit` Jinja2 template filters
- `web/templates/search_results.html` — applied new filters to intel panel display
- `tests/test_search_ux_fixes.py` — 32 new tests (all passing)
- `tests/test_permit_lookup.py` — updated 2 assertions to expect title-cased output

## Test results
- 32 new tests: all pass
- Full suite: 4463 passed, 2 skipped/xfailed baseline unchanged

## Design lint
- Score: 5/5 (no violations)

---

# CHANGELOG — T2 Sprint 95 Agent 2B

## Station Predictor + Stuck Permit Polish

### Changes

**web/templates/tools/station_predictor.html**
- Updated primary demo permit chip from `202501015257` to `202509155257`
- Added `buildStalledBanner()` — surfaces a visible amber warning banner with DBI phone number when the API response indicates the permit is stalled (>60 days, STALLED keyword in markdown)
- Improved result header layout: permit number and "Station Analysis" label rendered inline (flex row) for tighter visual hierarchy
- Improved empty state hint copy to explicitly describe routing prediction, dwell times, and next stations
- Added `parseStalledStatus()` helper

**web/templates/tools/stuck_permit.html**
- Updated primary demo permit chip from `202501015257` to `202509155257`
- Improved phone linkification: tel: links now use `--accent` color + `font-weight:500` for prominence
- Added URL linkification in contact lines (regex match on `https?://` URLs, opens in `_blank` with `rel="noopener"`)
- Added collapsible "Full diagnostic report" section: when structured content (block cards + playbook steps) is parsed successfully, the raw markdown is hidden behind an expandable toggle button instead of showing twice
- Updated empty state hint copy to mention intervention playbook and agency contacts

**web/static/js/gantt-interactive.js**
- Fixed `gantt-station-badge` placement: moved inside `gantt-station-main` div so badge renders inline with station name and meta, not below the row

**tests/test_tool_ux_station_stuck.py** (NEW — 87 tests)
- `TestStationPredictorUX`: 27 tests covering pre-fill, loading state, empty state, Gantt interactivity, stalled banner, results display
- `TestStuckPermitUX`: 33 tests covering pre-fill, loading state, empty state, severity dashboard, block cards, playbook parsing, phone/URL linkification, timeline impact, collapsible report
- `TestGanttInteractiveJS`: 16 tests covering module exports, badge placement, event wiring, accessibility, detail panel, animations
- `TestCrossTemplateConsistency`: 10 tests verifying both templates share consistent UX patterns (demo chips, pre-fill, signal colors, CSP nonces)

### Test Results
- 87 new tests: all passing
- Design lint: 5/5 on templates (0 new violations introduced; 5 pre-existing medium violations in gantt-interactive.js are architectural, use CSS custom properties at runtime)

---

# CHANGELOG — T2 Sprint 95 (Tool UX Polish)

## Agent: T2 — entity_network, revision_risk, what_if, cost_of_delay polish

### Critical Fix: revision_risk.html — missing style block
The revision_risk.html template was rendering broken because the entire `<style nonce="{{ csp_nonce }}">` opening tag was absent. CSS was floating as bare text after the `<link>` tag, causing the page to render with all CSS as visible text. Fixed by rewriting the template with a proper `<head>` structure.

### revision_risk.html — full UX rebuild
- **Redesigned input**: Changed from `permit-number-input` to `permit-type` select + optional neighborhood/project_type/review_path fields — matching the actual `revision_risk()` MCP tool signature
- **?permit_type= pre-fill**: URL param auto-fills select and triggers analysis
- **Two-column layout**: Sticky left form, right results panel (matches cost_of_delay.html pattern)
- **Loading skeleton**: 3-row skeleton while analysis is in flight
- **Empty state**: Centered state with demo link (?permit_type=alterations&neighborhood=Mission)
- **SVG risk gauge**: Half-circle arc SVG with stroke-dasharray animation; arc color = red/amber/green
- **Graceful 404**: If /api/revision-risk returns 404, shows helpful message suggesting What-If Simulator
- **Lint**: 5/5

### entity_network.html — UX improvements
- **?address= pre-fill**: Reads `?address=` or `?q=` URL params, auto-populates input, auto-runs
- **Loading skeleton**: Separate loading-area div with skeleton rows
- **Empty state**: Dedicated div with demo link (?address=Smith+Construction)
- **Network graph visualization**: Center node badge, connection rows, shared permit counts
- **Network stats row**: 3 stat cards (Connected entities, Relationships, Hops)
- **Lint**: 5/5

### Tests
- Created `tests/test_tool_ux_remaining.py`: 82 new tests
- Updated `tests/test_tools_new.py`: 7 assertions updated to match new designs

---

# CHANGELOG — T2 Sprint 95 (Auth + Supporting Pages UX)

## Agent 2D — auth_login, beta_request, demo, consultants polish

### demo.html
- Mobile overflow fix: added `.callout { display: block; max-width: 100%; box-sizing: border-box; }` and `.arch-grid { grid-template-columns: 1fr; }` at 480px
- Rewrote all 6 callout annotations to use user-facing language (removed internal refs: dataset IDs, module names)
- CTA copy: "Ready to search your property?" with cleaner supporting text
- **Security fix**: Removed hardcoded `?invite_code=friends-gridcare` from CTA link — this exposed an invite code publicly, bypassing the beta gate

### auth_login.html
- Added `.auth-trust` trust signals row: "no password · no credit card · SF permit data"
- Tightened subtitle copy for clarity

### beta_request.html
- Added `.auth-trust` trust signals row: "reviewed in 1–2 days · no spam"
- Replaced inline `style="color: var(--signal-red);"` on required markers with `.field-req` CSS class

### Tests
- Created `tests/test_auth_ux_fixes.py`: 26 tests, 21 pass + 5 skip gracefully on auth redirect
- Updated `tests/test_qs4_b_perf.py`: 2 stale assertions updated (old CTA text, removed invite code)

### Design lint
- Score: 5/5 — zero violations across 3 changed templates
