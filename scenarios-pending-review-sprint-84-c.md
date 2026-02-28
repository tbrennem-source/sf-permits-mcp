## SUGGESTED SCENARIO: Rate limit enforced consistently across multiple Gunicorn workers
**Source:** web/helpers.py — Redis-backed rate limiter (Sprint 84-C)
**User:** expediter
**Starting state:** App is running with multiple Gunicorn workers and Redis is available via REDIS_URL. A single IP has made N requests in the current window.
**Goal:** Enforce per-IP rate limits that are shared across all worker processes so that a user cannot bypass the limit by hitting different workers.
**Expected outcome:** Once the IP hits the rate limit, all subsequent requests within the window are rejected regardless of which worker process handles them. The counter is stored in Redis and is visible to every worker.
**Edge cases seen in code:** Worker A may have incremented the Redis counter while worker B serves the rejection — the shared INCR + EXPIRE pipeline ensures consistency.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Rate limiter degrades gracefully when Redis is down
**Source:** web/helpers.py — _get_redis_client fallback logic (Sprint 84-C)
**User:** expediter
**Starting state:** App is running and REDIS_URL is set, but the Redis service is unreachable (e.g., network partition or Redis restart).
**Goal:** Continue serving requests without crashing or hanging; enforce rate limits with best-effort in-memory counting.
**Expected outcome:** When the Redis pipeline raises a connection error, the rate limiter silently falls back to the in-process dictionary. Requests are counted per-worker rather than globally, but the app remains available and does not return 500 errors.
**Edge cases seen in code:** The socket_connect_timeout=1 ensures the connect attempt fails fast rather than blocking for the default TCP timeout.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Rate limit resets after time window expires
**Source:** web/helpers.py — Redis INCR + EXPIRE pattern (Sprint 84-C)
**User:** homeowner
**Starting state:** A user has exceeded the rate limit for a given endpoint (e.g., /analyze) and is currently blocked.
**Goal:** After the rate limit window (60 seconds) expires, the user should be able to make new requests without contacting support or waiting for a deploy.
**Expected outcome:** Once the Redis TTL expires, the INCR counter resets to 0 and the next request is allowed. In the in-memory fallback, old timestamps are pruned from the bucket and fresh requests are permitted after the window elapses.
**Edge cases seen in code:** EXPIRE is set on every INCR call, so the window slides relative to the first request in the current bucket, not the last.
**CC confidence:** high
**Status:** PENDING REVIEW
