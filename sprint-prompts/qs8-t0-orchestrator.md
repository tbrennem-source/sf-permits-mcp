# QS8 Terminal 0: Orchestrator

> This is Tim's terminal. T0 has the full context, runs pre-flight, launches T1-T4,
> monitors progress, merges in order, runs the prod gate, and promotes.
>
> **Do NOT paste this into an agent.** Tim reads this and executes it manually,
> pasting T1-T4 prompts into separate CC terminals.

## Context

**Sprint goal:** Performance, intelligence tools, design migration, and beta experience — the four pillars needed before public beta launch.

**What ships:**
- 9 core templates migrated to Obsidian design tokens (193 violations fixed)
- Property report N+1 fix (44-permit pages drop from ~11s to ~2-3s)
- `page_cache` table + `get_cached_or_compute()` + cron pre-compute
- SODA circuit breaker + Cache-Control headers + response timing
- 4 NEW intelligence tools: station predictor, stuck permit playbook, what-if simulator, cost of delay
- Multi-step onboarding wizard + PREMIUM tier + 5 feature flags
- Search NLP parser (natural language → structured filters)
- Trade permit ingest (electrical/plumbing/boiler — 450K records)
- 16+ E2E tests for new features
- ~200 new tests total

**Chief tasks resolved:** #355, #319, #349 (A+B), #164, #218, #217, #287, #129, #174, #166, #169, #330, #135, #139, #271, #130

---

## Pre-Flight (T0 runs this BEFORE launching any terminal)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Verify clean state
git status
git log --oneline -5

# Verify tests pass
source .venv/bin/activate
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -3

# Verify prod is healthy
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Record sprint start commit for post-merge diff audit
echo "Sprint start: $(git rev-parse --short HEAD)"

# Baseline lint scores for core templates
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/report.html web/templates/brief.html web/templates/portfolio.html --quiet
```

**Stop conditions:** If tests fail (beyond known pre-existing failures), if prod is unhealthy, or if HEAD has unexpected changes — investigate before launching.

---

## Launch Sequence

Open 4 CC terminal windows. In each, paste the command to read the terminal's sprint prompt.

| Terminal | Command to paste | What it does |
|---|---|---|
| **T1** | `Read sprint-prompts/qs8-t1-design-migration.md and execute it` | Design token migration: 9 templates to Obsidian |
| **T2** | `Read sprint-prompts/qs8-t2-performance.md and execute it` | Performance: N+1 fix, page_cache, circuit breaker, headers |
| **T3** | `Read sprint-prompts/qs8-t3-intelligence.md and execute it` | 4 new intelligence tools (all new files, zero conflicts) |
| **T4** | `Read sprint-prompts/qs8-t4-beta-data.md and execute it` | Beta onboarding, search NLP, trade permits, E2E tests |

**Launch all 4 simultaneously.** Each terminal spawns 4 agents via Task tool (16 agents total).

---

## Monitoring

While terminals run, T0 watches for:

1. **Agent failures** — if a terminal reports an agent failed, note it. Do not intervene unless all 4 agents in a terminal failed.
2. **File ownership violations** — if any terminal's agent accidentally touches a file owned by another terminal, that's a merge conflict. The terminal that owns the file takes precedence.
3. **Early finishers** — T3 will likely finish first (all new files, zero deps). Don't merge yet — wait for all terminals to complete.

**Expected timeline:**
```
T+0 min:   All 4 terminals launched
T+15 min:  T3 finishes (all new files, fastest)
T+20 min:  T1 finishes (template migration)
T+20 min:  T4 finishes (parallel with T1)
T+25 min:  T2 finishes (most complex — cache infra + N+1 fix)
T+25-35:   Merge ceremony
T+35 min:  Prod gate → promote
```

---

## Merge Ceremony (T0 runs this)

**Merge order matters:** T2 (infrastructure) → T1 (templates) → T3 (new tools) → T4 (beta + tests)

T3 can go anywhere (all new files, zero conflicts). T1 depends on design-system.css which it owns. T4 has E2E tests that test T1/T2 features.

### Step 1: Each terminal pushes to main

Each terminal completes its own internal merge (4 agent branches → main, push). T0 orchestrates the order.

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -20
# Verify you see commits from all 4 terminals
```

If a terminal hasn't pushed yet, wait. Do not proceed with partial merges.

### Step 2: File ownership audit

```bash
git diff --stat $(git log --oneline -20 | tail -1 | cut -d' ' -f1)..HEAD
```

