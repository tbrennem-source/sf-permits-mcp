## QS11 / T1-agent-1B — Intelligence Showcase Components

**Date:** 2026-02-28
**Branch:** worktree-agent-a26689c0

### Added

- **6 showcase component templates** (`web/templates/components/`):
  - `showcase_gantt.html` — Station Timeline Gantt: horizontal bar chart showing permit routing through 8+ stations, color-coded by status (approved/comments/current), "you are here" indicator on current station, reviewer names on each bar, CSS-only (no canvas/SVG)
  - `showcase_stuck.html` — Stuck Permit Diagnosis: severity badge with block count, 4-block grid with station/reviewer/round detail, 3-step intervention playbook, timeline impact callout
  - `showcase_whatif.html` — What-If Comparison: 9-row table comparing two permit scenarios (kitchen-only OTC vs full remodel in-house), semantic color coding for favorable/unfavorable values, strategy callout
  - `showcase_risk.html` — Revision Risk Meter: percentage gauge with HIGH badge, sample size, top 5 correction triggers as numbered list, timeline/budget impact rows
  - `showcase_entity.html` — Entity Network Mini-Graph: pure SVG (no D3), central property node + 4 professional nodes with role-coded colors, animated fade-in
  - `showcase_delay.html` — Cost of Delay Calculator: pre-filled monthly cost, 4 percentile scenarios (p25/p50/p75/p90), probability-weighted expected cost, slow-station warning badge

- **Fixture data** (`web/static/data/showcase_data.json`): Pre-rendered data for all 6 showcase components with realistic SF permit data

- **JavaScript entrance animations**:
  - `web/static/js/showcase-gantt.js` — IntersectionObserver-driven bar-grow animation (scaleX 0→1, staggered 100ms/station)
  - `web/static/js/showcase-entity.js` — IntersectionObserver-driven node fade-in (central first, then edges, then secondary nodes)

- **Tests** (`tests/test_showcase_components.py`): 43 tests covering all 6 components — render without error, key content assertions, ghost CTA href correctness, data-track attributes

- **DESIGN_COMPONENT_LOG.md** updated with: gantt bar pattern, severity badge pattern, entity SVG mini-graph, signal color alpha tints (approved derived pattern)

### Design System Compliance

- All components use Obsidian token CSS custom properties (`--obsidian-mid`, `--glass-border`, `--accent`, `--signal-*`, `--dot-*`, `--mono`, `--sans`, `--space-*`, `--radius-*`)
- Signal color alpha tints (rgba derived from token values) documented in DESIGN_COMPONENT_LOG.md as approved pattern
- All CTAs use `ghost-cta` class
- All containers use `glass-card` class
- `data-track="showcase-view"` and `data-track="showcase-click"` on all components for analytics
- WCAG AA contrast: no `--text-tertiary` on interactive elements

### Test Results

```
43 passed in 0.30s (test_showcase_components.py)
3932 passed, 4 skipped, 13 xfailed in 165.33s (full suite)
```

## Sprint 90 — T1 Landing Showcase (MCP Demo)

### Added
- **MCP Demo Chat Transcript Component** — animated chat section for landing page showing Claude using sfpermits.ai tools
  - 3 demo conversations cycle: What-If Scope Comparison (leads), Stuck Permit Diagnosis, Cost of Delay
  - Scroll-triggered animation via IntersectionObserver (threshold 0.3)
  - User messages fade-in + slide-up, tool call badges pulse with stagger, Claude responses type line by line
  - Tables render as pre-built HTML blocks (instant, not typed)
  - 4s pause between demos, auto-cycles indefinitely
  - Manual prev/next arrows and navigation dots
  - Dark terminal-style window with red/amber/green title bar dots
  - CTA section: "Connect your AI" button + 3-step explainer (Connect, Ask, Get Intelligence)
- **Mobile treatment (480px breakpoint)**
  - Tables collapse to stacked key-value cards (e.g., "Kitchen Only" card, "Kitchen + Bath + Wall" card)
  - Long Claude responses capped at 300px with "See full analysis" expand button
  - Tool badges wrap to 2 lines max
- **Reduced motion support** — all animations disabled, content shown immediately
- **43 tests** covering template rendering, demo presence, rotation order, tool badges, CTA, mobile CSS, JS structure, navigation, transcript accuracy

