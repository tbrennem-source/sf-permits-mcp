# QS9 Terminal 1: Tool Registration + Admin Health

You are the orchestrator for QS9-T1. Spawn 3 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T1 start: $(git rev-parse --short HEAD)"
```

## File Ownership (3 agents)

| Agent | Files Owned |
|-------|-------------|
| A | `src/server.py` |
| B | `web/routes_admin.py`, `web/templates/fragments/admin_health.html` (NEW) |
| C | `scripts/prod_gate.py` |

## Standard Agent Preamble (include verbatim in every agent prompt)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-pending-review-qs9-t1-{agent}.md (write 2-5 scenarios per feature)
  * CHANGELOG-qs9-t1-{agent}.md
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -10

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. SCENARIOS — write 2-5 behavioral scenarios to your per-agent scenarios file
5. QA — for CLI-only work: pytest is sufficient. For UI/template work: describe what needs visual verification in your CHECKCHAT.
6. DESIGN TOKEN COMPLIANCE — if you created/modified any template: run `python scripts/design_lint.py --changed --quiet`
7. CHECKCHAT — write a summary with: what shipped, tests added, scenarios written, any BLOCKED items, Visual QA Checklist (list items needing human spot-check)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- CRON_WORKER env var needed for cron tests
```

## Launch All 3 Agents (FOREGROUND, parallel)

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
source .venv/bin/activate
python -c "from src.server import mcp; print(f'Tools registered')"
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e -k "server" 2>&1 | tail -5

### Scenarios
Write 2-3 scenarios to scenarios-pending-review-qs9-t1-a.md:
- Scenario: MCP client discovers all 34 tools
- Scenario: Intelligence tool returns formatted markdown via MCP

### CHECKCHAT
Write a summary including: tools registered, test results, scenarios written, Visual QA Checklist (N/A — no UI).

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
- web/helpers.py (get_cached_or_compute — for cache stats)
- docs/DESIGN_TOKENS.md (for template styling — read FULL file)

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
Write tests/test_admin_health.py:
- test_admin_health_requires_auth
- test_admin_health_shows_pool_stats
- test_admin_health_shows_cache_count

### Design Token Compliance
Run after build: python scripts/design_lint.py --files web/templates/fragments/admin_health.html --quiet
Target: 5/5. Fix any violations before committing.

### Scenarios
Write 3-4 scenarios to scenarios-pending-review-qs9-t1-b.md:
- Scenario: Admin sees DB pool utilization in real-time
- Scenario: Circuit breaker state change visible on admin dashboard
- Scenario: Admin notices stale cache and triggers invalidation

### CHECKCHAT
Write summary: endpoint created, template created, lint score, tests added, scenarios written.
Visual QA Checklist:
- [ ] /admin page shows health panel with 3 cards
- [ ] Pool card shows bar visualization
- [ ] Circuit breaker dot is correct color
- [ ] HTMX auto-refresh works (wait 30s, verify update)

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
- scripts/prod_gate.py (full file — find ratchet logic, HOTFIX_REQUIRED.md references)
- qa-results/HOTFIX_REQUIRED.md (if exists — see what was tracked)

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

### Scenarios
Write 2 scenarios to scenarios-pending-review-qs9-t1-c.md:
- Scenario: Prod gate promotes when new issues differ from previous sprint
- Scenario: Prod gate holds when same issue persists across sprints

### CHECKCHAT
Write summary: ratchet logic fixed, tests added, scenarios written. Visual QA Checklist: N/A — CLI tool.

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

# Merge all 3
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit

# Design lint on new template
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/fragments/admin_health.html --quiet

# Concatenate per-agent output files
cat scenarios-pending-review-qs9-t1-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs9-t1-*.md >> CHANGELOG.md 2>/dev/null

# Push
git push origin main
```

## Report

```
T1 (Registration + Admin) COMPLETE
  A: Tool registration:      [PASS/FAIL] (30→34 tools)
  B: Admin health panel:     [PASS/FAIL] lint: [N/5]
  C: Prod gate ratchet fix:  [PASS/FAIL]
  Scenarios: [N] across 3 files
  Visual QA Checklist:
    - [ ] /admin health panel renders
    - [ ] Pool/CB/Cache cards display data
  Pushed: [commit hash]
```
