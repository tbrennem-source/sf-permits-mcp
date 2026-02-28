# QS9 Terminal 1: Tool Registration + Admin Health

You are the orchestrator for QS9-T1. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T1 start: $(git rev-parse --short HEAD)"
```

## File Ownership (3 agents — consolidation moved to T4)

| Agent | Files Owned |
|-------|-------------|
| A | `src/server.py` |
| B | `web/routes_admin.py`, `web/templates/fragments/admin_health.html` (NEW) |
| C | `scripts/prod_gate.py` |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Register 4 Intelligence Tools

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Register 4 intelligence tools in src/server.py

### File Ownership
- src/server.py (ONLY this file)

### Read First
- src/server.py (understand how existing 30 tools are registered — find the pattern)
- src/tools/predict_next_stations.py (function signature + docstring)
- src/tools/stuck_permit.py (function signature + docstring)
- src/tools/what_if_simulator.py (function signature + docstring)
- src/tools/cost_of_delay.py (function signature + docstring)

### Build
Register these 4 tools following the EXACT pattern used by existing tools:
1. predict_next_stations (from src.tools.predict_next_stations)
2. diagnose_stuck_permit (from src.tools.stuck_permit)
3. simulate_what_if (from src.tools.what_if_simulator)
4. calculate_delay_cost (from src.tools.cost_of_delay)

Total after: 34 tools.

### Test
```bash
source .venv/bin/activate
python -c "from src.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Should show 34
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e -k "server or tool_count" 2>&1 | tail -5
```

### Output Files
- scenarios-pending-review-qs9-t1-a.md
- CHANGELOG-qs9-t1-a.md

### Commit
feat: register 4 intelligence tools in MCP server (30→34 tools) (QS9-T1-A)
""")
```

---

### Agent B: Admin Health Panel

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add system health panel to admin dashboard

### File Ownership
- web/routes_admin.py
- web/templates/fragments/admin_health.html (NEW)

### Read First
- web/routes_admin.py (existing admin routes)
- src/db.py (get_pool_stats, get_pool_health)
- src/soda_client.py (find CircuitBreaker class or state)
- web/helpers.py (find get_cached_or_compute — for cache stats query)
- docs/DESIGN_TOKENS.md (for styling)

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

### Build

Task B-1: Add /admin/health endpoint to web/routes_admin.py:
- Returns HTML fragment with 3 sections: Pool, Circuit Breaker, Cache
- Requires admin auth (follow existing admin route pattern)

Task B-2: Create fragments/admin_health.html:
- Pool card: connections used / available / max. Bar visualization.
- Circuit breaker card: state dot (green=closed, red=open, amber=half-open) + failure count
- Cache card: page_cache row count + oldest entry age
- Use glass-card containers, --mono for numbers
- HTMX hx-get="/admin/health" hx-trigger="every 30s" for auto-refresh

Task B-3: Include the fragment on the main /admin page.

### Test
Write tests/test_sprint_82_d.py:
- test_admin_health_requires_auth
- test_admin_health_shows_pool_stats
- test_admin_health_shows_cache_count

### Output Files
- scenarios-pending-review-qs9-t1-b.md
- CHANGELOG-qs9-t1-b.md

### Commit
feat: admin health panel — pool + circuit breaker + cache stats (QS9-T1-B)
""")
```

---

### Agent C: Fix Prod Gate Ratchet Logic

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Fix prod gate hotfix ratchet to track specific issues

### File Ownership
- scripts/prod_gate.py (ONLY this file)

### Read First
- scripts/prod_gate.py (full file — find the ratchet logic, HOTFIX_REQUIRED.md references)
- qa-results/HOTFIX_REQUIRED.md (if it exists — see what was tracked before)

### Problem
The ratchet triggers HOLD on consecutive score-3 sprints even when the specific issues changed. QS8 got HOLD because QS7 was also score-3, but the issues were completely different.

### Build
Fix the ratchet to compare specific failing checks, not overall score:
1. When score <= 3: write failing check names to qa-results/HOTFIX_REQUIRED.md
2. On next run: read previous HOTFIX_REQUIRED.md, compare check names
3. Only trigger ratchet if the SAME checks are still failing
4. If different checks fail: normal score behavior (3 = promote + hotfix), reset ratchet
5. If previous hotfix file doesn't exist: no ratchet (first occurrence)

### Test
Write tests/test_prod_gate_ratchet.py:
- test_ratchet_triggers_on_same_checks
- test_ratchet_resets_on_different_checks
- test_no_ratchet_on_first_occurrence
- test_ratchet_clears_after_all_green

### Output Files
- scenarios-pending-review-qs9-t1-c.md
- CHANGELOG-qs9-t1-c.md

### Commit
fix: prod gate ratchet tracks specific failing checks, not overall score (QS9-T1-C)
""")
```

---

## Post-Agent: Merge + Push

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit
cat scenarios-pending-review-qs9-t1-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs9-t1-*.md >> CHANGELOG.md 2>/dev/null
git push origin main
```

## Report

```
T1 (Registration + Admin) COMPLETE
  A: Tool registration:      [PASS/FAIL] (30→34 tools)
  B: Admin health panel:     [PASS/FAIL]
  C: Prod gate ratchet fix:  [PASS/FAIL]
  Pushed: [commit hash]
```
