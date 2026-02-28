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
