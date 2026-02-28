## SUGGESTED SCENARIO: Page cache returns cached result on second request
**Source:** tests/test_page_cache.py — TestCacheMissAndHit
**User:** expediter | homeowner | architect | admin
**Starting state:** Page cache is empty (no cached entry for the requested key)
**Goal:** Retrieve the same data twice — the second request should be served from cache without recomputing
**Expected outcome:** The compute function is called exactly once; the second response includes `_cached: true` and `_cached_at` timestamp indicating it was served from cache
**Edge cases seen in code:** TTL=0 forces every read to recompute; large nested payloads (100 items) round-trip without truncation; empty dict `{}` is cached and annotated correctly
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Page cache cleanup prevents cross-test contamination
**Source:** tests/conftest.py — _restore_db_path fixture; tests/test_page_cache.py — _clear_page_cache fixture
**User:** admin
**Starting state:** A prior test (e.g. test_qs3_a_permit_prep.py) called importlib.reload(src.db), resetting _DUCKDB_PATH to the real database path rather than the session temp path
**Goal:** Subsequent page_cache tests should still connect to the correct session-scoped temp database and see cache entries they wrote in the same test
**Expected outcome:** The `_restore_db_path` conftest fixture restores `_DUCKDB_PATH`, `BACKEND`, and `DATABASE_URL` after each test; the `_clear_page_cache` fixture truncates all rows from page_cache so no stale key from any prefix can produce a false hit
**Edge cases seen in code:** TEST GUARD in conftest raises RuntimeError when the real DB path is opened during tests — this RuntimeError was silently swallowed by get_cached_or_compute's bare `except Exception: pass`, causing every cache read to silently fail and compute_fn to be called on every request
**CC confidence:** high
**Status:** PENDING REVIEW
