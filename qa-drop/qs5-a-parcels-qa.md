# QS5-A: Materialized Parcels Table — QA Script

## Pre-requisites
- Tests passing: `pytest tests/test_qs5_a_parcels.py -v`
- DuckDB has permits table with at least one row

## Checks

1. [NEW] parcel_summary table created in DuckDB
   - Run: `python -c "from src.db import get_connection, init_user_schema; c = get_connection(); init_user_schema(c); print(c.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'parcel_summary'\").fetchone()[0])"`
   - Expected: 1
   - PASS/FAIL

2. [NEW] POST /cron/refresh-parcel-summary requires auth
   - Run test: `pytest tests/test_qs5_a_parcels.py::TestCronRefreshParcelSummary::test_requires_auth -v`
   - Expected: PASSED
   - PASS/FAIL

3. [NEW] POST /cron/refresh-parcel-summary populates rows
   - Run test: `pytest tests/test_qs5_a_parcels.py::TestCronRefreshParcelSummary::test_returns_count -v`
   - Expected: PASSED, parcels_refreshed >= 1
   - PASS/FAIL

4. [NEW] canonical_address is UPPER-cased
   - Run test: `pytest tests/test_qs5_a_parcels.py::TestCronRefreshParcelSummary::test_canonical_address_uppercased -v`
   - Expected: PASSED, address == address.upper()
   - PASS/FAIL

5. [NEW] report.py uses parcel_summary when available
   - Run test: `pytest tests/test_qs5_a_parcels.py::TestReportParcelSummaryIntegration::test_get_parcel_summary_returns_cache -v`
   - Expected: PASSED
   - PASS/FAIL

6. [NEW] report.py falls back to SODA when parcel_summary empty
   - Run test: `pytest tests/test_qs5_a_parcels.py::TestReportParcelSummaryIntegration::test_get_parcel_summary_returns_none_when_missing -v`
   - Expected: PASSED
   - PASS/FAIL
