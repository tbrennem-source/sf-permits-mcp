## SUGGESTED SCENARIO: Response time visible in response headers
**Source:** QS8-T1-D / web/app.py _add_response_time_header
**User:** admin
**Starting state:** App is running, any page is requested
**Goal:** Measure and observe server-side response time without needing server logs
**Expected outcome:** Every HTTP response (2xx, 4xx, 5xx) includes X-Response-Time header with value in milliseconds (e.g., "47.2ms"); value increases proportionally with DB-heavy pages vs. static pages
**Edge cases seen in code:** Header uses time.time() wall clock, not monotonic; value is always >= 0; present on 404 and health check responses
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Static content pages cached at CDN/browser level
**Source:** QS8-T1-D / web/app.py add_cache_headers
**User:** homeowner
**Starting state:** User visits /methodology, /about-data, or /demo for the first time
**Goal:** Content loads quickly on repeat visits without hitting the origin server
**Expected outcome:** Response includes Cache-Control: public, max-age=3600, stale-while-revalidate=86400; browser/CDN serves from cache for up to 1 hour; stale content served up to 24 hours while revalidating
**Edge cases seen in code:** Cache header only set on 200 responses (not errors); auth pages, API endpoints, and search routes do NOT receive this header; /pricing also included in the static page list
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Health endpoint reports pool connection state
**Source:** QS8-T1-D / web/app.py /health route enhancement
**User:** admin
**Starting state:** App connected to PostgreSQL with active connection pool
**Goal:** Diagnose connection pool health without needing direct DB access
**Expected outcome:** GET /health returns pool_stats with backend, minconn, maxconn, pool_size, used_count, and health sub-object; cache_stats shows page_cache row count and oldest entry age; both fields present even when pool is unused (DuckDB fallback returns no_pool status)
**Edge cases seen in code:** DuckDB backend returns {"status": "no_pool", "backend": "duckdb"} for pool_stats; cache_stats falls back to {"error": "unavailable"} on any DB exception; cache_stats.oldest_entry_age_minutes is null on DuckDB
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: DB pool max tunable for high-traffic deployments
**Source:** QS8-T1-D / src/db.py DB_POOL_MAX documentation
**User:** admin
**Starting state:** App running on Railway with default DB_POOL_MAX=20, experiencing connection pool exhaustion under load
**Goal:** Scale connection pool without code changes
**Expected outcome:** Setting DB_POOL_MAX env var to 40 (or any value) overrides the default; app restarts and creates pool with new max; pool exhaustion errors reduce; /health reports new maxconn value in pool_stats
**Edge cases seen in code:** Pool is a lazy singleton; changing env var requires restart; increasing beyond 50 requires PgBouncer (Railway pgvector DB limit)
**CC confidence:** low
**Status:** PENDING REVIEW
