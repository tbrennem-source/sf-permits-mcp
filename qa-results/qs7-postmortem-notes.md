# QS7 Post-Mortem: Beta Readiness Quad Sprint

**Sprint:** QS7 (Sprints 74-77 equivalent)
**Date:** 2026-02-27
**Duration:** ~35 minutes agent work + ~15 minutes merge ceremony + ~10 minutes test reconciliation = ~60 minutes total
**Result:** PROMOTED TO PROD (52 files, 11,086 insertions)

---

## Executive Summary

QS7 shipped successfully: 9 core templates migrated to 5/5 design lint, page_cache infrastructure, cron pre-compute, 40+ new tests, prod gate v2, obsidian.css (1,476 lines). All 16 agents across 4 terminals completed. However, the sprint surfaced 15 issues — mostly in orchestration, test infrastructure, and cross-terminal interface contracts — that need to be fixed before the next quad sprint.

**Key metric:** Of the ~60 minutes total, only ~35 were productive agent work. The remaining ~25 were wasted on redundant pre-flight checks, redundant post-merge test runs, DuckDB contention, and manual intervention. A well-specced sprint should be ~40 minutes end-to-end.

---

## What Went Right

1. **All 16 agents completed.** No agent failures. Every agent delivered its assigned work.
2. **Design lint: 1/5 → 5/5.** 193 violations → 0 across all 9 core templates. This was the sprint goal and it shipped.
3. **File ownership was clean.** T1 (backend), T2 (public templates), T3 (auth templates), T4 (tests/docs) had zero production file overlap. All merges were clean except append-only files.
4. **T2 and T3 had excellent pre-flight.** Both skipped redundant test suites and went straight to agents. T2 only ran design lint baseline. T3 same.
5. **Cross-terminal dependency worked.** T4's cache tests correctly fail until T1 merges. The spec anticipated this. T0 reconciled the interface mismatches in the merge ceremony (~10 minutes).
6. **Prod gate caught a real issue** (false positive in secret scanner) and a real issue (test/implementation interface mismatches). Both were fixed before promotion.

---

## Issues Log (15 issues)

### Category A: Sprint Prompt Spec Quality (5 issues)

These are spec-quality problems — the prompts didn't give terminals/agents enough information to avoid wasted work.

#### Issue 1: `--timeout=30` flag doesn't exist
- **Where:** T0, T1 pre-flight
- **What:** Sprint prompts include `pytest --timeout=30` but `pytest-timeout` is not installed
- **Impact:** Minor — recovered by re-running without flag
- **Fix for next sprint:** Remove `--timeout=30` from all prompt templates. Or install `pytest-timeout`.

#### Issue 2: T1-T4 prompts duplicate T0 pre-flight
- **Where:** T1 spent 5+ minutes re-running full test suite before spawning agents
- **What:** Terminal prompts include their own full `pytest` pre-flight. T0 already verified.
- **Impact:** ~5 min wasted per terminal = up to 20 min total
- **Fix for next sprint:** T1-T4 pre-flight should be: `git pull && git log --oneline -3`. One line. No tests. Add explicit: "T0 already verified tests pass — skip to agent launch."

#### Issue 3: Pre-existing test failures not documented
- **Where:** T1 hit `test_landing.py`, started excluding files iteratively
- **What:** Known pre-existing failures aren't listed in prompts, so terminals waste time investigating each one
- **Impact:** Compounds issue #2 — each exclusion triggers another full test run
- **Fix for next sprint:** Include a "Known test exclusions" section: `--ignore=tests/e2e --ignore=tests/test_tools.py`

#### Issue 5: Terminals re-run full test suite after internal merge
- **Where:** T2, T4 post-merge (T1, T3 likely also)
- **What:** After merging 4 agent branches, terminals run the full test suite. This is T0's job.
- **Impact:** 5-10 min per terminal × 4 = 20-40 min wasted compute, plus DuckDB contention
- **Fix for next sprint:** Terminal prompts must say: "After merging agents, push to main. Do NOT run the full test suite — T0 handles that in merge ceremony."

