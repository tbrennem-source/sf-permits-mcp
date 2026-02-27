# QS5-A: Materialized Parcels Table — QA Results

**Date:** 2026-02-26
**Agent:** QS5-A (worktree-qs5-a)
**Test suite:** 14 tests, 14 passed

## Results

1. [NEW] parcel_summary table created in DuckDB — **PASS**
2. [NEW] POST /cron/refresh-parcel-summary requires auth — **PASS**
3. [NEW] POST /cron/refresh-parcel-summary populates rows — **PASS**
4. [NEW] canonical_address is UPPER-cased — **PASS**
5. [NEW] report.py uses parcel_summary when available — **PASS**
6. [NEW] report.py falls back to SODA when parcel_summary empty — **PASS**

## Summary

All 6 QA checks PASS. All 14 pytest tests pass. No regressions detected.
