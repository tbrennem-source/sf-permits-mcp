# CHANGELOG — QS5-C: Trade Permit Bridge + Orphan Inspections

## Investigation: Orphan Inspection Root Cause

**Finding:** 68,116 orphan inspections (10.1% of 671,170 total) — but 68,092 are **complaint inspections** (`reference_number_type = 'complaint'`) that reference complaint numbers, not permit numbers. Only 24 are actual permit-type orphans (0.00% of 592,248 permit-type inspections).

**Root cause:** The inspections dataset includes DBI complaint investigations that use complaint IDs as `reference_number`. These are a different entity type entirely — they'll never match the `permits` table and shouldn't be counted as orphans.

**Zero orphans match boiler_permits or fire_permits.** Trade permits are not the source of any orphaned inspections.

**Follow-up needed:** None — the 24 permit orphans are from a single old permit (`201503050030`) and represent 0.00% of permit inspections. The DQ check filters to `reference_number_type = 'permit'` to give meaningful results.

## Changes

### web/data_quality.py
- Added `_check_orphan_inspections()`: Counts permit-type inspections with no matching permit. Filters by `reference_number_type = 'permit'` to exclude complaint inspections. Thresholds: green <5%, yellow 5-15%, red >15%.
- Added `_check_trade_permit_counts()`: Verifies `boiler_permits` and `fire_permits` tables have data. Returns red if either table is empty (pipeline broken).
- Registered both checks in `run_all_checks()` universal checks list.

### web/app.py
- Added `boiler_permits` and `fire_permits` to `EXPECTED_TABLES`.

### Verification: Trade Ingest
- `ingest_boiler_permits()` and `ingest_fire_permits()` verified working correctly through DuckDB connection. Both use `DELETE FROM` + `INSERT OR REPLACE` pattern (DuckDB-only; Postgres uses separate migration path).

### tests/test_qs5_c_bridges.py (NEW)
- 16 tests covering:
  - Orphan inspection DQ check: structured result, green/yellow/red thresholds, boundary at 15%, error handling
  - Trade permit DQ check: structured result, green when populated, red when empty (boiler, fire, both), error handling
  - EXPECTED_TABLES: boiler_permits and fire_permits present
  - Schema: boiler_permits has block/lot columns, fire_permits does not
