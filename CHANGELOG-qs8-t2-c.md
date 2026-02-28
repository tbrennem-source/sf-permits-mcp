# CHANGELOG — QS8-T2-C: What-If Permit Simulator

## Added

### `src/tools/what_if_simulator.py` (new)

New tool: **`simulate_what_if(base_description, variations)`**

Orchestrates four existing tools (predict_permits, estimate_timeline, estimate_fees, revision_risk)
across a base project + N variations, running them in parallel via `asyncio.gather()`, and returns
a formatted markdown comparison table.

**Key features:**
- Parallel scenario evaluation — all scenarios run concurrently, not sequentially
- Markdown extraction helpers parse headline values from each sub-tool's output:
  - `_extract_permits` — permit type / form summary
  - `_extract_review_path` — OTC vs. In-house
  - `_extract_p50` / `_extract_p75` — timeline percentiles
  - `_extract_total_fee` — Total DBI Fees from Table 1A-A row
  - `_extract_revision_risk` — risk level + rate
- Cost parsing from natural language: `$80K`, `80k`, `$80,000` all recognized; missing cost defaults to $50K
- Graceful degradation: sub-tool errors populate affected cells with "N/A" and surface error notes at end of output
- Delta section: compares each variation to base, calls out review path changes, timeline shifts, fee deltas
- Module-level sub-tool imports to support clean patch-based mocking in tests
- All sub-tool imports at module level (not inside the async function) — avoids import-time side effects on mock patching

**Output format:**
```
# What-If Permit Simulator

**Base project:** Kitchen remodel in the Mission, $80K
**Scenarios evaluated:** 3 (1 base + 2 variation(s))

## Comparison Table
| Scenario | Description | Permits | Review Path | Timeline (p50) | Timeline (p75) | Est. DBI Fees | Revision Risk |
|---|---|---|---|---|---|---|---|
| **Base** | Kitchen remodel... | Alteration (3 App) | OTC | 45 days | 75 days | $3,013 | MODERATE (18.5%) |
| **Add bathroom** | Kitchen + bath... | Alteration (3 App) | In-house | 90 days | 130 days | $4,520 | MODERATE (18.5%) |

## Delta vs. Base
### Add bathroom
- **Review path:** OTC → In-house (significant change — may add weeks)
- **Timeline (p50):** 45 days → 90 days
- **Fees:** $3,013 → $4,520
```

### `tests/test_what_if_simulator.py` (new)

38 tests across 6 test classes:

- `TestExtractPermits` (3 tests) — extraction helpers for permit summary
- `TestExtractReviewPath` (4 tests) — OTC / In-house detection
- `TestExtractP50` / `TestExtractP75` (5 tests) — timeline extraction
- `TestExtractTotalFee` (3 tests) — fee extraction including table row pattern
- `TestExtractRevisionRisk` (4 tests) — risk level + rate extraction
- `TestSimulateWhatIfBasic` (6 tests) — happy path with mocked sub-tools
- `TestSimulateWhatIfEdgeCases` (8 tests) — error handling, missing fields, truncation, call counts
- `TestSimulateWhatIfCostParsing` (3 tests) — dollar/K cost notation
- `TestSimulateWhatIfReturnType` (2 tests) — return type and table structure

All tests use `unittest.mock.patch` + `AsyncMock` targeting `src.tools.what_if_simulator.*` module-level names.
Uses `asyncio.run()` for Python 3.14 compatibility (not deprecated `get_event_loop()`).

## Test Results

```
38 passed in 0.12s
```

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `src/tools/what_if_simulator.py` | ~360 | Tool implementation |
| `tests/test_what_if_simulator.py` | ~460 | 38 tests |

## Notes

- `what_if_simulator` is NOT yet registered in `src/server.py` — orchestrator handles tool registration.
- Sub-tool imports are at module level to support mocking; this means importing the module will import all four sub-tools. This is intentional and consistent with how other tools are structured.
