## SUGGESTED SCENARIO: Load test shows staging can handle launch traffic
**Source:** scripts/load_test.py
**User:** admin
**Starting state:** Staging app is running; load_test.py available in scripts/
**Goal:** Verify the app sustains 10 concurrent users for 30 seconds without errors on the landing, search, and health pages
**Expected outcome:** All scenarios return p95 latency < 2000ms and error rate < 5%
**Edge cases seen in code:** Script exits with code 1 if any scenario error_rate > 5%; results saved to load-test-results.json
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Load test CLI filters to a single scenario
**Source:** scripts/load_test.py
**User:** admin
**Starting state:** App is deployed; user wants to isolate health check performance
**Goal:** Run load test on health endpoint only with custom concurrency
**Expected outcome:** Only /health requests are made; JSON output contains only the "health" scenario key; summary table shows one row
**Edge cases seen in code:** --scenario argument is validated against the SCENARIOS registry; invalid names rejected by argparse
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Load test captures timeout errors correctly
**Source:** scripts/load_test.py
**User:** admin
**Starting state:** A scenario endpoint is timing out (e.g., DB overload)
**Goal:** Load test should record timeout errors rather than crashing
**Expected outcome:** error_count increments for the affected scenario; elapsed_ms still recorded; error field explains the cause
**Edge cases seen in code:** httpx.TimeoutException is caught; result.success=False; exit code 1 if error_rate > 5%
**CC confidence:** medium
**Status:** PENDING REVIEW
