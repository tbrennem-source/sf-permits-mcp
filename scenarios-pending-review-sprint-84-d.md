## SUGGESTED SCENARIO: Load test identifies DB pool bottleneck before it hits production users
**Source:** scripts/load_test.py, src/db.py (DB_POOL_MAX default=20)
**User:** admin
**Starting state:** App is running on staging with default DB_POOL_MAX=20 and 4 gunicorn workers. A sprint added a new search feature with a heavy DB query.
**Goal:** Verify the app handles 50 concurrent users without DB pool exhaustion before promoting to production.
**Expected outcome:** Load test reports p95 latency and error rate per endpoint. If DB pool is exhausted, the test exits with code 1 and shows error_rate > 5% on DB-bound endpoints. Admin increases DB_POOL_MAX and re-runs — error rate drops to < 1%.
**Edge cases seen in code:** psycopg2 ThreadedConnectionPool blocks (does not raise immediately) when pool is exhausted; gevent workers wait silently, causing p99 spike without an explicit error until the request timeout fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: New developer finds scaling guide and configures correct pool size
**Source:** docs/SCALING.md
**User:** admin
**Starting state:** A new developer is onboarding. The app is running locally against a local Postgres instance. They want to run a load test and tune the DB pool for their expected traffic.
**Goal:** Find documentation explaining what DB_POOL_MAX does, what value to set, and how to verify the change worked.
**Expected outcome:** Developer reads SCALING.md, identifies DB_POOL_MAX as the primary bottleneck, sets it to 50 via railway variable set, deploys, and re-runs the load test. p95 latency on search endpoint improves. /health endpoint confirms pool configuration change is active.
**Edge cases seen in code:** DB_POOL_MAX * worker_count must not exceed Postgres max_connections (default 100). SCALING.md includes this warning explicitly.
**CC confidence:** high
**Status:** PENDING REVIEW
