# QS4-B Performance + Production Hardening — QA Script

## Setup
```bash
source .venv/bin/activate
cd /Users/timbrenneman/AIprojects/sf-permits-mcp/.claude/worktrees/qs4-b
```

## Checks

1. [NEW] GET /health includes pool stats (maxconn, backend) — PASS/FAIL
2. [NEW] GET /health/ready returns JSON with ready+checks keys — PASS/FAIL
3. [NEW] GET /health/ready checks include db_pool, tables, migrations — PASS/FAIL
4. [NEW] GET /health/schema still works (CC0 regression) — PASS/FAIL
5. [NEW] DB_POOL_MAX env var is recognized in code — PASS/FAIL
6. [NEW] .github/workflows/docker-build.yml exists and is valid YAML — PASS/FAIL
7. [NEW] /demo page renders 200 — PASS/FAIL
8. [NEW] /demo has CTA linking to signup with invite code friends-gridcare — PASS/FAIL
9. [NEW] /demo mentions MCP tools and entity resolution — PASS/FAIL
