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
