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
