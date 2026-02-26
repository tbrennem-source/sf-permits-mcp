# Sprint 64: Reliability + Monitoring QA Script

## Pre-requisites
- Staging deployed with Sprint 64 code
- CRON_SECRET available for cron endpoint tests

---

## 1. Migration Hardening (scripts/release.py)

### 1a. Schema sync completeness
- [ ] Run `source .venv/bin/activate && python -c "from scripts.release import run_release_migrations; print('import OK')"`
- PASS: Import succeeds without error
- FAIL: Import error or missing module

### 1b. EXPECTED_TABLES includes pim_cache and dq_cache
- [ ] Run `python -c "from web.app import EXPECTED_TABLES; assert 'pim_cache' in EXPECTED_TABLES; assert 'dq_cache' in EXPECTED_TABLES; print('PASS')"`
- PASS: Both tables present
- FAIL: AssertionError

### 1c. Stuck job threshold is 10 minutes
- [ ] Run `python -c "import inspect; from web.app import cron_nightly; s=inspect.getsource(cron_nightly); assert \"INTERVAL '10 minutes'\" in s; assert \"INTERVAL '15 minutes'\" not in s; print('PASS')"`
- PASS: 10-minute threshold confirmed, no 15-minute reference
- FAIL: Either assertion fails

---

## 2. Data Quality Checks

### 2a. Orphaned contacts check uses entity-based logic
- [ ] Run `python -c "import inspect; from web.data_quality import _check_orphaned_contacts; s=inspect.getsource(_check_orphaned_contacts); assert 'entities' in s; assert 'Unresolved' in s; print('PASS')"`
- PASS: Check references entities table and "Unresolved" name
- FAIL: Old permit-based logic detected

### 2b. New addenda freshness check exists
- [ ] Run `python -c "from web.data_quality import _check_addenda_freshness; r=_check_addenda_freshness(); assert r['name']=='Addenda Freshness'; print('PASS:', r['status'])"`
- PASS: Check returns valid result (green/yellow/red)
- FAIL: ImportError or missing name

### 2c. New station velocity freshness check exists
- [ ] Run `python -c "from web.data_quality import _check_station_velocity_freshness; r=_check_station_velocity_freshness(); assert r['name']=='Station Velocity'; print('PASS:', r['status'])"`
- PASS: Check returns valid result
- FAIL: ImportError or missing name

### 2d. All DQ tests pass
- [ ] Run `pytest tests/test_data_quality.py -v --tb=short`
- PASS: All 18 tests pass
- FAIL: Any test failure

---

## 3. Morning Brief Pipeline Stats

### 3a. Brief includes change_velocity
- [ ] Run `pytest tests/test_sprint64_brief.py -v --tb=short`
- PASS: All 7 tests pass
- FAIL: Any test failure

### 3b. _get_last_refresh returns pipeline stats
- [ ] Verify `changes_detected` and `inspections_updated` fields exist in response
- PASS: Both fields present when cron_log has data
- FAIL: Fields missing or error

---

## 4. Cron Pipeline Integration

### 4a. Nightly includes signals + velocity_v2
- [ ] Run `pytest tests/test_sprint64_cron.py -v --tb=short`
- PASS: All 5 tests pass
- FAIL: Any test failure

### 4b. Signal pipeline failure is non-fatal
- [ ] Already covered by TestNightlyNonFatal::test_signals_error_captured
- PASS: Test passes (error captured in response, HTTP 200)
- FAIL: Test fails

---

## 5. Full Regression

### 5a. Full test suite
- [ ] Run `pytest tests/ --ignore=tests/test_tools.py -q --tb=short`
- PASS: 3,123+ passed, 0 failed
- FAIL: Any test failure or count regression
