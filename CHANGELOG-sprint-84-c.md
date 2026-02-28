## Sprint 84-C: Redis Rate Limiter

### Changes

- **web/helpers.py** — Added Redis-backed rate limiter with in-memory fallback
  - New `_get_redis_client()` — connects to Redis via REDIS_URL (cached per-process); returns None when unavailable
  - New `check_rate_limit(key, limit, window_seconds)` — public function using Redis INCR + EXPIRE for cross-worker shared counting; falls back to in-memory sliding window when Redis is unavailable or raises
  - Refactored `_is_rate_limited(ip, max_requests)` — now delegates to `check_rate_limit()`; backward-compatible (same signature and return semantics)
  - All existing callers (`app.py`, `routes_public.py`, `routes_api.py`, `routes_property.py`) continue to work without modification

- **pyproject.toml** — Added dependencies
  - `redis>=5.0.0` to `[project.dependencies]` (production)
  - `fakeredis>=2.20.0` to `[project.optional-dependencies.dev]` (test only)

- **tests/test_redis_rate_limiter.py** — New test file (10 tests, all passing)
  - `TestRedisRateLimiter` — counts, blocks over threshold, resets after window, TTL is set
  - `TestInMemoryFallback` — falls back when no Redis, falls back when Redis down, counts correctly
  - `TestIsRateLimited` — backward-compat: returns False when under limit, True when over, uses Redis when available

### Notes

- REDIS_URL is Railway-internal only; not reachable from local dev. Local runs always use the in-memory path.
- Redis client is cached after the first successful ping so connection overhead is paid once per process, not per request.
- socket_connect_timeout=1 ensures fast failure when Redis is unreachable, avoiding request hangs.
