## SUGGESTED SCENARIO: Admin views request performance dashboard

**Source:** web/routes_admin.py (admin_perf route), web/templates/admin_perf.html
**User:** admin
**Starting state:** Admin is logged in. The app has been running for at least a few minutes and some requests have been sampled into request_metrics (slow requests > 200ms or 10% random sample).
**Goal:** Admin wants to understand which endpoints are slowest and what the overall latency profile looks like.
**Expected outcome:** Admin sees p50/p95/p99 latency stat blocks at the top, a table of the 10 slowest endpoints by p95, and a volume table showing traffic by path. Empty state messages appear if no data has been collected yet.
**Edge cases seen in code:** If the request_metrics table is empty (fresh deploy), all stat blocks show 0ms and both tables show an empty state message rather than errors.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Request metrics are sampled automatically

**Source:** web/app.py (_slow_request_log after_request hook)
**User:** admin
**Starting state:** Admin is observing the system. Any user makes requests to the app.
**Goal:** Admin wants request performance data to accumulate passively without manual instrumentation.
**Expected outcome:** Requests slower than 200ms are always recorded. Approximately 10% of all other requests are recorded via random sampling. Recording never causes a request to fail — DB errors in metric capture are swallowed silently and the response still returns normally.
**Edge cases seen in code:** The metric insert happens only when `g._request_start` is set (i.e., request went through `_set_start_time`). Static file requests that bypass the before_request hook will not be recorded.
**CC confidence:** high
**Status:** PENDING REVIEW
