## SUGGESTED SCENARIO: App logs warning when DB pool nears exhaustion
**Source:** src/db.py — _check_pool_exhaustion_warning() added in Sprint 84-A
**User:** admin
**Starting state:** App is running under high load; DB_POOL_MAX=50; 40+ connections are in use simultaneously
**Goal:** Detect that the connection pool is running low before requests start failing
**Expected outcome:** A WARNING-level log line appears containing the current used/max connection counts and a suggestion to increase DB_POOL_MAX or enable PgBouncer. No user-facing error occurs — warning is operational signal only.
**Edge cases seen in code:** Warning threshold is configurable via DB_POOL_WARN_THRESHOLD (default 0.8). If pool._used attribute is missing (psycopg2 internals change), the check fails silently with a DEBUG log rather than raising.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin increases pool size via env var without code change
**Source:** src/db.py — DB_POOL_MAX env var + docs/ONBOARDING.md pool config section (Sprint 84-A)
**User:** admin
**Starting state:** App is deployed on Railway; pool exhaustion warnings are appearing in logs because traffic has grown beyond the default DB_POOL_MAX=50
**Goal:** Increase the connection pool ceiling to handle more concurrent users without a code deploy
**Expected outcome:** Admin sets DB_POOL_MAX=80 (or higher) in Railway environment variables. After Railway auto-restarts the service, the pool is initialized with the new max and exhaustion warnings stop. The /health endpoint reflects the updated pool configuration (maxconn=80).
**Edge cases seen in code:** The pool is a lazy singleton — changes only take effect on process restart. DB_POOL_MIN must remain <= DB_POOL_MAX (psycopg2 enforces this at pool creation time).
**CC confidence:** high
**Status:** PENDING REVIEW
