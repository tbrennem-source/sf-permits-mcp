## Sprint 84-D: Load Test + Scaling Docs

- Enhanced `scripts/load_test.py` — added `--users` flag (alias for `--concurrency`), added `/methodology` endpoint to scenario set, added urllib stdlib fallback when httpx is unavailable, defaults changed to 50 concurrent users / 60s duration to match sprint spec
- Created `docs/SCALING.md` — 315-line practical scaling guide covering current capacity (gevent + 4 workers + DB_POOL_MAX=20), environment variables table, bottleneck hierarchy (DB pool -> rate limiter -> static assets -> Anthropic API), 3-tier scaling checklist for 0-200/200-1K/1K-5K concurrent users, load test usage examples with result interpretation table, and Railway monitoring/ops quick reference
