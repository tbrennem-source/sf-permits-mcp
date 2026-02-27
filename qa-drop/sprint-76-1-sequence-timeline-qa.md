# QA Script: Sprint 76-1 — Station Routing Sequence Model

**Feature:** `estimate_sequence_timeline()` + `GET /api/timeline/<permit_number>`
**File:** qa-drop/sprint-76-1-sequence-timeline-qa.md
**Date:** 2026-02-26

All steps are CLI/pytest — no browser required.

---

## Step 1: Import check

```
source .venv/bin/activate
python -c "from src.tools.estimate_timeline import estimate_sequence_timeline; print('OK')"
```

PASS: prints `OK` with no import errors
FAIL: any ImportError or AttributeError

---

## Step 2: Sprint test suite passes

```
source .venv/bin/activate
pytest tests/test_sprint_76_1.py -v
```

PASS: 15 passed, 0 failed
FAIL: any test fails

---

## Step 3: No regressions in full suite

```
source .venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -q 2>&1 | tail -5
```

PASS: same pass count as pre-sprint (only pre-existing `test_permit_lookup_address_suggestions` may fail — it's data-dependent, not caused by this sprint)
FAIL: any new test failures introduced by this sprint

---

## Step 4: API endpoint registered

```
source .venv/bin/activate
python -c "
from web.app import app
rules = [str(r) for r in app.url_map.iter_rules() if 'timeline' in str(r)]
print(rules)
assert any('/api/timeline/' in r for r in rules), 'route not registered'
print('PASS: /api/timeline/<permit_number> registered')
"
```

PASS: prints route and `PASS` message
FAIL: AssertionError or no output

---

## Step 5: No-addenda returns None (unit)

```
source .venv/bin/activate
python -c "
from unittest.mock import MagicMock
from src.tools.estimate_timeline import estimate_sequence_timeline

conn = MagicMock()
result_mock = MagicMock()
result_mock.fetchall.return_value = []
conn.execute.return_value = result_mock

result = estimate_sequence_timeline('000000000000', conn=conn)
assert result is None, f'Expected None, got {result}'
print('PASS: returns None when no addenda')
"
```

PASS: prints `PASS`
FAIL: AssertionError

---

## Step 6: Sequential stations summed (unit)

```
source .venv/bin/activate
python -c "
from unittest.mock import MagicMock
from src.tools.estimate_timeline import estimate_sequence_timeline

conn = MagicMock()
call_n = [0]

def _execute(sql, params=None):
    r = MagicMock()
    if 'SELECT 1 FROM station_velocity_v2' in sql:
        r.fetchall.return_value = [(1,)]
        return r
    if 'FROM addenda' in sql:
        r.fetchall.return_value = [('BLDG', '2024-01-10', '2024-02-10'), ('CP-ZOC', '2024-02-11', '2024-03-11')]
        return r
    if 'FROM station_velocity_v2' in sql:
        r.fetchall.return_value = [
            ('BLDG', 30.0, 20.0, 45.0, 60.0, 500, 'current'),
            ('CP-ZOC', 20.0, 15.0, 30.0, 45.0, 200, 'current'),
        ]
        return r
    r.fetchall.return_value = []
    return r

conn.execute.side_effect = _execute
result = estimate_sequence_timeline('202200000001', conn=conn)
assert result['total_estimate_days'] == 50.0, f'Expected 50.0, got {result[\"total_estimate_days\"]}'
print('PASS: sequential stations summed correctly')
"
```

PASS: prints `PASS`
FAIL: AssertionError

---

## Step 7: Result structure is correct

From Step 6 above — if that passes, also verify:

PASS: result contains keys `permit_number`, `stations`, `total_estimate_days`, `confidence`
FAIL: missing any required key

---

QA READY: qa-drop/sprint-76-1-sequence-timeline-qa.md | 2 scenarios appended to scenarios-pending-review.md
