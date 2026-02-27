# QA Script: Request Metrics + /admin/perf Dashboard (Sprint 74-1)

Self-contained. No credentials required for CLI steps. Admin login required for browser steps.

---

## CLI QA (no browser)

**Step 1: DDL table creation**
```python
from src.db import init_user_schema
import duckdb
conn = duckdb.connect(':memory:')
init_user_schema(conn)
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'request_metrics'").fetchall()
assert len(tables) == 1
conn.close()
```
PASS if: no assertion error
FAIL if: assertion error or import error

**Step 2: EXPECTED_TABLES includes request_metrics**
```python
from web.app import EXPECTED_TABLES
assert 'request_metrics' in EXPECTED_TABLES
```
PASS if: no assertion error
FAIL if: assertion error

**Step 3: /admin/perf route registered**
```python
from web.app import app
rules = [r.rule for r in app.url_map.iter_rules()]
assert '/admin/perf' in rules
```
PASS if: no assertion error
FAIL if: assertion error

**Step 4: Metric sampling — slow request triggers insert**
```python
import time
from unittest.mock import patch, MagicMock
from web.app import app, _slow_request_log
app.config['TESTING'] = True
app.config['SECRET_KEY'] = 'test'
with patch('web.app.random') as mock_random, patch('src.db.execute_write') as mock_write:
    mock_random.random.return_value = 0.5
    with app.test_request_context('/test', method='GET'):
        from flask import g
        g._request_start = time.monotonic() - 0.3
        resp = MagicMock(); resp.status_code = 200
        _slow_request_log(resp)
    assert mock_write.called
```
PASS if: no assertion error
FAIL if: assertion error

**Step 5: Fast non-sampled request does NOT insert**
```python
with patch('web.app.random') as mock_random, patch('src.db.execute_write') as mock_write:
    mock_random.random.return_value = 0.9
    with app.test_request_context('/fast', method='GET'):
        from flask import g
        g._request_start = time.monotonic() - 0.05
        resp = MagicMock(); resp.status_code = 200
        _slow_request_log(resp)
    assert not mock_write.called
```
PASS if: no assertion error
FAIL if: assertion error

**Step 6: Run test file**
```bash
source .venv/bin/activate
pytest tests/test_sprint_74_1.py -v
```
PASS if: 14 passed
FAIL if: any failures

---

## Browser QA (admin login required)

**Step 7: /admin/perf loads for admin**
- Log in as admin
- Navigate to /admin/perf
PASS if: 200, page shows stat blocks and endpoint tables
FAIL if: 404, 403, 500, or page crashes

**Step 8: Empty state renders without errors**
- On a fresh DB (or if request_metrics table is empty)
- Navigate to /admin/perf
PASS if: Empty state messages shown in tables, stat blocks show 0ms
FAIL if: Python exception, missing template variable error, or blank/broken page

**Step 9: Non-admin access rejected**
- Log in as non-admin user
- Navigate to /admin/perf
PASS if: 403 page or redirect
FAIL if: 200 (page shown to non-admin)
