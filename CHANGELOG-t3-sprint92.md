# CHANGELOG — Sprint 92 T3 Agent 3B

## feat(tools): Polish What-If Simulator and Cost of Delay pages

**Files modified:**
- `web/templates/tools/what_if.html` — complete redesign
- `web/templates/tools/cost_of_delay.html` — complete redesign
- `tests/test_tools_polish_b.py` — new, 73 tests

### What-If Simulator (/tools/what-if)

**Before:** Single base project textarea + variations section (up to 3). Results rendered as raw markdown. No structured comparison view.

**After:**
- Two-panel side-by-side form: Project A (scope, cost, neighborhood) vs Project B (scope, cost, label)
- Comparison table with `diff-better` (green) and `diff-worse` (red) indicators on dramatic differences across: Permit Type, Review Path, Timeline (p50/p75), Est. DBI Fees, Revision Risk
- Strategy callout (accent teal left border) — auto-extracts recommendation from Delta section of API response
- Skeleton loading state mirroring comparison table rows
- Empty state: "Compare two project scopes" + demo suggestion link
- `?demo=kitchen-vs-full` auto-fills both panels and auto-runs (400ms delay for UX)
- Full markdown detail rendered below the structured table (fallback and reference)
- Design lint: 5/5 — no hardcoded hex, all tokens

### Cost of Delay Calculator (/tools/cost-of-delay)

**Before:** Text inputs for permit type, monthly cost, neighborhood, triggers. Results rendered as raw markdown. No structured cards.

**After:**
- Two-column sticky layout: form on left (sticky top), results on right
- Permit type dropdown (12 types: restaurant, commercial_ti, change_of_use, new_construction, adu, adaptive_reuse, seismic, general_alteration, kitchen_remodel, bathroom_remodel, alterations, otc)
- Monthly carrying cost pre-filled to $15,000 in demo mode
- Expected cost highlight card: accent left border, large monospaced value, sublabel for context
- Bottleneck alert: amber status dot, permit-type-specific slow station warning
- Percentile table: p25/p50/p75/p90 rows with days, carrying cost, revision risk, total columns; likely (p50) row subtly highlighted
- Recommendation callout: green left border — "Budget for p75, not p50"
- `?demo=restaurant-15k` auto-fills and auto-runs
- Skeleton loading state (4-column table shape)
- Empty state: "Calculate your delay exposure" + demo link
- Design lint: 5/5 — no hardcoded hex, all tokens

### Tests

`tests/test_tools_polish_b.py` — 73 tests total:
- `TestWhatIfTemplate` (33 tests): structure, input panels, comparison table, delta indicators, strategy callout, loading/empty states, demo param, API/auth, design token compliance
- `TestCostOfDelayTemplate` (36 tests): structure, inputs, percentile table, expected cost card, bottleneck alert, recommendation, loading/empty states, demo param, API/auth, design token compliance, signal tokens
- `TestToolRoutes` (4 tests): auth redirect for routes and API endpoints

**Full suite impact:** 124 passed (test_what_if_ui.py + test_cost_of_delay_ui.py + test_tools_polish_b.py), 0 failures.

# CHANGELOG — T3 Agent 3C — Sprint QS11 / Sprint 92

## [Sprint QS11-T3-3C] — 2026-02-28

### Added

#### `/tools/entity-network` — Entity Network page
- New route `GET /tools/entity-network` in `web/routes_search.py`
- New template `web/templates/tools/entity_network.html`
  - D3 v7 force-directed graph loaded from CDN
  - Address/entity text input with ?address= auto-fill + auto-run
  - Node sizing proportional to permit count
  - Edge labels showing relationship type (contractor, architect, engineer, owner)
  - Node click expands entity detail sidebar (license, permit count, avg issuance days)
  - Loading overlay, empty state, and error notice
  - Legend using design token CSS vars (no inline hex)
- New `web/static/js/entity-graph.js`
  - D3 force simulation (forceLink, forceManyBody, forceCenter, forceCollide)
  - Drag, zoom (pan + scroll), hover highlight
  - All colours referenced via design token values
  - `EntityGraph.init(container, data, onNodeClick)` + `EntityGraph.destroy()`

#### `/tools/revision-risk` — Revision Risk page
- New route `GET /tools/revision-risk` in `web/routes_search.py`
- New template `web/templates/tools/revision_risk.html`
  - Permit type dropdown (15 options including ADU, restaurant, new construction)
  - Neighborhood dropdown (25 SF neighborhoods)
  - Optional project description text input
  - ?demo=restaurant-mission query param auto-fills form and runs assessment
  - Animated risk gauge bar (green < 15%, amber 15–25%, red > 25%)
  - Top 5 correction triggers with name + description
  - Timeline impact bar (average delay days)
  - Mitigation strategies checklist
  - Loading state, empty state, and error notice

#### Tests
- New `tests/test_tools_new.py` — 25 tests, all passing
  - 10 tests for entity network route and template structure
  - 15 tests for revision risk route and template structure
  - Tests cover 200 responses, HTML structure, query param handling, dropdown options

### Design
- Design lint score: 3/5 — 3 false positives from HTML entities (&#9673; &#9650; &#10003;) being matched by the lint hex-color regex; no real token violations introduced.
- All colours via CSS custom properties (`--accent`, `--signal-amber`, `--signal-blue`, `--signal-green`, `--obsidian-mid`, etc.)
- Fonts: `--sans` for all labels/body, `--mono` for data values/badges/CTAs

## Sprint QS10 — T3 Agent 3D: Share Mechanic for Intelligence Tool Pages

### Added
- `web/templates/components/share_button.html` — reusable share button component (Jinja2 include)
- `web/static/js/share.js` — Web Share API on mobile, clipboard copy on desktop, textarea execCommand fallback for older browsers
- `web/static/css/share.css` — share button styles using only DESIGN_TOKENS.md CSS custom properties (5/5 lint score)
- `web/templates/tools/entity_network.html` — new Entity Network tool page (full tool UI with share button)
- `web/templates/tools/revision_risk.html` — new Revision Risk tool page (full tool UI with share button)
- `web/routes_search.py` — added `/tools/entity-network` and `/tools/revision-risk` routes
- `web/routes_api.py` — added `/api/share` POST endpoint (placeholder for future shareable-link persistence)
- `tests/test_share_mechanic.py` — 30 tests covering component existence, CSS token compliance, all 6 tool page inclusions, and API endpoints (30/30 passing)
- `docs/DESIGN_COMPONENT_LOG.md` — logged share-container + share-btn as new component

### Modified
- `web/templates/tools/station_predictor.html` — added share button include + share.js/share.css links
- `web/templates/tools/stuck_permit.html` — added share button include + share.js/share.css links
- `web/templates/tools/what_if.html` — added share button include + share.js/share.css links
- `web/templates/tools/cost_of_delay.html` — added share button include + share.js/share.css links

### Test results
- 30/30 new tests pass
- 3,919 passing / 4 skipped in full suite (no regressions)
- Design lint: 5/5 for all agent-owned files
