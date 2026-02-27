## SUGGESTED SCENARIO: cost kill switch blocks AI routes without affecting browsing

**Source:** web/app.py _kill_switch_guard + web/cost_tracking.py
**User:** homeowner
**Starting state:** Admin has activated the API kill switch (daily spend exceeded $20). User is browsing the site and tries to use the AI analysis tool.
**Goal:** User submits a project description to the /ask or /analyze endpoint while kill switch is active.
**Expected outcome:** User receives a clear error message saying AI features are temporarily unavailable (cost protection), with a prompt to try again later. All non-AI pages (home, property reports, search) continue to function normally.
**Edge cases seen in code:** Kill switch check happens in before_request hook before rate limiter or view function runs. JSON 503 response with kill_switch=True field. Health endpoint never blocked.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: daily API usage aggregation rolls up to summary table

**Source:** web/cost_tracking.py aggregate_daily_usage + web/routes_cron.py cron_aggregate_api_usage
**User:** admin
**Starting state:** api_usage table has entries from yesterday's activity (user queries, plan analyses).
**Goal:** Nightly cron job runs POST /cron/aggregate-api-usage to produce a daily summary for the dashboard.
**Expected outcome:** api_daily_summary table has a row for yesterday with correct total_calls, total_cost_usd, and endpoint breakdown. Subsequent runs are idempotent (UPSERT). Admin cost dashboard reflects up-to-date daily totals.
**Edge cases seen in code:** Missing api_usage table handled gracefully (returns inserted=False, no crash). Optional ?date=YYYY-MM-DD param for back-filling. Defaults to yesterday.
**CC confidence:** high
**Status:** PENDING REVIEW