#### Issue 11: Agent used wrong CSS variable names
- **Where:** T3 agent 3C, index.html
- **What:** Used `var(--font-display)` and `var(--font-body)` instead of `var(--mono)` and `var(--sans)`. 64 violations.
- **Impact:** T3 orchestrator fixed manually (+5 min)
- **Root cause:** DESIGN_TOKENS.md has both legacy and current naming. Agent picked the wrong one.
- **Fix for next sprint:** Agent prompts must include explicit mapping table. Sprint prompt "gotchas" section.

### Category B: Cross-Terminal Interface Contracts (3 issues)

These are the T1↔T4 interface mismatches where the test spec and implementation diverged.

#### Issue 13: CRON_WORKER env var missing from cache tests
- **Where:** T0 merge ceremony test run
- **What:** T4's cron cache tests didn't set `CRON_WORKER=1`, so CRON_GUARD returned 404 before auth was checked
- **Impact:** 3 test failures, ~5 min to diagnose and fix
- **Root cause:** T4 didn't know about CRON_GUARD. The sprint spec didn't include this gotcha.
- **Fix for next sprint:** Sprint prompts for test-writing agents must include "Known DuckDB/Postgres/Flask Gotchas" section listing CRON_WORKER, TESTING mode, daily limits, etc.

#### Issue 14: Parameter name mismatch (ttl vs ttl_minutes)
- **Where:** T0 merge ceremony
- **What:** T4 tests use `ttl=60`, T1 implementation uses `ttl_minutes=30`
- **Impact:** 30+ occurrences, bulk rename fix
- **Root cause:** The spec said `ttl` but T1 chose the more explicit `ttl_minutes`. No shared interface contract.
- **Fix for next sprint:** When T4 writes tests against T1's implementation, the sprint spec must include an explicit API contract: `def get_cached_or_compute(cache_key: str, compute_fn: callable, ttl_minutes: int = 30) -> dict`. Function signature, parameter names, return types.

#### Issue 15: Implementation architecture diverged from test assumptions
- **Where:** T0 merge ceremony
- **What:** T4 assumed in-memory dict cache (`_page_cache`). T1 built DB-backed `page_cache` table. T4 expected `invalidate_cache()` to return count; T1 returns None. T4 expected numeric timestamps; T1 returns ISO strings.
- **Impact:** Multiple test fixes needed — fixture rewrite (dict.clear → DB truncate), return value assertions, timestamp format
- **Root cause:** The spec described the interface but not the architecture. "Cache" could mean in-memory or DB-backed. T1 and T4 made different assumptions.
- **Fix for next sprint:** Interface contracts must specify: storage mechanism (DB table vs dict), return types, metadata fields injected, error handling behavior. Not just function signatures.

### Category C: DuckDB Infrastructure (3 issues)

All resolved by Chief task #357 (Sprint 78: Postgres test migration).

#### Issue 4: 382 DuckDB lock contention failures
- **Where:** T0 full parallel test run
- **What:** Tests pass in isolation but fail in parallel due to DuckDB single-writer lock
- **Impact:** Masks real regressions in merge ceremony test run

#### Issue 6: DuckDB stale process lock
- **Where:** T2 post-merge
- **What:** A Python process (PID 71831) held the DuckDB lock from a parallel agent worktree
- **Impact:** T2 had to kill the process manually

#### Issue 8: Parallel terminal test runs amplify contention
- **Where:** 4 terminals running pytest simultaneously against same `permits.db`
- **What:** All competing for single-writer lock, causing cascading failures
- **Impact:** Tim had to interrupt T2 and T4 to stop the bleeding

### Category D: Swarm Rule Violations (2 issues)

