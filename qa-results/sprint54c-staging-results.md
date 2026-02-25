# Sprint 54C — Staging QA Results

**Date:** 2026-02-25
**Staging URL:** https://sfpermits-ai-staging-production.up.railway.app
**Branch:** main (commit 548dae9+)

## Test Results

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Health shows new tables | PASS | All 4 tables present with data |
| 2 | Boiler permits count | PASS | 151,919 (expected 140K-170K) |
| 3 | Fire permits count | PASS | 83,975 (expected 75K-95K) |
| 4 | Planning records count | PASS | 282,169 (expected 260K-310K) |
| 5 | Tax rolls count | PASS | 636,410 (expected 580K-700K) |
| 6 | Cross-ref match rates | PASS | planning=79.8%, boiler=97.8%, tax=23.4% |
| 7 | Existing tables intact | PASS | All pre-existing tables present, status=ok |
| 8 | Auth rejection | PASS | 403 for unauthenticated requests |
| 9 | pytest suite | PASS | 1,696 passed, 20 skipped, 0 failures |

**Total: 9/9 PASS**

## Row Counts
- boiler_permits: 151,919
- fire_permits: 83,975
- planning_records: 282,169
- tax_rolls: 636,410
- **Total new records: 1,154,473**

## Cross-Reference Match Rates
- Planning → Building permits: 79.8% (225,193 of 282,169)
- Boiler → Building permits: 97.8% (148,592 of 151,919)
- Tax rolls → Active permits: 23.4% (149,135 of 636,410)

All match rates above 5% threshold. Tax rolls 23.4% is expected — tax rolls cover all parcels in SF, not just those with active building permits.

## Screenshots
- `screenshots/sprint54c/health-endpoint.png` — health endpoint showing new table counts
