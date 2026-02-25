# Sprint 55 — QA Script

**Sprint:** 55
**Date:** 2026-02-25
**Scope:** Full dataset coverage (7 new datasets), reference tables, MCP tool enrichment, morning brief enhancements, nightly pipeline expansion

---

## Prerequisites

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
source .venv/bin/activate
```

Set CRON_SECRET in your shell (replace with actual value from Railway):
```bash
export CRON_SECRET="<your-cron-secret>"
export STAGING_URL="https://sfpermits-ai-staging-production.up.railway.app"
```

---

## Step 1: Health endpoint shows all new tables

```bash
curl -s "$STAGING_URL/health" | python3 -m json.tool
```

**PASS:** Response contains `"status": "ok"` and `tables` object includes at minimum:
- `street_use_permits` with `row_count > 0` (after ingest) or `row_count >= 0`
- `development_pipeline` with `row_count >= 0`
- `affordable_housing` with `row_count >= 0`
- `housing_production` with `row_count >= 0`
- `dwelling_completions` with `row_count >= 0`
- `ref_zoning_routing` with `row_count >= 29`
- `ref_permit_forms` with `row_count >= 28`
- `ref_agency_triggers` with `row_count >= 38`

**FAIL:** Any new table missing from `tables` object, or `status != "ok"`

---

## Step 2: permits table has electrical and plumbing rows

```bash
curl -s "$STAGING_URL/health" | python3 -c "
import sys, json
h = json.load(sys.stdin)
tables = h.get('tables', {})
permits = tables.get('permits', {})
print('permits row_count:', permits.get('row_count', 0))
"
```

Then verify via MCP tool that trade permits are queryable (requires local DB access):
```bash
python3 - << 'PYEOF'
from src.db import get_db_connection
conn = get_db_connection()
result = conn.execute("""
    SELECT permit_type_definition, COUNT(*) as cnt
    FROM permits
    WHERE permit_type_definition ILIKE '%electrical%'
       OR permit_type_definition ILIKE '%plumbing%'
    GROUP BY permit_type_definition
    ORDER BY cnt DESC
    LIMIT 10
""").fetchall()
for row in result:
    print(row)
conn.close()
PYEOF
```

**PASS:** At least one row returned for electrical and one for plumbing; combined count > 100K
**FAIL:** Zero rows for either trade type, or error connecting to DB

---

## Step 3: Reference tables are seeded

```bash
python3 - << 'PYEOF'
from src.db import get_db_connection
conn = get_db_connection()
for table in ['ref_zoning_routing', 'ref_permit_forms', 'ref_agency_triggers']:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table}: {count} rows")
conn.close()
PYEOF
```

**PASS:** ref_zoning_routing >= 29, ref_permit_forms >= 28, ref_agency_triggers >= 38
**FAIL:** Any table has 0 rows, or table does not exist (SQL error)

---

## Step 4: Cross-ref check passes (all rates > 5%)

```bash
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$STAGING_URL/cron/cross-ref-check" | python3 -m json.tool
```

**PASS:** Response contains match rate entries; all rates are > 5% (or explicitly noted as expected-low)
**FAIL:** Any rate shown as 0% or endpoint returns 4xx/5xx

---

## Step 5: Signal pipeline has property_health > 0

```bash
python3 - << 'PYEOF'
from src.db import get_db_connection
conn = get_db_connection()
count = conn.execute("SELECT COUNT(*) FROM property_health").fetchone()[0]
print(f"property_health rows: {count}")
conn.close()
PYEOF
```

**PASS:** count > 0
**FAIL:** count == 0 or table does not exist

---

## Step 6: Cron endpoints reject unauthenticated requests

Test 3 of the new endpoints:
```bash
# No auth header — should return 403
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$STAGING_URL/cron/ingest-electrical"
echo ""

curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$STAGING_URL/cron/ingest-street-use"
echo ""

curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$STAGING_URL/cron/seed-references"
echo ""
```

**PASS:** All 3 return `403`
**FAIL:** Any endpoint returns 200 without auth, or returns 500

Also test with wrong token:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer wrongtoken" \
  -X POST "$STAGING_URL/cron/ingest-electrical"
echo ""
```

**PASS:** Returns `403`
**FAIL:** Returns 200 or 500

---

## Step 7: Morning brief includes planning_context, compliance_calendar, data_quality keys

```bash
python3 - << 'PYEOF'
import os, sys
sys.path.insert(0, '.')
from web.brief import get_brief_data

# Mock minimal context
data = get_brief_data(watched_items=[], user_id=None)
keys = list(data.keys()) if data else []
print("Brief keys:", keys)
for key in ['planning_context', 'compliance_calendar', 'data_quality']:
    present = key in data if data else False
    print(f"  {key}: {'PRESENT' if present else 'MISSING'}")
PYEOF
```

**PASS:** All 3 keys present in brief data (values may be empty lists/dicts for test environment with no watches)
**FAIL:** Any key missing from returned dict

---

## Step 8: pytest passes (1964+)

```bash
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py 2>&1 | tail -5
```

**PASS:** Output shows `1964 passed` (or more), `20 skipped`, `0 failed`
**FAIL:** Any failures, or passed count < 1820 (pre-sprint baseline)

---

## Step 9: permit_lookup returns planning records for a known parcel

```bash
python3 - << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '.')
from src.tools.permit_lookup import permit_lookup_tool

async def run():
    # Use block 3512, lot 001 — a known SF parcel
    result = await permit_lookup_tool(block="3512", lot="001")
    text = result if isinstance(result, str) else str(result)
    print("Output length:", len(text))
    has_planning = "planning" in text.lower()
    print("Contains 'planning':", has_planning)
    print("First 500 chars:", text[:500])

asyncio.run(run())
PYEOF
```

**PASS:** Response is returned without error; response includes "planning" keyword (even if no records found, section header should appear)
**FAIL:** Exception raised, or response is empty

---

## Step 10: property_lookup returns local tax data for a known block/lot

```bash
python3 - << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '.')
from src.tools.property_lookup import property_lookup_tool

async def run():
    # Use block 3512, lot 001
    result = await property_lookup_tool(block="3512", lot="001")
    text = result if isinstance(result, str) else str(result)
    print("Output length:", len(text))
    has_zoning = any(kw in text.lower() for kw in ['zoning', 'tax', 'assessed', 'lot_area'])
    print("Contains property data:", has_zoning)
    print("First 500 chars:", text[:500])

asyncio.run(run())
PYEOF
```

**PASS:** Response returned without error; contains at least one of: zoning, tax, assessed, lot_area keyword
**FAIL:** Exception raised, or response is empty, or no property data keywords found

---

## Summary Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Health endpoint shows all new tables | |
| 2 | permits table has electrical + plumbing rows | |
| 3 | Reference tables seeded (29/28/38 rows) | |
| 4 | Cross-ref check passes (rates > 5%) | |
| 5 | Signal pipeline has property_health > 0 | |
| 6 | Cron endpoints reject unauthenticated (3 endpoints, 403) | |
| 7 | Morning brief has planning_context, compliance_calendar, data_quality | |
| 8 | pytest: 1964+ passed, 0 failed | |
| 9 | permit_lookup returns planning section for known parcel | |
| 10 | property_lookup returns local tax data for known block/lot | |
