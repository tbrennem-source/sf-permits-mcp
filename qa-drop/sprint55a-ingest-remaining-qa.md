# QA Script: Sprint 55A — Ingest Remaining + Cron Endpoints

## Session: sprint55a-ingest-remaining
## Feature: Cron endpoints for electrical/plumbing + 5 new dataset schemas/ingest

---

## 1. pytest — new test suite

```bash
source .venv/bin/activate
pytest tests/test_ingest_remaining.py -v
```

**PASS:** 81 tests pass, 0 fail
**FAIL:** Any test failure

---

## 2. pytest — full regression check

```bash
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py
```

**PASS:** No new failures vs baseline (1865 passed, 20 skipped)
**FAIL:** Any test that was previously passing now fails

---

## 3. DATASETS dict — new entries present

```python
source .venv/bin/activate
python3 -c "
from src.ingest import DATASETS
keys = ['street_use_permits', 'development_pipeline', 'affordable_housing', 'housing_production', 'dwelling_completions']
for k in keys:
    assert k in DATASETS, f'Missing: {k}'
    eid = DATASETS[k]['endpoint_id']
    import re
    assert re.match(r'^[a-z0-9]{4}-[a-z0-9]{4}$', eid), f'Bad endpoint_id: {eid}'
    print(f'  OK: {k} -> {eid}')
print('ALL PASS')
"
```

**PASS:** Prints "ALL PASS" with 5 OK lines
**FAIL:** Any assertion error

---

## 4. Schema check — all 5 new tables created

```python
source .venv/bin/activate
python3 -c "
import src.db as db_mod
import duckdb, tempfile, os
with tempfile.TemporaryDirectory() as d:
    db_path = os.path.join(d, 'test.duckdb')
    import os; os.environ['SF_PERMITS_DB'] = db_path
    db_mod.BACKEND = 'duckdb'
    db_mod._DUCKDB_PATH = db_path
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    tables = conn.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name\").fetchall()
    names = {t[0] for t in tables}
    for t in ['street_use_permits', 'development_pipeline', 'affordable_housing', 'housing_production', 'dwelling_completions']:
        assert t in names, f'Missing table: {t}'
        print(f'  OK: {t}')
    conn.close()
print('ALL TABLES PRESENT')
"
```

**PASS:** Prints all 5 table names + "ALL TABLES PRESENT"
**FAIL:** Any assertion error or missing table

---

## 5. Cron endpoint auth — electrical and plumbing

```bash
# Without auth (should return 403)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5001/cron/ingest-electrical
# Expected: 403

curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5001/cron/ingest-plumbing
# Expected: 403
```

**PASS:** Both return 403
**FAIL:** Either returns 200 or any other code

---

## 6. Cron endpoint auth — 5 new datasets

```bash
for endpoint in ingest-street-use ingest-development-pipeline ingest-affordable-housing ingest-housing-production ingest-dwelling-completions; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5001/cron/$endpoint)
  echo "$endpoint: $code"
done
# Expected: all 5 return 403
```

**PASS:** All 5 return 403
**FAIL:** Any endpoint returns 200 or 404

---

## 7. run_ingestion() signature check

```python
source .venv/bin/activate
python3 -c "
import inspect
from src.ingest import run_ingestion
sig = inspect.signature(run_ingestion)
params = sig.parameters
new_params = ['street_use', 'development_pipeline', 'affordable_housing', 'housing_production', 'dwelling_completions']
for p in new_params:
    assert p in params, f'Missing param: {p}'
    assert params[p].default is True, f'{p} should default to True'
    print(f'  OK: {p} (default=True)')
print('SIGNATURE OK')
"
```

**PASS:** Prints "SIGNATURE OK" with 5 OK lines
**FAIL:** Any assertion error

---

## 8. CLI flags — new datasets

```bash
source .venv/bin/activate
python3 -m src.ingest --help
# Expected: --street-use, --development-pipeline, --affordable-housing, --housing-production, --dwelling-completions all appear
```

**PASS:** All 5 new flags appear in help output
**FAIL:** Any new flag is missing

---

## 9. Normalizer field mapping spot check

```python
source .venv/bin/activate
python3 -c "
from src.ingest import _normalize_street_use_permit, _normalize_dwelling_completion

# Street-use: unique_identifier used as PK
r1 = _normalize_street_use_permit({'unique_identifier': 'X_Y', 'permit_number': 'X', 'analysis_neighborhood': 'SoMa'})
assert r1[0] == 'X_Y', f'Expected X_Y, got {r1[0]}'
assert r1[13] == 'SoMa', f'Expected SoMa, got {r1[13]}'
print('  street_use: OK')

# Dwelling: integer parsing
r2 = _normalize_dwelling_completion({'building_permit_application': 'P1', 'number_of_units_certified': '68'}, 42)
assert r2[0] == 42
assert r2[5] == 68
print('  dwelling_completions: OK')
print('NORMALIZERS OK')
"
```

**PASS:** Prints "NORMALIZERS OK"
**FAIL:** Any assertion error

---

## 10. postgres_schema.sql — all 5 new CREATE TABLE blocks present

```bash
grep -c "CREATE TABLE IF NOT EXISTS" scripts/postgres_schema.sql
# Expected: 20 (15 existing + 5 new)
grep "CREATE TABLE IF NOT EXISTS" scripts/postgres_schema.sql | grep -E "street_use_permits|development_pipeline|affordable_housing|housing_production|dwelling_completions"
# Expected: 5 lines
```

**PASS:** 20 total CREATE TABLE statements, 5 new ones visible
**FAIL:** Count < 20 or any new table name missing
