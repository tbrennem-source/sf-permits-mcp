# CHANGELOG — QS4-B: Performance + Production Hardening

## 2026-02-26 — QS4-B Session

### Added
- **Connection pool monitoring** (`src/db.py`): `get_pool_stats()` function returns pool utilization metrics (maxconn, minconn, used_count, pool_size, closed state)
- **DB_POOL_MAX env var** (`src/db.py`): Connection pool maxconn now configurable via environment variable (default remains 20 — Railway limit: 100 / 5 workers = 20)
- **`/health/ready` endpoint** (`web/app.py`): Readiness probe for Railway zero-downtime deploys — checks DB pool, expected tables, and migration markers. Returns 200 when fully operational, 503 when not ready. Includes 5s statement_timeout to prevent hanging.
- **Pool stats in `/health`** (`web/app.py`): `/health` response now includes `pool` key with connection pool utilization stats
- **Docker CI workflow** (`.github/workflows/docker-build.yml`): GitHub Actions workflow builds and pushes Docker images to GHCR on every push to main. Includes layer caching via GHA cache.
- **Demo page polish** (`web/templates/demo.html`): Architecture showcase section (30 MCP tools, 1M entities, 576K relationships, 3.9M addenda), "Try it yourself" CTA linking to signup with `friends-gridcare` invite code

### Tests
- 24 new tests in `tests/test_qs4_b_perf.py` covering pool stats, /health/ready, Docker CI, /health/schema regression, and /demo page content

### Manual Steps Required
- Configure Railway to pull pre-built Docker images from GHCR instead of building from source
- Set `/health/ready` as Railway health check URL for zero-downtime deploys
