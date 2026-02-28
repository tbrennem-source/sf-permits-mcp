# CHANGELOG — QS8-T1-A: Batch DB Queries + SODA Caching

## [QS8-T1-A] — 2026-02-27

### Performance: Property Report N+1 Fix (web/report.py)

**Problem:** Property report for a 44-permit parcel took ~11.6s. Root cause: `_get_contacts()` and `_get_inspections()` called once per permit in a loop = 88 serial DB queries.

**Solution:** Replaced per-permit loop with 2 batch queries.

#### New functions in `web/report.py`

**`_get_contacts_batch(conn, permit_numbers: list[str]) -> dict[str, list]`**
- Single `SELECT ... WHERE permit_number IN (...)` with LEFT JOIN to entities
- Returns `{permit_number: [contact_dict, ...]}` grouped by permit
- Handles both DuckDB (`?`) and Postgres (`%s`) placeholders via `_PH`
- Role ordering preserved: applicant → contractor → architect → engineer → other

**`_get_inspections_batch(conn, permit_numbers: list[str]) -> dict[str, list]`**
- Single `SELECT ... WHERE reference_number IN (...)` on inspections table
- Returns `{permit_number: [inspection_dict, ...]}` grouped by permit
- Ordered by scheduled_date DESC per permit

**`get_property_report()` loop change:**
```python
# BEFORE (N+1 — 88 queries for 44 permits):
for permit in permits:
    permit["contacts"] = _get_contacts(conn, pnum)
    permit["inspections"] = _get_inspections(conn, pnum)

# AFTER (2 queries total):
pnums = [p["permit_number"] for p in permits if p.get("permit_number")]
contacts_map = _get_contacts_batch(conn, pnums)
inspections_map = _get_inspections_batch(conn, pnums)
for permit in permits:
    permit["contacts"] = contacts_map.get(pnum, [])
    permit["inspections"] = inspections_map.get(pnum, [])
```

#### SODA Response Caching

**Module-level cache:** `_soda_cache: dict[str, tuple[float, Any]] = {}`
- TTL: 900 seconds (15 minutes)
- Cache key format: `{endpoint_id}:{block}:{lot}`
- Applies to: `_fetch_complaints`, `_fetch_violations`, `_fetch_property`
- Uses `time.monotonic()` — immune to system clock changes

**Impact:** Repeat renders of the same parcel within 15 minutes skip 3 SODA API calls.

### Tests Added

**`tests/test_sprint_79_1.py`** — 11 new tests:
- `test_get_contacts_batch_returns_grouped_dict` — verifies dict keyed by permit_number
- `test_get_contacts_batch_empty_list` — empty input returns {}
- `test_get_contacts_batch_unknown_permit` — missing permit returns []
- `test_get_contacts_batch_role_ordering` — applicant before contractor
- `test_get_inspections_batch_returns_grouped_dict` — same grouping pattern
- `test_get_inspections_batch_empty_list`
- `test_get_inspections_batch_unknown_permit`
- `test_soda_cache_hit_skips_api_call` — API called once, second call uses cache
- `test_soda_cache_expired_makes_new_api_call` — stale entry triggers fresh call
- `test_soda_cache_violations_hit_skips_api_call`
- `test_soda_cache_property_hit_skips_api_call`

### Files Changed
- `web/report.py` — batch helpers, SODA cache, loop replacement
- `tests/test_sprint_79_1.py` — new (11 tests, all passing)
