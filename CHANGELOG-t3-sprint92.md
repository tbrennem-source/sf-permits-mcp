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
