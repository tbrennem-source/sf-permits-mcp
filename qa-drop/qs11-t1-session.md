# QS11 T1 Session Report — Landing Page Intelligence Showcase + MCP Demo

**Sprint:** QS11 · **Terminal:** T1 · **Date:** 2026-02-28
**Head commit:** 7518664

## Agent Results

| Agent | Branch | Status | Tests | Notes |
|---|---|---|---|---|
| 1A — Data Prep | worktree-agent-aa86274a | ✅ PASS | 49/49 | showcase_data.json + generate script |
| 1B — Showcase Components | worktree-agent-a26689c0 | ✅ PASS | 43/43 | 6 component templates + JS animations |
| 1C — MCP Demo | worktree-agent-a793f02a | ✅ PASS | 43/43 | mcp_demo.html + CSS + JS (Opus) |
| 1D — Landing Integration | worktree-agent-a0f9f37b | ✅ PASS | 15/15 | landing.html + routes_public.py |

## Files Created/Modified

**New files (agents):**
- `scripts/generate_showcase_data.py` — fixture data generator
- `web/static/data/showcase_data.json` — 6 showcase data fixtures
- `web/templates/components/showcase_gantt.html` — Station Timeline Gantt
- `web/templates/components/showcase_stuck.html` — Stuck Permit Diagnosis
- `web/templates/components/showcase_whatif.html` — What-If Comparison
- `web/templates/components/showcase_risk.html` — Revision Risk Meter
- `web/templates/components/showcase_entity.html` — Entity Network Mini-Graph
- `web/templates/components/showcase_delay.html` — Cost of Delay Calculator
- `web/static/js/showcase-gantt.js` — Gantt entrance animation
- `web/static/js/showcase-entity.js` — Entity network entrance animation
- `web/templates/components/mcp_demo.html` — Animated chat demo (3 demo rotation)
- `web/static/mcp-demo.css` — MCP demo styling + animations + mobile breakpoints
- `web/static/mcp-demo.js` — Auto-advance, typing animation, scroll trigger
- `tests/test_showcase_data.py` — 49 tests
- `tests/test_showcase_components.py` — 43 tests
- `tests/test_mcp_demo.py` — 43 tests
- `tests/test_landing_showcases.py` — 15 tests
- `docs/mcp-demo-transcripts.md` — Demo content (created by orchestrator)

**Modified files:**
- `web/templates/landing.html` — Added showcase section + MCP demo, removed Capabilities/Demo
- `web/routes_public.py` — Added showcase data loading to index()
- `docs/DESIGN_COMPONENT_LOG.md` — Added QS11 T1 showcase components
- `tests/test_landing.py` — Updated stale test for new showcase structure

## Test Counts

- New tests added: 150
- Full suite after merge: **4349 passed, 0 failed, 6 skipped**

## Merge Notes

- 4 agents merged in dependency order: 1A → 1B → 1C → 1D
- Post-merge data reconciliation: JSON field names from 1A and template field names from 1B differed. Resolved by updating showcase_data.json to add: `start_month`, `width_pct`, `name`, `is_current` (stations); `expected_cost`, `scenarios`, `warning_text` (delay); `total_permits`, `central_node`, `nodes` (entity); `whatif` alias; spec-matching labels for whatif/risk/stuck.
- Added `{% if showcase %}` fallback guards in landing.html for graceful degradation
- Added `data-track="mcp-demo-cta"` to CTA button in mcp_demo.html

## Design Lint

Score: **1/5** — apparent violations are:
1. `mcp_demo.html`: 6 flagged as "hex colors" — these are HTML entities (&#9889; ⚡, &#9888; ⚠, &#65039; variation selector) — **FALSE POSITIVES in lint tool**
2. `landing.html`: 10 violations — all **pre-existing** before this sprint (clamp() font-sizes, inline JS styles)

Recommendation: No T1-introduced design system violations. Prod gate should be: PASS (with note to fix lint false-positive for HTML entities).

## Visual QA Checklist (for DeskRelay)

- [ ] Landing page hero renders correctly
- [ ] Intelligence Showcase section appears below hero (2-col grid desktop)
- [ ] All 6 showcase cards visible: Gantt, Stuck, What-If, Risk, Entity, Delay
- [ ] MCP Demo section: 3 demos rotate (What-If → Stuck → Delay)
- [ ] MCP Demo: typing animation plays on scroll trigger
- [ ] Mobile (375px): Showcases stack full-width, MCP demo tables collapse to cards
- [ ] "Try it yourself →" ghost CTAs present on each showcase
- [ ] Gantt bars animate in on scroll (IntersectionObserver)
- [ ] Entity network SVG nodes visible

## Blocked Items

None.
