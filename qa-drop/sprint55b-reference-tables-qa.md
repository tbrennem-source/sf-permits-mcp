# QA Script: Sprint 55B — Reference Tables for predict_permits

**Session:** sprint55b-agent-b
**Feature:** Reference tables (ref_zoning_routing, ref_permit_forms, ref_agency_triggers)
**Type:** CLI-only (no browser required)

---

## Step 1: Tables created by init_schema

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_schema
init_schema(conn)
tables = {r[0] for r in conn.execute(\"SELECT table_name FROM information_schema.tables\").fetchall()}
required = {'ref_zoning_routing', 'ref_permit_forms', 'ref_agency_triggers'}
missing = required - tables
print('PASS' if not missing else f'FAIL missing: {missing}')
conn.close()
os.unlink(tmp)
"
```

**PASS:** Prints `PASS`
**FAIL:** Prints `FAIL missing: {...}`

---

## Step 2: Tables created by init_user_schema

```bash
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_user_schema
init_user_schema(conn)
tables = {r[0] for r in conn.execute(\"SELECT table_name FROM information_schema.tables\").fetchall()}
required = {'ref_zoning_routing', 'ref_permit_forms', 'ref_agency_triggers'}
missing = required - tables
print('PASS' if not missing else f'FAIL missing: {missing}')
conn.close()
os.unlink(tmp)
"
```

**PASS:** Prints `PASS`
**FAIL:** Prints `FAIL missing: {...}`

---

## Step 3: Seed script runs without error

```bash
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_schema
init_schema(conn)
from scripts.seed_reference_tables import (
    ZONING_ROUTING_ROWS, PERMIT_FORMS_ROWS, AGENCY_TRIGGERS_ROWS,
    _upsert_zoning_routing, _upsert_permit_forms, _upsert_agency_triggers
)
_upsert_zoning_routing(conn, 'duckdb', ZONING_ROUTING_ROWS)
_upsert_permit_forms(conn, 'duckdb', PERMIT_FORMS_ROWS)
_upsert_agency_triggers(conn, 'duckdb', AGENCY_TRIGGERS_ROWS)
z = conn.execute('SELECT COUNT(*) FROM ref_zoning_routing').fetchone()[0]
f = conn.execute('SELECT COUNT(*) FROM ref_permit_forms').fetchone()[0]
t = conn.execute('SELECT COUNT(*) FROM ref_agency_triggers').fetchone()[0]
print(f'PASS zoning={z} forms={f} triggers={t}' if z>0 and f>0 and t>0 else f'FAIL z={z} f={f} t={t}')
conn.close()
os.unlink(tmp)
"
```

**PASS:** `PASS zoning=N forms=N triggers=N` where all N > 0
**FAIL:** Any FAIL output or exception

---

## Step 4: Common SF zoning codes present

```bash
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_schema
init_schema(conn)
from scripts.seed_reference_tables import ZONING_ROUTING_ROWS, _upsert_zoning_routing
_upsert_zoning_routing(conn, 'duckdb', ZONING_ROUTING_ROWS)
codes = {r[0] for r in conn.execute('SELECT zoning_code FROM ref_zoning_routing').fetchall()}
required = {'RC-4', 'RH-1', 'NC-2', 'C-3-O', 'PDR-1-G'}
missing = required - codes
print('PASS' if not missing else f'FAIL missing: {missing}')
conn.close()
os.unlink(tmp)
"
```

**PASS:** `PASS`
**FAIL:** `FAIL missing: {...}`

---

## Step 5: RC-4 has planning+fire review; RH-1 does not

```bash
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_schema
init_schema(conn)
from scripts.seed_reference_tables import ZONING_ROUTING_ROWS, _upsert_zoning_routing
_upsert_zoning_routing(conn, 'duckdb', ZONING_ROUTING_ROWS)
rc4 = conn.execute(\"SELECT planning_review_required, fire_review_required FROM ref_zoning_routing WHERE zoning_code='RC-4'\").fetchone()
rh1 = conn.execute(\"SELECT planning_review_required FROM ref_zoning_routing WHERE zoning_code='RH-1'\").fetchone()
ok = rc4 and rc4[0] and rc4[1] and rh1 and not rh1[0]
print('PASS' if ok else f'FAIL rc4={rc4} rh1={rh1}')
conn.close()
os.unlink(tmp)
"
```

**PASS:** `PASS`
**FAIL:** `FAIL rc4=... rh1=...`

---

## Step 6: Idempotency — double seed yields same counts

```bash
python -c "
import duckdb, tempfile, os
tmp = tempfile.mktemp(suffix='.duckdb')
conn = duckdb.connect(tmp)
from src.db import init_schema
init_schema(conn)
from scripts.seed_reference_tables import ZONING_ROUTING_ROWS, _upsert_zoning_routing
_upsert_zoning_routing(conn, 'duckdb', ZONING_ROUTING_ROWS)
c1 = conn.execute('SELECT COUNT(*) FROM ref_zoning_routing').fetchone()[0]
_upsert_zoning_routing(conn, 'duckdb', ZONING_ROUTING_ROWS)
c2 = conn.execute('SELECT COUNT(*) FROM ref_zoning_routing').fetchone()[0]
print('PASS' if c1 == c2 else f'FAIL: {c1} -> {c2} (duplicates!)')
conn.close()
os.unlink(tmp)
"
```

**PASS:** `PASS`
**FAIL:** `FAIL: N -> M (duplicates!)`

---

## Step 7: Migration registry has reference_tables entry

```bash
python -c "
from scripts.run_prod_migrations import MIGRATIONS
names = [m.name for m in MIGRATIONS]
has_rt = 'reference_tables' in names
is_last = names[-1] == 'reference_tables'
print(f'PASS last={is_last}' if has_rt else 'FAIL: reference_tables not in MIGRATIONS')
"
```

**PASS:** `PASS last=True`
**FAIL:** Any FAIL output

---

## Step 8: pytest test_reference_tables all pass

```bash
pytest tests/test_reference_tables.py -v 2>&1 | tail -5
```

**PASS:** `21 passed`
**FAIL:** Any FAILED lines

---

## Step 9: Cron endpoint returns 403 without auth

```bash
python -c "
import os
os.environ.setdefault('CRON_SECRET', 'test-secret')
os.environ.setdefault('SECRET_KEY', 'test-key')
from web.app import app
app.config['TESTING'] = True
c = app.test_client()
r = c.post('/cron/seed-references')
print('PASS' if r.status_code == 403 else f'FAIL: got {r.status_code}')
"
```

**PASS:** `PASS`
**FAIL:** `FAIL: got N`

---

## Step 10: Full test suite no regressions

```bash
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py 2>&1 | tail -3
```

**PASS:** `N passed, M skipped` with 0 failed
**FAIL:** Any `failed` in output
