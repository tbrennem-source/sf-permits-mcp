# QA Script — Sprint 77-1: Severity + Property Health E2E Scenarios

_Self-contained. No setup or credentials needed for anonymous steps._
_Auth steps require TESTING=1 and TEST_LOGIN_SECRET env vars._

---

## Step 1: Collect tests

```
source .venv/bin/activate
pytest tests/e2e/test_severity_scenarios.py --collect-only -q
```

PASS: 14 tests collected, 0 errors
FAIL: Collection error or fewer than 14 tests

---

## Step 2: Run anonymous tests (no credentials needed)

```
source .venv/bin/activate
pytest tests/e2e/test_severity_scenarios.py -v -k "not expediter and not auth_page and not brief_loads and not brief_lookback"
```

PASS: All anonymous tests PASS (search, demo, portfolio-anon-redirect, brief-anon-redirect)
FAIL: Any FAILED result (skips are OK for report tests without DuckDB)

---

## Step 3: Verify report tests skip gracefully (no DuckDB)

```
pytest tests/e2e/test_severity_scenarios.py -v -k "property_report"
```

PASS: All 3 property report tests SKIP with reason "DuckDB permits table likely absent"
FAIL: Any FAILED result

---

## Step 4: Run full suite — verify no regressions from new file

```
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e/ -q 2>&1 | tail -5
```

PASS: Same number of failures as before Sprint 77-1 (314 in test_web.py — pre-existing)
FAIL: Any new failures outside test_web.py

---

## Step 5: (With TEST_LOGIN_SECRET) Run auth tests

```
TESTING=1 TEST_LOGIN_SECRET=e2e-test-secret-local \
  pytest tests/e2e/test_severity_scenarios.py -v -k "expediter or brief_loads or brief_lookback"
```

PASS: portfolio_loads_for_expediter, brief_loads_for_authenticated_user, brief_lookback PASS
FAIL: Any FAILED result (skips acceptable for report tests)

---

## Step 6: Verify screenshot capture

```
ls qa-results/screenshots/e2e/
```

PASS: PNG files present (report-known-parcel.png, search-market-results.png, demo-anonymous.png, brief-anon-redirect.png, portfolio-anon-redirect.png, etc.)
FAIL: Directory empty or missing after test run

---

## Step 7: Verify scenario and changelog files committed

```
git log --oneline -1
git show --stat HEAD
```

PASS: Commit message contains "severity + property health scenarios (Sprint 77-1)", all 4 files present
FAIL: Files not committed or missing

---

## Summary

| Step | Check | Expected |
|------|-------|----------|
| 1 | collect | 14 tests |
| 2 | anonymous tests | all PASS |
| 3 | report tests no-DB | all SKIP |
| 4 | full suite | no new failures |
| 5 | auth tests | PASS (with secret) |
| 6 | screenshots | PNGs present |
| 7 | git log | all files committed |
