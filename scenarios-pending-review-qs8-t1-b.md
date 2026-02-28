## SUGGESTED SCENARIO: morning brief shows pipeline health stats
**Source:** web/brief.py — _get_pipeline_stats(), get_morning_brief()
**User:** admin
**Starting state:** Nightly cron has run at least once; cron_log has records
**Goal:** User opens morning brief and sees pipeline health summary (avg job duration, 24h success/fail counts)
**Expected outcome:** Brief data includes pipeline_stats with recent_jobs list and 24h counts; average duration is computed from successful runs; non-fatal if cron_log is empty or unavailable
**Edge cases seen in code:** If DB unavailable, pipeline_stats returns {} — brief still renders without it
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: signals cron endpoint logs to cron_log
**Source:** web/routes_cron.py — cron_signals()
**User:** admin
**Starting state:** CRON_SECRET configured; signals pipeline operational
**Goal:** Scheduler calls POST /cron/signals to run signal detection
**Expected outcome:** Job start logged as 'running', completion logged as 'success' or 'failed' with elapsed time; response includes ok, status, elapsed_seconds; failure does not crash the endpoint (returns ok=False)
**Edge cases seen in code:** cron_log insert failure is non-fatal (logged as warning); pipeline exception returns HTTP 500 with ok=False
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: velocity-refresh cron endpoint logs to cron_log
**Source:** web/routes_cron.py — cron_velocity_refresh()
**User:** admin
**Starting state:** CRON_SECRET configured; addenda table populated with routing data
**Goal:** Scheduler calls POST /cron/velocity-refresh to refresh station velocity baselines
**Expected outcome:** Velocity refresh runs, transitions and congestion sub-steps also attempted (non-fatal); all logged to cron_log; response includes rows_inserted, stations, transitions; partial failures (transitions/congestion) don't fail overall job
**Edge cases seen in code:** transitions failure logged as transitions_error key in response; congestion failure same pattern
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: pipeline stats unavailable at first deploy
**Source:** web/brief.py — _get_pipeline_stats()
**User:** admin
**Starting state:** Fresh deploy, cron_log table empty or not yet populated
**Goal:** Admin opens morning brief before any cron jobs have run
**Expected outcome:** Brief still renders; pipeline_stats is empty dict ({}); no error shown to user
**Edge cases seen in code:** Exception caught silently, returns {}
**CC confidence:** medium
**Status:** PENDING REVIEW
