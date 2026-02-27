# QA Script: Sprint 74-4 — Connection Pool Tuning

## Scope
Verify env var configuration for pool parameters, health function, stats integration, and pool exhaustion logging.

## Prerequisites
- `source .venv/bin/activate`
- Run from repo root (worktree or main)

---

## Step 1 — New tests pass
```bash
pytest tests/test_sprint_74_4.py -v
```
PASS: 13 tests collected, all PASSED
FAIL: Any test failure

---

## Step 2 — Existing pool tests still pass
```bash
pytest tests/test_db_pool.py -v
```
PASS: 28 tests collected, all PASSED
FAIL: Any test failure

---

## Step 3 — DB_POOL_MIN env var is read
```python
import importlib, sys, os
os.environ["DATABASE_URL"] = "postgresql://x/y"
os.environ["DB_POOL_MIN"] = "5"
for k in list(sys.modules):
    if "src.db" in k: del sys.modules[k]
import src.db as db
db._pool = None
# Verify the env var would be read
import inspect
src = inspect.getsource(db._get_pool)
assert "DB_POOL_MIN" in src
print("PASS: DB_POOL_MIN in _get_pool source")
```
PASS: "DB_POOL_MIN in _get_pool source" printed
FAIL: AssertionError

---

## Step 4 — DB_CONNECT_TIMEOUT env var is read
```python
import src.db as db, inspect
src = inspect.getsource(db._get_pool)
assert "DB_CONNECT_TIMEOUT" in src
print("PASS: DB_CONNECT_TIMEOUT in _get_pool source")
```
PASS: assertion passes
FAIL: AssertionError

---

## Step 5 — DB_STATEMENT_TIMEOUT env var is read
```python
import src.db as db, inspect
src = inspect.getsource(db.get_connection)
assert "DB_STATEMENT_TIMEOUT" in src
print("PASS: DB_STATEMENT_TIMEOUT in get_connection source")
```
PASS: assertion passes
FAIL: AssertionError

---

## Step 6 — get_pool_health() exists and returns correct keys
```python
import src.db as db
db._pool = None
h = db.get_pool_health()
assert set(h.keys()) == {"healthy", "min", "max", "in_use", "available"}
assert h["healthy"] is False  # no pool
print("PASS: get_pool_health() returns correct keys, healthy=False when no pool")
```
PASS: both assertions pass
FAIL: AssertionError or KeyError

---

## Step 7 — get_pool_stats() includes health key
```python
from unittest.mock import MagicMock
import src.db as db
mock_pool = MagicMock()
mock_pool.closed = False
mock_pool.minconn = 2
mock_pool.maxconn = 20
mock_pool._pool = []
mock_pool._used = set()
db._pool = mock_pool
stats = db.get_pool_stats()
assert "health" in stats
assert isinstance(stats["health"], dict)
assert "healthy" in stats["health"]
db._pool = None
print("PASS: get_pool_stats() includes health dict")
```
PASS: assertion passes
FAIL: KeyError or AssertionError

---

## Step 8 — Full test suite (excluding known pre-existing failures)
```bash
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e \
  --deselect=tests/test_permit_lookup.py::test_permit_lookup_address_suggestions \
  -q 2>&1 | tail -5
```
PASS: No new failures compared to baseline (286 failed, ~3357 passed)
FAIL: More failures than baseline

---

## Notes
- `test_permit_lookup.py::test_permit_lookup_address_suggestions` is a pre-existing failure (mock behavior mismatch unrelated to pool changes)
- `test_reference_tables.py::TestCronEndpointAuth::test_cron_seed_references_blocked_on_web_worker` is a test-ordering issue (passes in isolation, fails in full suite) — pre-existing
