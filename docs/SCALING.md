# SF Permits Scaling Guide

This document describes the current production capacity of sfpermits.ai, how to identify
bottlenecks, and a step-by-step checklist for scaling to 5,000 concurrent users.

---

## Current Capacity

### Production Configuration (as of Sprint 84)

| Component | Current Setting | Source |
|-----------|----------------|--------|
| Gunicorn worker class | `gevent` (async) | `web/railway.toml` |
| Gunicorn worker count | 4 | `web/railway.toml` |
| Gunicorn worker connections | 100 per worker | `web/railway.toml` |
| Gunicorn timeout | 120s | `web/railway.toml` |
| DB pool min | 2 | `src/db.py` (`DB_POOL_MIN`) |
| DB pool max | 20 | `src/db.py` (`DB_POOL_MAX`) |
| Railway plan | Pro | Railway dashboard |
| Database | PostgreSQL + pgvector (pgvector-db service) | Railway internal |

### Estimated Capacity — Current Setup

With gevent + 4 workers + 100 connections each, the theoretical I/O concurrency ceiling is
**400 simultaneous requests**. In practice, the DB pool is the binding constraint:

- **DB pool max = 20** means at most 20 simultaneous DB-bound requests complete without waiting
- Non-DB requests (health check, static pages) can serve the full 400 concurrent slots
- At peak load, DB-bound requests queue behind the pool, increasing p99 latency significantly
- **Safe operating range without tuning: ~50–80 concurrent users** before DB pool exhaustion causes 500ms+ tail latency

### Observed Bottleneck Hierarchy

```
1. DB connection pool (DB_POOL_MAX=20)       <- primary bottleneck at >50 concurrent
2. Rate limiter (in-memory, per-worker)      <- doesn't share state across 4 workers
3. Anthropic API calls (plan analysis, RAG)  <- external latency, not scalable locally
4. Static assets (served by Flask/gunicorn)  <- no CDN; every asset costs a worker slot
5. Railway plan limits (CPU/RAM)             <- Pro plan; upgrade needed for 1K+ sustained
```

---

