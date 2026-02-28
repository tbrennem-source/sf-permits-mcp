# QS8-T2-D Changelog

## [QS8-T2-D] Cost of Delay Calculator Tool

**Date:** 2026-02-27
**Agent:** T2-D (QS8)
**Branch:** worktree-agent-ad958e30

### Added

#### `src/tools/cost_of_delay.py` (NEW)

New MCP tool providing financial cost-of-delay analysis for SF permit processing.

**Public API:**

```python
async def calculate_delay_cost(
    permit_type: str,
    monthly_carrying_cost: float,
    neighborhood: Optional[str] = None,
    triggers: Optional[list] = None,
) -> str
```

Returns a formatted markdown string with:
- Financial exposure table (Best/Likely/Worst scenarios at p25/p50/p90)
- Carrying cost per scenario (monthly_cost × timeline_days / 30.44)
- Revision risk cost per scenario (P(revision) × revision_delay × daily_cost)
- Break-even analysis (daily cost of delay including revision risk)
- OTC eligibility note (when permit type qualifies for same-day processing)
- Mitigation strategies (specific to permit type)
- Methodology section (data sources, formulas)

```python
def daily_delay_cost(monthly_carrying_cost: float) -> str
```

One-liner helper: "Every day of permit delay costs you $X/day"

**Key design decisions:**
- Uses `estimate_timeline` for live p25/p50/p90 data when DB available
- Falls back to calibrated historical averages (13 permit types) when DB unavailable
- Trigger escalations (planning_review, ceqa, historic, etc.) applied to fallback timelines only
- Module-level `estimate_timeline = None` sentinel enables clean test patching
- All permit-type data (revision probability, delay days, OTC eligibility) in module-level constants

**Permit types supported:** restaurant, commercial_ti, change_of_use, new_construction, adu, adaptive_reuse, seismic, general_alteration, kitchen_remodel, bathroom_remodel, alterations, otc, no_plans (+ unknown types fall back to defaults)

#### `tests/test_cost_of_delay.py` (NEW)

42 tests covering:
- `TestDailyDelayCost` (6 tests) — basic/round numbers/small/large/zero/negative
- `TestFormatCurrency` (5 tests) — small/thousands/millions/boundary/under-10k
- `TestGetRevisionInfo` (4 tests) — restaurant high risk/OTC low risk/unknown/new construction
- `TestGetTimelineEstimates` (4 tests) — restaurant/OTC/new construction/unknown
- `TestGetPermitTypeLabel` (3 tests) — restaurant/ADU/unknown
- Async `calculate_delay_cost` tests (17 tests) — happy path, table structure, math, error handling, OTC note, triggers, mitigation, methodology, break-even, neighborhood, daily oneliner, live timeline parsing, unknown type, small/large costs, multiple triggers
- `TestConstants` (3 tests) — OTC set membership, probability range, all positive

All 42 tests pass.

### Test Results

```
============================= 42 passed in 0.10s ==============================
```
