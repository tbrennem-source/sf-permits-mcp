# CHANGELOG — QS8-T2-A: What's Next Station Predictor

## Sprint: QS8 Terminal 2 Agent A
## Date: 2026-02-27
## Branch: worktree-agent-aabebfd3

---

## What Was Built

### New: `src/tools/predict_next_stations.py`

Async MCP tool that predicts what review stations an SF permit will visit next.

**Function:** `async def predict_next_stations(permit_number: str) -> str`

**Algorithm:**
1. Query permit metadata (type, neighborhood, status) from `permits` table
2. Query this permit's addenda routing history (deduped by station/addenda_number)
3. Find current active station (arrived but no finish_date)
4. Build Markov-style transition probability matrix from 3 years of similar permits
   - Tries neighborhood-filtered first (e.g., Mission permits only)
   - Falls back to type-only if neighborhood has insufficient data
5. Compute top-3 predicted next stations ranked by historical transition frequency
6. Enrich each prediction with velocity data (p50/p75) from `station_velocity_v2`
7. Return formatted markdown with: current station, predictions table, all-clear estimate, confidence

**Output includes:**
- Current station with dwell time + STALLED warning if >60 days with no activity
- Probability table: station | probability | typical duration | range
- "All-clear estimate" (sequential sum of p50 durations for predicted stations)
- Prediction confidence: High (≥100 samples), Medium (≥30), Low (<30)

**Edge cases handled:**
- Permit not found → helpful error with correction guidance
- No addenda data → "No routing data available" message
- Complete/issued/cancelled permit → "completed all review stations" message
- No transition data for current station → explains why prediction isn't available
- get_connection() failure → catches exception, returns error message string

---

### New: `tests/test_station_predictor.py`

41 tests covering:

| Class | Count | Coverage |
|-------|-------|---------|
| `TestFormatDays` | 7 | Edge cases for day formatting helper |
| `TestLabel` | 2 | Known + unknown station code labels |
| `TestFindCurrentStation` | 5 | Empty, all-finished, one-unfinished, multi-unfinished, no-arrive |
| `TestComputeDwellDays` | 4 | None arrive, recent, old, timestamp format |
| `TestComputeTopPredictions` | 6 | Empty transitions, below-threshold, top-n, probabilities, sort order, labels |
| `TestFormatOutput` | 7 | No history, all-finished, current station, stall warning, predictions, all-clear, confidence |
| `TestPredictNextStationsAsync` | 8 | Permit not found, complete, no addenda, in-progress, stalled, error handling, markdown return, predictions table |
| Module-level | 2 | Import sanity, async function check |

**All 41 tests: PASSING**

---

## Pre-existing File Note

`src/tools/station_predictor.py` pre-existed as a cron/refresh utility (contains `refresh_station_transitions()` and `predict_remaining_path()` for the station_transitions table, postgres-only). Per agent rules (no modifying existing files), the new MCP-facing async tool was placed in `src/tools/predict_next_stations.py`. The orchestrator should consider whether to consolidate or alias during merge.

The test file is named `tests/test_station_predictor.py` as specified in the sprint prompt, and tests the new `predict_next_stations` module.

---

## Files Created

- `src/tools/predict_next_stations.py` (new, 717 lines)
- `tests/test_station_predictor.py` (new, 631 lines)
- `scenarios-pending-review-qs8-t2-a.md` (per-agent output file)
- `CHANGELOG-qs8-t2-a.md` (this file)

## Files NOT Modified

Per sprint rules, no existing files were modified. Server registration (`src/server.py`) is left for the orchestrator's merge step.

---

## Test Results

```
41 passed in 0.12s
```

All tests pass with mocked DB connections — no live database required.
