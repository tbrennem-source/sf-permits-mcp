# QS8 Terminal 0: Orchestrator

> Tim's terminal. T0 runs pre-flight, launches T1-T3, monitors, merges, prod gates, promotes.
> **Do NOT paste this into an agent.** Tim reads this and pastes T1-T3 prompts into 3 CC terminals.

## Context

**Sprint goal:** Performance + intelligence + beta experience — the three pillars for public beta launch.

**What ships:**
- Report N+1 fix (11s → ~2-3s), SODA circuit breaker, Cache-Control headers, response timing
- Pipeline stats in brief, signals/velocity cron endpoints
- 4 NEW intelligence tools: station predictor, stuck permit, what-if simulator, cost of delay
- Multi-step onboarding wizard, PREMIUM tier, 5 feature flags
- Search NLP parser, demo seed script, trade permit ingest functions
- ~150 new tests + 16 E2E tests

**Already shipped (QS7 + Sprint 78):** page_cache table, get_cached_or_compute, /cron/compute-caches, brief cache-read, obsidian.css, 9 templates at 5/5 lint, DuckDB test isolation.

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git status
git log --oneline -5

# Tests (T0 only — terminals skip this)
source .venv/bin/activate
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -3

# Prod health
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Record sprint start
echo "QS8 start: $(git rev-parse --short HEAD)"
```

**Stop conditions:** If tests fail (beyond known pre-existing), prod unhealthy, or unexpected changes — investigate.

---

## Launch Sequence

Open 3 CC terminals. Paste:

| Terminal | Paste | Theme | ~ETA |
|----------|-------|-------|------|
| **T1** | `Read sprint-prompts/qs8-t1-performance.md and execute it` | N+1 fix, cron, circuit breaker, headers | ~20 min |
| **T2** | `Read sprint-prompts/qs8-t2-intelligence.md and execute it` | 4 new tools (all new files) | ~15 min |
| **T3** | `Read sprint-prompts/qs8-t3-beta-data.md and execute it` | Onboarding, search NLP, ingest, E2E | ~22 min |

Launch all 3 simultaneously.

---

## Monitoring

1. **Agent failures** — note them. Don't intervene unless all 4 agents in a terminal failed.
2. **File ownership violations** — file owner wins.
3. **T2 finishes first** (all new files). Let it push. Don't merge yet.
4. **If a Task launch errors** — take over immediately. Don't wait for an orphaned agent.

**Expected timeline:**
```
T+0:      All 3 terminals launched
T+15:     T2 finishes (all new files, fastest)
T+20:     T1 finishes (performance)
T+22:     T3 finishes
T+25-30:  Merge ceremony
T+30-35:  Full test suite
T+35:     Prod gate → promote
```

---

## Merge Ceremony

### Step 1: Verify all terminals pushed

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -20
# Verify commits from all 3 terminals
```

### Step 2: File ownership audit

```bash
git diff --stat $(git log --oneline -20 | tail -1 | cut -d' ' -f1)..HEAD
```

**T1 files:** web/report.py, web/brief.py, web/routes_cron.py, src/soda_client.py, web/routes_misc.py, web/app.py
**T2 files:** src/tools/station_predictor.py, stuck_permit.py, what_if_simulator.py, cost_of_delay.py + matching test files (ALL NEW)
**T3 files:** web/routes_auth.py, web/feature_gate.py, web/templates/onboarding_*.html, web/routes_search.py, web/routes_public.py, src/ingest.py, tests/e2e/*, scripts/seed_demo.py

### Step 3: Full test suite

```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e
```

QS7's 26 cache tests (test_page_cache.py + test_brief_cache.py) should still pass.

### Step 4: Design lint (templates should still be 5/5)

```bash
python scripts/design_lint.py --changed --quiet
```

### Step 5: Prod gate

```bash
python scripts/prod_gate.py --quiet
```

### Step 6: Promote

```bash
git checkout prod && git merge main && git push origin prod && git checkout main
```

### Step 7: Post-promotion

```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5
```

### Step 8: Cleanup

```bash
git worktree prune
git branch | grep worktree-agent | xargs git branch -d 2>/dev/null
```

---

## Report Template

```
QS8 COMPLETE — Sprints 79-81
============================================
Started: [time]  Finished: [time]  Duration: [N] min

Terminal 1 (Performance — Sprint 79):
  A: Report N+1 fix:         [PASS/FAIL]
  B: Pipeline stats + cron:   [PASS/FAIL]
  C: SODA circuit breaker:    [PASS/FAIL]
  D: Headers + timing + pool: [PASS/FAIL]

Terminal 2 (Intelligence — Sprint 80):
  A: Station predictor:       [PASS/FAIL] [N tests]
  B: Stuck permit playbook:   [PASS/FAIL] [N tests]
  C: What-if simulator:       [PASS/FAIL] [N tests]
  D: Cost of delay:           [PASS/FAIL] [N tests]

Terminal 3 (Beta + Data — Sprint 81):
  A: Onboarding + features:   [PASS/FAIL]
  B: Search NLP:              [PASS/FAIL]
  C: Trade permits ingest:    [PASS/FAIL]
  D: E2E tests + seed:        [PASS/FAIL] [N E2E]

Post-merge:
  Full test suite: [N passed / M failed]
  Design lint: [N/5]
  Prod gate: [PROMOTE/HOLD]
  Promoted: [commit hash]
  Prod health: [ok/error]

Hotfixes needed: [list or "none"]
```

---

## Failure Recovery

| Scenario | Action |
|---|---|
| One agent fails | Terminal merges other 3. Failed task = follow-up. |
| Entire terminal fails | Merge other 2. Failed terminal = follow-up sprint. |
| Tests fail after merge | Check which test. Cross-terminal mismatch = fix implementation. |
| Merge conflicts | Should not happen. File owner wins. |
| Prod gate HOLD | Read report. Score 3 = promote + mandatory hotfix. |
| Task launch error | Take over immediately. Don't wait for orphaned agent. |