## Environment Variables for Scaling

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_MIN` | 2 | Minimum connections kept open in the PostgreSQL pool |
| `DB_POOL_MAX` | 20 | Maximum simultaneous PostgreSQL connections (primary bottleneck) |
| `DB_CONNECT_TIMEOUT` | 10 | Seconds to wait for a new DB connection before error |
| `WEB_CONCURRENCY` | 4 | Gunicorn worker count (set in `railway.toml` start command) |
| `REDIS_URL` | (none) | Redis URL for distributed rate limiting (not yet implemented) |
| `GUNICORN_WORKER_CONNECTIONS` | 100 | Max concurrent connections per gevent worker |
| `GUNICORN_TIMEOUT` | 120 | Request timeout in seconds |

Set these on the Railway service via:

```bash
railway service link sfpermits-ai
railway variable set DB_POOL_MAX=50
```

Or update `web/railway.toml` to pass them as environment variables in the start command.

---

## Bottleneck Deep-Dives

### 1. DB Connection Pool

**File:** `src/db.py` — `_get_pool()` function

```python
_minconn = int(os.environ.get("DB_POOL_MIN", "2"))
_maxconn = int(os.environ.get("DB_POOL_MAX", "20"))
_pool = psycopg2.pool.ThreadedConnectionPool(minconn=_minconn, maxconn=_maxconn, ...)
```

`psycopg2.pool.ThreadedConnectionPool` blocks when all connections are checked out. Under
gevent, blocking on the pool exhausts the event loop's green threads. **Increase `DB_POOL_MAX`
in lockstep with gunicorn worker count and connection capacity on pgvector-db.**

PostgreSQL default max_connections = 100. The pgvector-db Railway service has its own
`max_connections` setting. Never set `DB_POOL_MAX * WEB_CONCURRENCY` above the Postgres limit.

For >100 concurrent users, add **PgBouncer** in transaction pooling mode. PgBouncer lets
100+ application connections multiplex through ~20 real Postgres connections.

### 2. In-Memory Rate Limiter

**File:** `web/cost_tracking.py` and `web/app.py` (before_request hooks)

The current rate limiter uses Python dictionaries (in-process memory). With 4 gevent workers,
each worker has its own rate-limit state — a user can hit each worker independently and
effectively get 4x the rate limit. Fix: add Redis and switch to a shared counter.

**When this matters:** At >50 concurrent users, aggressive bots or scrapers can exceed
per-IP limits on some workers while being rate-limited on others.

### 3. Static Assets

Static files (`web/static/`) are served by gunicorn, which occupies worker connections during
each file transfer. A page load with 10 static assets can hold 10 green-thread slots for 50–200ms.

**Fix:** Put a CDN (Cloudflare, Railway's edge, or AWS CloudFront) in front of static assets.
Each Railway Pro service gets a public URL that can be fronted by Cloudflare with a 5-min CNAME.

### 4. Anthropic API Calls

Vision plan analysis and RAG calls hit the Anthropic API with latency of 2–30 seconds. These
are not horizontally scalable — the bottleneck is Anthropic's rate limits and inference time.

**Mitigation options:**
- Cache RAG embeddings query results (already done via pgvector materialized results)
- Queue plan analysis jobs and return async results (Sprint 84 implemented `plan_analysis_jobs`)
- Pre-fetch common queries during off-peak hours

---

## Scaling Checklist for 5,000 Concurrent Users

### Tier 1: 0–200 concurrent users (current + minor tuning)

- [x] Gunicorn gevent workers (done, `web/railway.toml`)
- [x] DB pool min/max configurable via env vars (done, `src/db.py`)
- [ ] Increase `DB_POOL_MAX` to 40–50 on Railway
- [ ] Verify pgvector-db `max_connections` >= 4 workers * DB_POOL_MAX
- [ ] Add `/health` to Railway healthcheck + monitoring alert

### Tier 2: 200–1,000 concurrent users (infrastructure upgrade)

- [ ] Upgrade Railway plan if CPU/RAM becomes saturated (monitor via Railway metrics)
- [ ] Add PgBouncer in transaction pooling mode between app and pgvector-db
  - PgBouncer Railway service template available in marketplace
  - Set `DATABASE_URL` to point to PgBouncer, not pgvector-db directly
- [ ] Move static assets to CDN (Cloudflare free tier works):
  - `STATIC_BASE_URL` env var in templates to prefix CDN domain
  - Set `Cache-Control: max-age=31536000, immutable` on hashed asset filenames
- [ ] Add Redis for shared rate limiting:
  - Deploy Redis via Railway (one command: `railway add --template redis`)
  - Set `REDIS_URL` env var
  - Implement `redis-py` counter in `web/cost_tracking.py`
- [ ] Increase Gunicorn workers: `WEB_CONCURRENCY = 2 * CPU_CORES + 1`
  - Railway Pro gives ~2 vCPUs → set `--workers 5`
  - Adjust `DB_POOL_MAX` accordingly so total pool doesn't exceed Postgres `max_connections`

### Tier 3: 1,000–5,000 concurrent users (architectural changes)

- [ ] Horizontal scaling: add a second Railway service instance behind a load balancer
  - Railway does not natively support multi-instance LB — use Cloudflare or AWS ALB
- [ ] Read replicas for SELECT-heavy queries (contacts, entities, relationships):
  - pgvector-db → add read replica
  - Separate `DATABASE_URL_READONLY` env var; route non-mutating queries there
- [ ] Async task queue for slow operations (already partially done via `plan_analysis_jobs`):
  - Move any endpoint with >500ms p95 to a background queue (Redis + RQ or Celery)
  - Return 202 Accepted + polling URL; client polls for result
- [ ] Application-level caching (Redis):
  - Cache: permit search results (5-min TTL), entity lookups (1-hour TTL)
  - Use `flask-caching` with Redis backend
- [ ] Database query audit:
  - Run `EXPLAIN ANALYZE` on the top 10 slow queries (pull from Railway logs)
  - Add missing indexes (especially on `permits.address`, `entities.name`)
- [ ] Enable pgvector HNSW index for faster embedding similarity search
  - `CREATE INDEX USING hnsw (embedding vector_cosine_ops)` on `knowledge_chunks`

---

## Load Testing

### Quick smoke test (5s, 5 users, health only)

```bash
source .venv/bin/activate
python -m scripts.load_test --url http://localhost:5001 --users 5 --duration 5 --scenario health
```

### Standard load test (50 users, 60s, all public endpoints)

```bash
source .venv/bin/activate
python -m scripts.load_test --url http://localhost:5001 --users 50 --duration 60
```

### Against staging

```bash
source .venv/bin/activate
python -m scripts.load_test \
  --url https://sfpermits-ai-staging-production.up.railway.app \
  --users 20 \
  --duration 30 \
  --scenario all \
  --output qa-results/load-test-staging.json
