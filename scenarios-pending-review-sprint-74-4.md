## SUGGESTED SCENARIO: Pool exhaustion surfaces diagnostic warning
**Source:** src/db.py get_connection() PoolError handler
**User:** admin
**Starting state:** Production app under high traffic; all DB_POOL_MAX connections are checked out
**Goal:** Diagnose why requests are failing with database errors
**Expected outcome:** Application log contains a WARNING entry with "Pool exhausted" and current pool stats (minconn, maxconn, in_use, available), allowing the operator to identify pool saturation without connecting to the database
**Edge cases seen in code:** PoolError is specifically caught before generic Exception, so pool exhaustion always logs at WARNING (not ERROR), distinct from other connection failures
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Pool health visible in health endpoint response
**Source:** src/db.py get_pool_stats() + get_pool_health()
**User:** admin
**Starting state:** App is running with an active PostgreSQL connection pool
**Goal:** Check current pool health from the /health endpoint to verify connections are available
**Expected outcome:** The health endpoint JSON response includes a pool stats section with a nested "health" object containing: healthy (bool), min, max, in_use, and available counts — all reflecting actual pool state
**Edge cases seen in code:** When pool is None (before first connection) or pool.closed=True, healthy=False with all counts at 0
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Custom pool parameters take effect via env vars
**Source:** src/db.py _get_pool() DB_POOL_MIN, DB_CONNECT_TIMEOUT
**User:** admin
**Starting state:** Production deployment with custom pool sizing requirements (e.g., DB_POOL_MIN=5, DB_CONNECT_TIMEOUT=30)
**Goal:** Configure minimum idle connections and connection timeout without code changes
**Expected outcome:** The connection pool is created with the env-configured minconn and connect_timeout values, visible in the startup log line "PostgreSQL connection pool created (minconn=5, maxconn=..., connect_timeout=30s)"
**Edge cases seen in code:** Default values (minconn=2, connect_timeout=10) apply when env vars are absent
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Statement timeout configurable per deployment context
**Source:** src/db.py get_connection() DB_STATEMENT_TIMEOUT
**User:** admin
**Starting state:** App deployed with DB_STATEMENT_TIMEOUT=60s (e.g., for analytics queries needing more time)
**Goal:** Allow longer-running queries without hitting the default 30s kill threshold
**Expected outcome:** New database connections have statement_timeout SET to 60s rather than the default 30s; cron workers (CRON_WORKER=true) continue to have no statement timeout regardless of the env var
**Edge cases seen in code:** CRON_WORKER=true bypasses the entire timeout setup, so DB_STATEMENT_TIMEOUT has no effect on cron connections
**CC confidence:** medium
**Status:** PENDING REVIEW
