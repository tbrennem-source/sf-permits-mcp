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
