## SUGGESTED SCENARIO: Cron endpoint rejects unauthenticated requests with 403
**Source:** tests/test_brief_cache.py, tests/test_sprint_79_3.py — CRON_WORKER env var audit
**User:** admin
**Starting state:** CRON_WORKER=1 is set (cron worker mode active), CRON_SECRET is set to a known value
**Goal:** Verify that /cron/* endpoints reject requests without a valid CRON_SECRET bearer token
**Expected outcome:** POST to any /cron/* endpoint without Authorization header returns 403; wrong token also returns 403; only the correct bearer token grants access
**Edge cases seen in code:** Some endpoints check for missing header vs wrong secret separately; both should return 403 (not 500)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Cron endpoint returns 404 when CRON_WORKER not set (guard behavior)
**Source:** tests/test_station_velocity_v2.py, tests/test_db_backup.py, tests/test_reference_tables.py — CRON_GUARD pattern
**User:** admin
**Starting state:** CRON_WORKER env var is NOT set (web worker mode, the default)
**Goal:** Verify that the cron guard blocks POST requests to /cron/* routes on web workers
**Expected outcome:** POST to /cron/* returns 404 (not 403, not 500) — the cron guard intercepts before auth; GET requests to /cron/* are still allowed through on web workers
**Edge cases seen in code:** GET /cron/status and GET /cron/pipeline-health are allowed on web workers; only POST is blocked; the 404 comes from the guard before any route handler runs
**CC confidence:** high
**Status:** PENDING REVIEW
