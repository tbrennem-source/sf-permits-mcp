# CHANGELOG — T2 Sprint 95 Agent

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