#### Issue 9a: Agent 3C self-merged to main
- **Where:** T3, agent 3C (portfolio + index)
- **What:** Agent merged its own branch to main instead of leaving it to the terminal orchestrator
- **Impact:** T3 had to merge remaining 3 branches on top of unauthorized merge
- **Root cause:** Agent prompt says "Do NOT merge to main" but 3C's CHECKCHAT/SHIP step overrode it
- **Fix for next sprint:** Agent preamble must be even stronger: `CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main. COMMIT to your worktree branch ONLY. The orchestrator handles all merges. Violating this rule destroys other agents' work.`

#### Issue 10: Append-only files still causing merge conflicts
- **Where:** T2 (scenarios), T3 (scenarios + DESIGN_COMPONENT_LOG)
- **What:** Multiple agents appending to same files = guaranteed conflict
- **Impact:** T3 spent significant time resolving 3 rounds of conflicts
- **Root cause:** QS7 prompts didn't enforce per-agent files for append-only targets
- **Fix for next sprint:** MANDATORY per-agent output files. `scenarios-pending-review-{terminal}-{agent}.md`, `CHANGELOG-{terminal}.md`, `DESIGN_COMPONENT_LOG-{terminal}.md`. Orchestrator concatenates.

### Category E: Housekeeping (2 issues)

#### Issue 9b: 126 stale worktrees accumulated
- **Where:** T4 ran `git worktree list`
- **What:** Worktrees from sprints 58-77 never cleaned up
- **Fix:** Add to T0 post-sprint: `git worktree prune && git branch | grep worktree-agent | xargs git branch -d`

#### Issue 12: Prod gate false positive on test secrets
- **Where:** T0 promotion gate
- **What:** Gate flagged `monkeypatch.setenv("CRON_SECRET", ...)` as a secret leak
- **Impact:** HOLD verdict, required code fix before promotion
- **Fixed:** Added `":!tests/"` exclusion to secret scanner (committed this sprint)

---

## Timing Analysis

```
T+0:00   T0 pre-flight (git pull, tests, prod health, lint baseline)
T+0:08   T0 pre-flight complete. Tim opens T1-T4 terminals.
T+0:10   T1-T4 launched. T2, T3 go straight to agents. T1 stuck in pre-flight.
T+0:15   Tim interrupts T1, tells it to skip to agents.
T+0:15   T2 agents finish (all 4). T2 starts internal merge.
T+0:18   T4 agents finish (all 4). T4 starts internal merge.
T+0:20   T2, T4 merged and pushed. Start redundant test runs.
T+0:22   Tim interrupts T2, T4 test runs (DuckDB contention).
T+0:25   T3 agents finish (all 4). T3 starts internal merge (3C self-merged).
T+0:30   T3 resolves conflicts, pushes. T1 agents finish, starts merge.
T+0:33   T1 merged and pushed. Tim interrupts T1 test run.
T+0:35   T0 merge ceremony begins: git pull, verify commits, file ownership.
T+0:37   Test suite run 1: fail (CRON_WORKER missing in test). Fix.
T+0:40   Test suite run 2: fail (wrong CRON_SECRET tests). Fix.
T+0:43   Test suite run 3: fail (page_cache import). Fix.
T+0:46   Test suite run 4: fail (empty dict assertion). Fix.
T+0:49   Test suite run 5: fail (timestamp format). Fix.
T+0:51   Test suite run 6: 1490 passed, DuckDB contention hit (pre-existing).
T+0:53   Design lint: 5/5 across all 9 templates.
T+0:54   Prod gate: HOLD (secret false positive). Fix gate. Re-run: PROMOTE 3/5.
T+0:57   Commit fixes, push main, merge to prod, push prod.
T+0:60   Post-promotion health check. Done.
```

**Productive time:** ~35 min (agent work) + ~10 min (T0 test reconciliation) = 45 min
**Wasted time:** ~15 min (redundant pre-flight + test runs + interrupts)
**Target for next sprint:** 40 min total (cut waste to ~5 min with better prompts)

---

## Actionable Changes for QS8+ Sprint Prompts

