## Sprint 94 — T1 Agent: Stuck Permit Showcase Redesign

### Changed

- **`web/templates/components/showcase_stuck.html`** — Full visual redesign of the Stuck Permit showcase card:
  - Replaced dense text layout (reviewer names, full playbook, timeline impact) with a visual-first diagnostic design
  - Added "Diagnostic Intelligence" intelligence label (mono, --text-tertiary) at top of card
  - New headline: "{N} days · {N} agencies blocked" in mono large font
  - CRITICAL severity badge with pulsing red dot animation (`pulse-red` keyframe, `severity-pulse` class)
  - Horizontal pipeline of 4 station blocks (BLDG, MECH, SFFD, CP-ZOC) — each with abbreviation, red X or green check icon, and dwell_days or round metadata
  - Blocked stations get red border + subtle red background tint
  - First playbook step only ("Step 1: …") as the intervention hint
  - CTA text changed from "Try it yourself →" to "See full playbook →"
  - Card height matches other showcase cards — no vertical overflow from full playbook

### Added

- **`tests/test_showcase_stuck_redesign.py`** — 16 tests covering:
  - Component renders without error
  - Headline contains days_stuck value and "days" keyword
  - CRITICAL badge present
  - All 4 station abbreviations (BLDG, MECH, SFFD, CP-ZOC) visible
  - Pipeline station block elements present (count >= 4)
  - CTA links to /tools/stuck-permit?permit=202412237330
  - CTA uses ghost-cta class
  - No raw JSON or Python dict output
  - "Diagnostic Intelligence" label present
  - Severity pulse animation elements present (severity-pulse class, pulse-red keyframe)
  - First intervention step present ("Step 1:")
  - Step 3 not shown on card
  - Agency count in headline

### Fixed

- **`tests/test_showcase_components.py`** — Updated 3 TestShowcaseStuck tests to reflect redesigned component:
  - `test_contains_severity_badge` — now asserts "agencies blocked" instead of "4 SIMULTANEOUS BLOCKS"
  - `test_contains_reviewer_names` → renamed `test_pipeline_station_blocks` — asserts station abbreviations instead of reviewer names
  - `test_contains_playbook_steps` → renamed `test_contains_first_playbook_step` — asserts "Step 1:" only

### Design Token Compliance

- Score: 3/5 (4 low-severity violations — rgba(239,68,68,*) tints for blocked station styling)
- All violations are the same pattern as the original component (signal-red alpha tints)
- No new color tokens invented
- Fonts: --mono for all data/labels, --sans for body copy and intervention text
- Components: glass-card, ghost-cta, var(--dot-red) for status dots
