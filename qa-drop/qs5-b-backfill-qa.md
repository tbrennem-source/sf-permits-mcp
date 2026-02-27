# QA: QS5-B Permit Changes Backfill

## CLI / Unit Checks (no browser needed)

1. [NEW] `ingest_recent_permits()` returns integer count
   - Run: `pytest tests/test_qs5_b_backfill.py::TestIngestRecentPermits::test_returns_integer_count -v`
   - Expected: PASS
   - [ ] PASS / FAIL

2. [NEW] `ingest_recent_permits()` does ON CONFLICT DO UPDATE (upsert, not error)
   - Run: `pytest tests/test_qs5_b_backfill.py::TestIngestRecentPermits::test_upsert_does_not_error_on_duplicate -v`
   - Expected: PASS
   - [ ] PASS / FAIL

3. [NEW] POST /cron/ingest-recent-permits requires CRON_SECRET
   - Run: `pytest tests/test_qs5_b_backfill.py::TestCronIngestRecentPermits::test_requires_cron_secret -v`
   - Expected: PASS
   - [ ] PASS / FAIL

4. [NEW] POST /cron/ingest-recent-permits returns upserted count
   - Run: `pytest tests/test_qs5_b_backfill.py::TestCronIngestRecentPermits::test_returns_upserted_count -v`
   - Expected: PASS
   - [ ] PASS / FAIL

5. [NEW] Sequencing guard skips when full_ingest ran recently
   - Run: `pytest tests/test_qs5_b_backfill.py::TestCronIngestRecentPermits::test_skips_if_full_ingest_recent -v`
   - Expected: PASS
   - [ ] PASS / FAIL

6. [NEW] `--backfill` flag accepted by nightly_changes.py
   - Run: `python -m scripts.nightly_changes --backfill --dry-run 2>&1 | head -5`
   - Expected: no argparse error, runs without crash
   - [ ] PASS / FAIL

7. [NEW] Pipeline ordering is documented in code
   - Run: `pytest tests/test_qs5_b_backfill.py::TestPipelineOrdering -v`
   - Expected: PASS (2 tests)
   - [ ] PASS / FAIL

8. [NEW] Full test suite still passes
   - Run: `pytest tests/ --ignore=tests/test_tools.py -q`
   - Expected: no new failures
   - [ ] PASS / FAIL
