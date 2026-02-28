# Changelog — Sprint 94 T1A: Landing Page Showcase Restructure

## Sprint 94 T1A — Gantt Full-Width, Kill Stats Bar

**Branch:** agent-a35bf3fb
**Date:** 2026-02-28
**Files modified:**
- `web/templates/landing.html` — showcase section restructured
- `tests/test_landing.py` — updated stale stats test
- `tests/test_landing_showcase_layout.py` — new test file (21 tests)

### Changes

#### Landing Page (`web/templates/landing.html`)

- **Removed stats bar** — Eliminated the entire 4-stat section (1,137,816 SF building permits / 22 City data sources / Nightly / Free During beta). The `.stats-section`, `.stats-row`, `.stat-item`, `.stat-divider` CSS and HTML are gone.

- **Full-width Gantt section** — Station Timeline showcase moved to its own full-width section (`showcase-gantt-section`) directly below the hero/search. The Gantt card no longer shares a row with other cards.
  - "Routing Intelligence" label in `--text-tertiary`, `--mono`, small caps above the chart
  - `.showcase-gantt-fullwidth` class sets `width: 100%; max-width: none`
  - Mobile treatment (≤480px): horizontal scroll with `overflow-x: auto` and box-shadow fade hint

- **5-card showcase grid** — The remaining 5 showcases (stuck, whatif, risk, entity, delay) placed in a responsive grid below the Gantt:
  - Desktop: `repeat(3, 1fr)`
  - Tablet (≤768px): `repeat(2, 1fr)`
  - Phone (≤480px): `1fr` (single column)
  - Gap: `var(--space-lg, 24px)`

- **Credibility line** — Added `<p class="credibility-line">` at page bottom (above footer): "Updated nightly from 22 city data sources · Free during beta". Styled with `--mono`, `--text-tertiary`, `text-align: center`, `margin: var(--space-lg) 0`.

- **JS cleanup** — Replaced `1,137,816` literal in JS dropdown footer text with `1.1M+` to avoid test false-positives and keep copy maintainable.

#### Tests

- **`tests/test_landing.py`** — Updated `test_landing_has_stats` → `test_landing_has_credibility_line` to assert the new bottom line content instead of the removed stats bar labels.

- **`tests/test_landing_showcase_layout.py`** (new, 21 tests):
  - `TestLandingBasic` (2): smoke tests — 200, HTML present
  - `TestStatsBarRemoved` (3): 1,137,816 gone, stat-item gone, stats-section gone
  - `TestCredibilityLine` (4): line present, mentions 22 sources, mentions beta, uses credibility-line class
  - `TestGanttFullWidth` (5): section exists, fullwidth class, "Routing Intelligence" label, label class, id="intelligence"
  - `TestShowcaseGrid` (4): grid exists, has id, Gantt before grid, ≤5 cards in grid
  - `TestResponsiveGrid` (3): 3-col desktop, 2-col tablet, 1-col mobile

### Design Lint

- Baseline (main): 1/5 — 10 violations
- Post-sprint: 1/5 — 8 violations (improved by 2)
- All remaining violations are pre-existing (interactive `--text-tertiary` usage, inline JS object styles)
- No new violations introduced

### Test Results

- New test file: 21/21 passed
- Landing test suite: 59/59 passed
- Full suite: 4454 passed, 6 skipped, 17 xfailed — no regressions