```

### Interpreting results

| Metric | Good | Warning | Critical |
|--------|------|---------|---------|
| p50 latency | < 200ms | 200–500ms | > 500ms |
| p95 latency | < 1,000ms | 1–3s | > 3s |
| p99 latency | < 3,000ms | 3–10s | > 10s |
| Error rate | < 1% | 1–5% | > 5% (exit code 1) |
| Throughput | depends on scenario | — | — |

The script exits with code `1` if any scenario's error rate exceeds 5%.

### Saving results for comparison

```bash
# Before infrastructure change
python -m scripts.load_test --url ... --output before.json

# After infrastructure change
python -m scripts.load_test --url ... --output after.json

# Compare p95 manually
python3 -c "
import json
b = json.load(open('before.json'))
a = json.load(open('after.json'))
for sc in b['results']:
    bp95 = b['results'][sc]['latency_ms']['p95']
    ap95 = a['results'][sc]['latency_ms']['p95']
    delta = ap95 - bp95
    print(f'{sc}: {bp95}ms -> {ap95}ms ({delta:+.0f}ms)')
"
```

---

## Monitoring

### Key metrics to watch in Railway dashboard

| Metric | Normal | Alert threshold |
|--------|--------|-----------------|
| CPU usage | < 40% | > 80% sustained |
| Memory | < 60% of limit | > 85% (OOM risk) |
| Response time (p95) | < 1s | > 3s |
| Error rate | < 0.1% | > 1% |
| DB connections active | < DB_POOL_MAX | == DB_POOL_MAX (pool exhaustion) |

### Health endpoint

`GET /health` returns a JSON object with DB connectivity, pool state, and key service status.
Use this as the primary uptime check:

```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```

### Logs

```bash
# Link to service first
railway service link sfpermits-ai

# Recent logs
railway logs -n 100

# Watch live
railway logs --follow
```

Look for:
- `psycopg2.pool.PoolError: connection pool exhausted` — increase `DB_POOL_MAX`
- `gunicorn.error WORKER TIMEOUT` — request took > 120s; optimize or queue async
- `Rate limit exceeded` — rate limiter is triggering; consider Redis for fairness

### Cron health check

The `cron_log` table tracks nightly job runs. Check for failures:

```sql
SELECT job_name, status, started_at, finished_at, error_message
FROM cron_log
ORDER BY started_at DESC
LIMIT 20;
```

Access via the `/admin` dashboard or Railway Postgres query console.

---

## Quick Reference: Deploy a Pool Size Change

```bash
# 1. Update the env var on Railway
railway service link sfpermits-ai
railway variable set DB_POOL_MAX=50

# 2. Redeploy (push triggers auto-deploy, or force restart)
# DO NOT use railway redeploy --yes — it restarts the old image
# Instead: touch a file, commit, and push to main to trigger a fresh deploy

# 3. Verify the new pool is active
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool
```

---

## Related Files

| File | Purpose |
|------|---------|
| `src/db.py` | DB pool configuration (`DB_POOL_MIN`, `DB_POOL_MAX`) |
| `web/railway.toml` | Gunicorn start command and worker count |
| `web/Procfile` | Local dev / fallback start command |
| `web/cost_tracking.py` | In-memory rate limiter implementation |
| `scripts/load_test.py` | Load test runner (this guide's companion) |
| `docs/ARCHITECTURE.md` | Full system architecture including DB schema |
| `docs/BACKUPS.md` | DB backup strategy |
| `DEPLOYMENT_MANIFEST.yaml` | All Railway service URLs and topology |
