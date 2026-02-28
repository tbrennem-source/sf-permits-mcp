# CHANGELOG — Sprint 83-B: page_cache test flakiness fix

## Fix: Eliminate page_cache test flakiness in full suite runs

### Root cause

`test_qs3_a_permit_prep.py` calls `importlib.reload(src.db)` inside its `app`
fixture. This resets `src.db._DUCKDB_PATH` from the session-scoped temp path
(set by `_isolated_test_db` in conftest.py) back to the real database path
(`data/sf_permits.duckdb`). After `test_qs3_a_permit_prep.py` finishes and
yields, `_DUCKDB_PATH` is left pointing to the real DB — not restored.

When `test_page_cache.py` tests run next, every call to `get_cached_or_compute`
tries to open `data/sf_permits.duckdb`. The TEST GUARD in conftest.py catches
this and raises `RuntimeError: TEST GUARD: Attempted to open the real DuckDB
file`. This exception is silently swallowed by the `except Exception: pass`
blocks inside `get_cached_or_compute`, causing every cache read and write to
fail invisibly. The result: `compute_fn` is called on every invocation, so
tests that assert `compute_fn` was called exactly once (like
`test_cache_hit_returns_cached`) fail with `assert 2 == 1`.

### Fix

**`tests/conftest.py`** — Added `_restore_db_path` autouse fixture (function
scope). Saves `src.db._DUCKDB_PATH`, `src.db.BACKEND`, and `src.db.DATABASE_URL`
before each test, then restores them in teardown. This ensures that any test
which reloads `src.db` via `importlib.reload()` — or otherwise mutates these
module-level globals — cannot pollute the DB state for subsequent tests.

**`tests/test_page_cache.py`** — Updated `_clear_page_cache` autouse fixture to
`DELETE FROM page_cache` (all rows) instead of the pattern-matched
`WHERE cache_key LIKE 'test:%' OR cache_key LIKE 'brief:%'`. This is belt-and-
suspenders: even if a test writes a cache entry under an unexpected prefix, the
next test starts with a clean slate.

### Verification

- `pytest tests/test_page_cache.py` — 16/16 passed (was always passing)
- `pytest tests/test_qs3_a_permit_prep.py tests/test_page_cache.py` — all page_cache tests now pass (was 9 failures)
- `pytest tests/test_auth.py tests/test_page_cache.py` — all pass
- `pytest tests/test_web.py tests/test_page_cache.py` — all pass
- `pytest tests/test_auth.py tests/test_brief.py tests/test_page_cache.py` — all page_cache tests pass
