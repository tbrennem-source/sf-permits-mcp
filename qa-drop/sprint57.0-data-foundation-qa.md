# Sprint 57.0 Data Foundation QA Script

## Prerequisites
- DuckDB at `data/sf_permits.duckdb` has been processed by entity resolution + graph rebuild + velocity refresh
- venv activated: `source .venv/bin/activate`

---

## 1. Test Suite Passes
```bash
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py -x
```
- [ ] PASS: 2000+ tests pass (baseline was 1,965)
- [ ] PASS: 0 failures

## 2. Entity Resolution Counts
```python
import duckdb
conn = duckdb.connect('data/sf_permits.duckdb', read_only=True)
for src_type in ['building', 'electrical', 'plumbing']:
    total = conn.execute(f"SELECT COUNT(DISTINCT entity_id) FROM contacts WHERE source = '{src_type}'").fetchone()[0]
    singletons = conn.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT entity_id, COUNT(*) c
            FROM contacts WHERE source = '{src_type}'
            GROUP BY entity_id HAVING c = 1
        )
    """).fetchone()[0]
    rate = singletons / total * 100 if total > 0 else 0
    print(f'{src_type}: {total:,} entities, {singletons:,} singletons ({rate:.1f}%)')
conn.close()
```
- [ ] PASS: Electrical entity count < 12,000 (was 14,180)
- [ ] PASS: Plumbing entity count < 14,000 (was 16,742)
- [ ] PASS: Building entity count within ±5% of 983K (not degraded)
- [ ] PASS: Architect singleton rate < 90%

## 3. Relationship Graph Integrity
```python
import duckdb
conn = duckdb.connect('data/sf_permits.duckdb', read_only=True)
edges = conn.execute('SELECT COUNT(*) FROM relationships').fetchone()[0]
max_weight = conn.execute('SELECT MAX(shared_permits) FROM relationships').fetchone()[0]
orphans = conn.execute("""
    SELECT COUNT(*) FROM relationships r
    WHERE NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.entity_id_a)
       OR NOT EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = r.entity_id_b)
""").fetchone()[0]
print(f'Edges: {edges:,}, Max weight: {max_weight}, Orphan edges: {orphans}')
conn.close()
```
- [ ] PASS: edges > 0
- [ ] PASS: orphan edges = 0

## 4. Velocity Periods
```python
import duckdb
conn = duckdb.connect('data/sf_permits.duckdb', read_only=True)
for period in ['current', 'baseline']:
    ct = conn.execute(f"SELECT COUNT(*) FROM station_velocity_v2 WHERE period = '{period}'").fetchone()[0]
    print(f'{period}: {ct} rows')
conn.close()
```
- [ ] PASS: 'current' period has > 0 rows
- [ ] PASS: 'baseline' period has > 0 rows

## 5. Neighborhood Backfill (local self-join test)
```python
import duckdb
conn = duckdb.connect('data/sf_permits.duckdb', read_only=True)
null_ct = conn.execute('SELECT COUNT(*) FROM permits WHERE neighborhood IS NULL').fetchone()[0]
print(f'NULL neighborhoods: {null_ct:,}')
conn.close()
```
- [ ] PASS: NULL neighborhoods < 50,000 (was 847K)
- NOTE: Full backfill uses tax_rolls (prod only). Local test uses self-join on permits block/lot.

## 6. Trade Permit Filter in Timeline
```python
from src.tools.estimate_timeline import _query_timeline
import duckdb

# Verify the filter is in the SQL
import inspect
src = inspect.getsource(_query_timeline)
assert "Electrical Permit" in src, "Trade filter not found"
assert "Plumbing Permit" in src, "Trade filter not found"
assert "1 year" in src, "Recency filter not found"
print("Trade permit filter: PASS")
```
- [ ] PASS: Trade permit exclusion and recency filter present in _query_timeline

## 7. Multi-Role Entity Tracking
```python
import duckdb
conn = duckdb.connect('data/sf_permits.duckdb', read_only=True)
multi = conn.execute("SELECT COUNT(*) FROM entities WHERE roles IS NOT NULL AND roles LIKE '%,%'").fetchone()[0]
print(f'Entities with multiple roles: {multi:,}')
conn.close()
```
- [ ] PASS: multi-role entities > 0

## 8. License Normalization Verification
```python
from src.entities import _normalize_license
assert _normalize_license("0012345") == "12345"
assert _normalize_license("C-10") == "C10"
assert _normalize_license("c10") == "C10"
assert _normalize_license(None) is None
print("License normalization: PASS")
```
- [ ] PASS: All assertions pass

## 9. Migration Registry
```python
from scripts.run_prod_migrations import MIGRATIONS
names = [m.name for m in MIGRATIONS]
assert "neighborhood_backfill" in names, f"Missing: {names}"
assert names.index("neighborhood_backfill") > names.index("inspections_unique"), "Wrong order"
print(f"Migrations: {len(MIGRATIONS)} total, neighborhood_backfill at position {names.index('neighborhood_backfill') + 1}")
```
- [ ] PASS: neighborhood_backfill migration exists and is after inspections_unique