### 1. Terminal Pre-flight (replace current)
```
## Pre-flight (30 seconds, not 5 minutes)
git checkout main && git pull origin main && git log --oneline -3
# T0 already verified tests, prod health, and lint baseline.
# Do NOT run pytest. Go straight to agent launch.
```

### 2. Terminal Post-merge (replace current)
```
## After all agents merged
git push origin main
# Do NOT run the full test suite. T0 runs it once in merge ceremony.
# Your job is done. Report results and stop.
```

### 3. Cross-terminal interface contracts (add to spec)
When T4 writes tests against T1/T2/T3 implementations, the spec must include:
```
### Interface Contract: page_cache API
- Function: get_cached_or_compute(cache_key: str, compute_fn: callable, ttl_minutes: int = 30) -> dict
- Storage: DB table `page_cache`, NOT in-memory dict
- Return: dict from compute_fn, with `_cached: bool` and `_cached_at: str (ISO)` injected on cache hit
- invalidate_cache(pattern: str) -> None (void, best-effort)
- Flask gotcha: cron endpoints require CRON_WORKER=1 env var for test visibility
```

### 4. Append-only file isolation (enforce in prompts)
```
## Output Files (per-agent isolation)
- Scenarios: scenarios-pending-review-{terminal}-{agent}.md
- CHANGELOG: CHANGELOG-{terminal}.md
- Component log: DESIGN_COMPONENT_LOG-{terminal}.md
NEVER append directly to the shared file. Orchestrator concatenates.
```

### 5. Agent merge guardrail (strengthen preamble)
```
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violation = data loss for other agents.
```

### 6. Known test exclusions (add to all prompts)
```
## Known Test Exclusions
pytest --ignore=tests/test_tools.py --ignore=tests/e2e
# DuckDB contention: tests pass in isolation, fail in parallel. Not a regression.
```

### 7. Design token gotchas (add to UI agent prompts)
```
## CSS Variable Mapping (MANDATORY)
--font-display → --mono (data, addresses, numbers)
--font-body → --sans (prose, labels, descriptions)
Do NOT use --font-display or --font-body. They are LEGACY names.
```

### 8. T0 post-sprint cleanup (add to orchestrator)
```
## Cleanup
git worktree prune
git branch | grep worktree-agent | xargs git branch -d 2>/dev/null
```

---

## Metrics

| Metric | Pre-Sprint | Post-Sprint | Delta |
|--------|-----------|-------------|-------|
| Design lint (9 core templates) | 1/5 (193 violations) | 5/5 (0 violations) | +4 |
| Tests passing (sequential -x) | 1669 | 1490+ (new tests added, same contention) | +49 new |
| Tests total (parallel) | 3571 | 3620 | +49 |
| Templates migrated to obsidian | 0 | 9 | +9 |
| New CSS (obsidian.css) | 0 lines | 1,476 lines | +1,476 |
| New JS (toast.js) | 0 | 64 lines | +64 |
| New test files | 0 | 5 (brief_cache, page_cache, cron_compute, design_lint, prod_gate) | +5 |
| Scenarios generated | 0 | ~17 (T3) + 25 drained (T4) | +42 |
| Prod gate version | v1 | v2 (migration, cron, lint trend checks) | upgraded |

---

## Lessons for dforge

These should be captured as dforge lessons for the quad sprint framework:

1. **Cross-terminal interface contracts must be architecture-level, not just function signatures.** (Category B)
2. **Terminal pre-flight and post-merge test runs are T0-only.** Terminals should do < 30 seconds of pre-flight. (Category A)
3. **Append-only file conflicts are guaranteed in multi-agent sprints.** Per-agent files are mandatory, not optional. (Category D)
4. **DuckDB single-writer lock makes parallel test runs destructive, not just slow.** (Category C)
5. **Agent self-merge prevention needs stronger guardrails than a single instruction.** (Category D)
6. **The prod gate works.** It caught both a real issue (test mismatches) and a false positive (test secrets). Fix the false positive, keep the gate. (Category E)
