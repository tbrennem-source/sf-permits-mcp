# Sprint 54C — Data Ingest Expansion QA Script

## Prerequisites
- Staging deployed with Sprint 54C code
- CRON_SECRET available for auth

## Steps

### 1. Health endpoint shows new tables
- GET `https://sfpermits-ai-staging-production.up.railway.app/health`
- PASS if response includes `boiler_permits`, `fire_permits`, `planning_records`, `tax_rolls` with row counts > 0
- FAIL if any table missing or count = 0

### 2. Boiler permits row count matches expected range
- Check health response `boiler_permits` count
- PASS if 140,000 < count < 170,000
- FAIL otherwise

### 3. Fire permits row count matches expected range
- Check health response `fire_permits` count
- PASS if 75,000 < count < 95,000
- FAIL otherwise

### 4. Planning records row count matches expected range
- Check health response `planning_records` count
- PASS if 260,000 < count < 310,000
- FAIL otherwise

### 5. Tax rolls row count matches expected range
- Check health response `tax_rolls` count
- PASS if 580,000 < count < 700,000
- FAIL otherwise

### 6. Cross-reference check returns reasonable match rates
- POST `/cron/cross-ref-check` with CRON_SECRET auth
- PASS if all 3 match rates > 5%:
  - `planning_to_permits_pct > 5`
  - `boiler_to_permits_pct > 5`
  - `tax_to_active_permits_pct > 5`
- FAIL if any match rate < 5%

### 7. Existing endpoints still work (no regression)
- GET `/health` returns `status: ok` and `db_connected: true`
- PASS if health returns ok with all pre-existing tables intact
- FAIL if any existing table missing or status degraded

### 8. Cron endpoints reject unauthenticated requests
- POST `/cron/ingest-boiler` without auth header
- PASS if returns 403
- FAIL otherwise

### 9. pytest passes with no regressions
- Run: `pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py -x`
- PASS if all tests pass (0 failures)
- FAIL if any test fails