**File ownership verification:**
- T1 files: `web/templates/landing.html`, `web/templates/search_results_public.html`, `web/templates/results.html`, `web/templates/report.html`, `web/templates/brief.html`, `web/templates/velocity_dashboard.html`, `web/templates/portfolio.html`, `web/templates/fragments/nav.html`, `web/templates/demo.html`, `web/static/design-system.css`
- T2 files: `web/report.py`, `web/helpers.py`, `src/db.py`, `scripts/release.py`, `web/brief.py`, `web/routes_cron.py`, `src/soda_client.py`, `web/routes_misc.py`
- T3 files: `src/tools/station_predictor.py`, `src/tools/stuck_permit.py`, `src/tools/what_if_simulator.py`, `src/tools/cost_of_delay.py`, `tests/test_station_predictor.py`, `tests/test_stuck_permit.py`, `tests/test_what_if_simulator.py`, `tests/test_cost_of_delay.py`
- T4 files: `web/routes_auth.py`, `web/feature_gate.py`, `web/templates/welcome.html`, `web/templates/onboarding_*.html`, `web/routes_search.py`, `web/routes_public.py`, `src/ingest.py`, `tests/e2e/test_onboarding_scenarios.py`, `tests/e2e/test_performance_scenarios.py`

If an unexpected file appears, investigate before continuing.

### Step 3: Full test suite

```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e
```

**If tests fail:** Check which test file. Cross-terminal interface mismatches (e.g., T4's E2E tests vs T2's cache implementation) are expected — fix the implementation to match the spec, or vice versa. These are quick fixes.

### Step 4: Design lint on migrated templates

```bash
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/report.html web/templates/brief.html web/templates/portfolio.html web/templates/demo.html --quiet
# Target: 5/5 on all migrated templates
```

### Step 5: Prod gate

```bash
python scripts/prod_gate.py --quiet
```

If HOLD: read `qa-results/prod-gate-results.md` for details. Fix blocking issues before promoting.

### Step 6: Promote to prod

```bash
git checkout prod && git merge main && git push origin prod && git checkout main
```

### Step 7: Post-promotion verification

```bash
# Wait 2-3 minutes for Railway deploy
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5
```

---

## Report Template

```
QS8 COMPLETE — Sprints 78-81
============================================
Started: [time]  Finished: [time]  Duration: [N] minutes

Terminal 1 (Design Migration — Sprint 78):
  78-1 landing + search:          [PASS/FAIL] lint: [N/5]
  78-2 results + report:          [PASS/FAIL] lint: [N/5]
  78-3 brief + velocity:          [PASS/FAIL] lint: [N/5]
  78-4 portfolio + nav + demo:    [PASS/FAIL] lint: [N/5]

Terminal 2 (Performance — Sprint 79):
  79-1 report N+1 fix:            [PASS/FAIL]
  79-2 page_cache infrastructure: [PASS/FAIL]
  79-3 brief cache + cron:        [PASS/FAIL]
  79-4 circuit breaker + headers: [PASS/FAIL]

Terminal 3 (Intelligence — Sprint 80):
  80-1 station predictor:         [PASS/FAIL]
  80-2 stuck permit playbook:     [PASS/FAIL]
  80-3 what-if simulator:         [PASS/FAIL]
  80-4 cost of delay:             [PASS/FAIL]

Terminal 4 (Beta + Data — Sprint 81):
  81-1 onboarding + feature gate: [PASS/FAIL]
  81-2 search NLP:                [PASS/FAIL]
  81-3 trade permits ingest:      [PASS/FAIL]
  81-4 E2E tests:                 [PASS/FAIL]

Post-merge:
  Full test suite: [N passed / M failed]
  Design lint (core 7): [N/5]
  Prod gate: [PROMOTE/HOLD] ([N/5])
  Promoted to prod: [commit hash]
  Prod health: [ok/error]

Hotfixes needed: [list or "none"]
```

---

## Failure Recovery

| Scenario | Action |
|---|---|
| One agent in a terminal fails | Terminal orchestrator retries or skips. Other agents unaffected. |
| Entire terminal fails | Note which terminal. Merge the other 3. Run the failed terminal's work as a follow-up sprint. |
| Merge conflicts | Should not happen with clean file ownership. If it does: the terminal that OWNS the file wins. |
| Tests fail after merge | Check which test. If cross-terminal interface mismatch, fix implementation to match spec. |
| Prod gate returns HOLD | Read the report. Score 2 = fix before promoting. Score 3 = promote + mandatory hotfix. |
| Prod deploy fails | Check Railway logs. Most common: missing env var or startup migration error. |

---

## Post-Sprint

1. **Update Chief:** Post the report via `chief_add_note`, update STATUS.md
2. **Clean up worktree branches:** `git branch -d` all agent branches
3. **Next:** Scenario drain (87 pending), visual QA on staging, remaining template migration (~20 templates)