### Files Created
- `web/templates/components/mcp_demo.html` — component template with all 3 demos inline
- `web/static/mcp-demo.css` — styling, animations, mobile breakpoints, reduced motion
- `web/static/mcp-demo.js` — scroll trigger, typing animation, auto-advance, manual controls
- `tests/test_mcp_demo.py` — 43 tests across 10 test classes

# Sprint 90 (QS11) — T1-A: Landing Showcase Integration

**Date:** 2026-02-28
**Agent:** T1-A (worktree-agent-a0f9f37b)
**Worktree branch:** worktree-agent-a0f9f37b

## Changes

### Landing Page — Major Section Restructure

**Removed:**
- Old "Capabilities" section with 4 question-based list items (#cap-permits, #cap-timeline, #cap-stuck, #cap-hire)
- Old static "Demo" widget (1455 Market St browser mockup)

**Added:**
- `<section class="showcase-section" id="intelligence">` — 6 showcase cards in 2×3 grid using `{% include %}` fragments
- `<section class="mcp-section" id="mcp-demo">` — animated AI chat demo section
- CSS for showcase-grid, showcase-card (with 6 data-specific sub-components), and MCP demo layout
- `<link rel="stylesheet" href=".../mcp-demo.css">` — external MCP demo CSS
- Script tags for `showcase-gantt.js`, `showcase-entity.js`, `mcp-demo.js` (deferred)
- PostHog analytics `data-track` attributes on all showcase cards and MCP demo CTA

### Route: `web/routes_public.py`

- Added `_load_showcase_data()` function — reads `web/static/data/showcase_data.json`
- `index()` now passes `showcase={}` dict to `landing.html` for unauthenticated users
- Graceful fallback: returns `{}` on `FileNotFoundError`, `json.JSONDecodeError`, or any `OSError`
- Added `import os` to imports

### New Files

| File | Purpose |
|------|---------|
| `web/templates/components/showcase_gantt.html` | Timeline Gantt card |
| `web/templates/components/showcase_stuck.html` | Routing tracker card |
| `web/templates/components/showcase_whatif.html` | What-if scenario card |
| `web/templates/components/showcase_risk.html` | Revision risk score card |
| `web/templates/components/showcase_entity.html` | Entity network card |
| `web/templates/components/showcase_delay.html` | Cost of delay card |
| `web/templates/components/mcp_demo.html` | MCP chat demo component |
| `web/static/data/showcase_data.json` | Sample data for all 6 showcase types |
| `web/static/mcp-demo.css` | MCP demo section styles |
| `web/static/mcp-demo.js` | MCP demo animation (stub, Agent 1C owns full version) |
| `web/static/js/showcase-gantt.js` | Gantt bar animation (stub, Agent 1B owns full version) |
| `web/static/js/showcase-entity.js` | Entity graph animation (stub, Agent 1B owns full version) |

### Tests

- `tests/test_landing_showcases.py` — 15 new tests (all passing)
  - Route returns 200 for unauthenticated users
  - `#intelligence` section id present
  - `showcase-grid` container present
  - `data-track="showcase-view"` present
  - MCP demo section present
  - Old `#cap-permits`, `#cap-hire` IDs absent
  - Fallback when `showcase_data.json` missing (mocked)
  - `_load_showcase_data()` returns `{}` on `FileNotFoundError`
  - `_load_showcase_data()` returns `{}` on malformed JSON
  - Search form preserved
  - Sign-in link preserved
  - Stats section preserved
  - `data-track="mcp-demo-cta"` present
  - All 6 `data-showcase` types present (gantt/stuck/whatif/risk/entity/delay)
  - `_load_showcase_data()` parses valid JSON correctly

- `tests/test_landing.py::TestLandingPage::test_landing_has_feature_cards` — updated to check showcase structure instead of old capability text (stale test)

### Design Compliance

- Lint score: 1/5 (unchanged from baseline — all 10 violations are pre-existing in original landing.html, not introduced by this PR)
- New CSS uses only token variables: `var(--obsidian-mid)`, `var(--glass-border)`, `var(--accent)`, `var(--signal-amber)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--text-tertiary)`, `var(--dot-green)`, `var(--dot-amber)`, `var(--dot-red)`, `var(--signal-green)`, `var(--signal-red)`
- New components logged in `docs/DESIGN_COMPONENT_LOG.md` (Showcase Card, MCP Demo Chat Section)
