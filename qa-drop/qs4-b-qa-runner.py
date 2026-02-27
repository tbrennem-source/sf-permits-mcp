"""QS4-B QA runner — executes checks and writes results."""
import json
import os
import sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets

results = []

def check(num, desc, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"{num}. {desc} — **{status}**"
    if detail:
        line += f" ({detail})"
    results.append(line)
    print(f"  {'✓' if passed else '✗'} {desc} — {status}")


app.config["TESTING"] = True
_rate_buckets.clear()

with app.test_client() as client:
    # 1. /health includes pool stats
    rv = client.get("/health")
    data = json.loads(rv.data)
    has_pool = "pool" in data and "backend" in data.get("pool", {})
    check(1, "GET /health includes pool stats", has_pool,
          f"pool keys: {list(data.get('pool', {}).keys())}")

    # 2. /health/ready returns JSON
    rv = client.get("/health/ready")
    data = json.loads(rv.data)
    has_ready = "ready" in data and "checks" in data
    check(2, "GET /health/ready returns JSON with ready+checks keys", has_ready)

    # 3. /health/ready checks structure
    checks = data.get("checks", {})
    has_all = all(k in checks for k in ["db_pool", "tables", "migrations"])
    check(3, "GET /health/ready checks include db_pool, tables, migrations", has_all,
          f"keys: {list(checks.keys())}")

    # 4. /health/schema regression
    rv = client.get("/health/schema")
    schema_ok = rv.status_code in (200, 503)
    schema_data = json.loads(rv.data)
    check(4, "GET /health/schema still works (CC0 regression)", schema_ok and "tables" in schema_data)

    # 5. DB_POOL_MAX env var recognized in code
    import src.db as db_mod
    import inspect
    source = inspect.getsource(db_mod._get_pool)
    has_env = "DB_POOL_MAX" in source
    check(5, "DB_POOL_MAX env var is recognized in code", has_env)

    # 6. Docker workflow exists and valid YAML
    wf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           ".github", "workflows", "docker-build.yml")
    wf_exists = os.path.exists(wf_path)
    wf_valid = False
    if wf_exists:
        with open(wf_path) as f:
            try:
                wf_data = yaml.safe_load(f)
                wf_valid = "jobs" in wf_data and "ghcr.io" in open(wf_path).read()
            except Exception:
                pass
    check(6, ".github/workflows/docker-build.yml exists and valid YAML",
          wf_exists and wf_valid)

    # 7. /demo renders 200
    rv = client.get("/demo")
    check(7, "/demo page renders 200", rv.status_code == 200)

    # 8. /demo has CTA with invite code
    html = rv.data.decode()
    has_cta = "friends-gridcare" in html and "/auth/login" in html
    check(8, "/demo has CTA with invite code friends-gridcare", has_cta)

    # 9. /demo mentions MCP and entity resolution
    has_mcp = "MCP" in html
    has_entity = "entity" in html.lower()
    check(9, "/demo mentions MCP tools and entity resolution",
          has_mcp and has_entity)


# Write results
results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qa-results")
os.makedirs(results_dir, exist_ok=True)

output = "# QS4-B Performance + Production Hardening — QA Results\n\n"
output += f"**Date:** 2026-02-26\n"
output += f"**Agent:** QS4-B (Performance)\n\n"
output += "## Results\n\n"
for r in results:
    output += r + "\n"

pass_count = sum(1 for r in results if "**PASS**" in r)
fail_count = sum(1 for r in results if "**FAIL**" in r)
output += f"\n## Summary\n\n"
output += f"**{pass_count} PASS / {fail_count} FAIL** out of {len(results)} checks\n"

results_path = os.path.join(results_dir, "qs4-b-results.md")
with open(results_path, "w") as f:
    f.write(output)
print(f"\nResults written to {results_path}")
print(f"Summary: {pass_count} PASS / {fail_count} FAIL")
