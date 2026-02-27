## SUGGESTED SCENARIO: Production handles concurrent users without pool exhaustion
**Source:** QS4-B Task B-1 (pool monitoring + env override)
**User:** admin
**Starting state:** 50+ concurrent users hitting sfpermits.ai during peak hours
**Goal:** Verify that the connection pool handles concurrent load without exhaustion or errors
**Expected outcome:** All requests complete successfully; /health pool stats show used_count stays below maxconn; no connection timeout errors in logs
**Edge cases seen in code:** Pool at Railway limit (5 workers x 20 = 100 connections = Postgres max); DB_POOL_MAX env var override for capacity tuning
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Railway zero-downtime deploy uses readiness probe
**Source:** QS4-B Task B-2 (/health/ready endpoint)
**User:** admin
**Starting state:** New container starting during Railway deployment
**Goal:** Verify that /health/ready returns 503 until DB pool, tables, and migrations are all verified, then returns 200
**Expected outcome:** Railway routes traffic to new container only after /health/ready returns 200; old container continues serving until new one is ready
**Edge cases seen in code:** Missing tables return 503 with list of what's missing; 5-second statement_timeout prevents readiness probe from hanging
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Connection pool stats visible in health monitoring
**Source:** QS4-B Task B-3 (pool stats in /health)
**User:** admin
**Starting state:** Production system running with active connections
**Goal:** View connection pool utilization via /health endpoint for capacity planning
**Expected outcome:** /health response includes pool.maxconn, pool.used_count, pool.pool_size; values update in real-time as connections are checked out/returned
**Edge cases seen in code:** DuckDB backend returns status "no_pool" since it has no connection pool; pool internals accessed via _pool/_used attributes which may change between psycopg2 versions
**CC confidence:** medium
**Status:** PENDING REVIEW
