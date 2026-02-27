## SUGGESTED SCENARIO: Incremental permit ingest reduces orphan rate
**Source:** QS5-B ingest_recent_permits + backfill
**User:** admin
**Starting state:** permit_changes has 52% orphan rate (permits detected by nightly tracker but not in bulk permits table)
**Goal:** Reduce orphan rate by ingesting recently-filed permits before change detection runs
**Expected outcome:** After incremental ingest runs nightly, orphan rate in permit_changes drops below 10% because recently-filed permits are already in the permits table when detect_changes() runs
**Edge cases seen in code:** SODA API may return 0 records during quiet periods; pagination needed for >10K results; must not run concurrently with full_ingest
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly pipeline runs incremental ingest before change detection
**Source:** QS5-B pipeline ordering in run_nightly()
**User:** admin
**Starting state:** Nightly cron job triggers run_nightly() which detects permit changes
**Goal:** Prevent false "new_permit" entries by ensuring recently-filed permits are in the DB before change detection compares against it
**Expected outcome:** Pipeline sequence is: incremental ingest → fetch SODA changes → detect_changes(). The incremental ingest step is non-fatal — if it fails, change detection still runs.
**Edge cases seen in code:** Incremental ingest must not run if full_ingest completed recently (sequencing guard via cron_log check); DuckDB vs Postgres SQL differences handled by existing patterns
**CC confidence:** high
**Status:** PENDING REVIEW
