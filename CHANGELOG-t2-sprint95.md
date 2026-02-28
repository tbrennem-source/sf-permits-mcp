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
