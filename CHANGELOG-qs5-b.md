## QS5-B: Permit Changes Backfill + Incremental Ingest (2026-02-26)

### Added
- `ingest_recent_permits()` in `src/ingest.py` — incremental ingest of recently-filed permits via SODA API with upsert (ON CONFLICT DO UPDATE)
- `POST /cron/ingest-recent-permits` endpoint in `web/routes_cron.py` — CRON_SECRET-protected, with sequencing guard that skips if full_ingest completed recently
- `backfill_orphan_permits()` in `scripts/nightly_changes.py` — queries orphan permit_changes and backfills from SODA in batches of 50
- `--backfill` CLI flag for `nightly_changes.py` — run `python -m scripts.nightly_changes --backfill` to clear existing orphans
- Incremental ingest step (Step 0) in `run_nightly()` pipeline — runs BEFORE change detection to reduce false orphans
- 12 new tests in `tests/test_qs5_b_backfill.py`
- 2 scenarios proposed

### Architecture Notes
- Incremental ingest is non-fatal in the nightly pipeline — if it fails, change detection still runs
- Sequencing guard prevents incremental ingest from running concurrently with full table replace
- Uses existing `_PgConnWrapper` pattern for Postgres compatibility
- Backfill processes orphans in chunks of 50 to avoid SODA query limits
