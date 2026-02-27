# QS7 Terminal 0: Orchestrator

> This is Tim's terminal. T0 has the full context, runs pre-flight, launches T1-T4,
> monitors progress, merges in order, runs the prod gate, and promotes.
>
> **Do NOT paste this into an agent.** Tim reads this and executes it manually,
> pasting T1-T4 prompts into separate CC terminals.

## Context

**Sprint goal:** Beta readiness — sub-second brief page + all core pages on the obsidian design system.

**What ships:**
- `page_cache` table + cache-read pattern → /brief loads in <200ms
- Cron pre-compute for active user briefs + event-driven invalidation
- Cache-Control headers for static pages
- `obsidian.css` production stylesheet (26 components from DESIGN_TOKENS.md)
- 9 core templates migrated: landing, search, results, report, brief, portfolio, index, auth, error
- Nav fragment + error pages redesigned
- Toast notification system (`toast.js`) wired to watch actions
- Prod gate v2 (migration safety, cron health, lint trend)
- Component golden test script (26 components)
- 40+ new tests (cache, lint, gate)
- 25 pending scenarios drained
- Black Box Protocol docs updated

**Chief tasks resolved:** #349 (Phase A), #355, #350, #352, #353, #354, #356

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
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --timeout=30 2>&1 | tail -3

# Verify prod is healthy
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Record sprint start commit for post-merge diff audit
echo "Sprint start: $(git rev-parse --short HEAD)"

# Baseline lint scores for core templates
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/report.html web/templates/brief.html web/templates/portfolio.html --quiet
```

**Stop conditions:** If tests fail, if prod is unhealthy, or if HEAD has unexpected changes — investigate before launching.

---

## Launch Sequence

Open 4 CC terminal windows. In each, paste the command to read the terminal's sprint prompt.

| Terminal | Command to paste | What it does |
|---|---|---|
| **T1** | `Read sprint-prompts/qs7-t1-speed.md and execute it` | Speed infrastructure: cache, cron, headers, gate |
| **T2** | `Read sprint-prompts/qs7-t2-public-templates.md and execute it` | CSS + public pages: landing, search, results, nav, errors |
| **T3** | `Read sprint-prompts/qs7-t3-auth-templates.md and execute it` | Auth pages: brief, report, portfolio, index, toast |
| **T4** | `Read sprint-prompts/qs7-t4-testing.md and execute it` | Tests, goldens, docs, scenario drain |

**Launch all 4 simultaneously.** Each terminal spawns 4 agents via Task tool (16 agents total).

---

## Monitoring

While terminals run, T0 watches for:

1. **Agent failures** — if a terminal reports an agent failed, note it. Do not intervene unless all 4 agents in a terminal failed.
2. **File ownership violations** — if any terminal's agent accidentally touches a file owned by another terminal, that's a merge conflict. The terminal that owns the file takes precedence.
3. **Early finishers** — T1 will likely finish first (~15 min). Don't merge yet — wait for the terminal to complete its own internal merge.

**Expected timeline:**
```
T+0 min:   All 4 terminals launched
T+15 min:  T1 finishes (backend, fastest)
T+20 min:  T2 finishes (CSS + public pages)
T+20 min:  T4 finishes (tests + docs, parallel with T2)
T+25 min:  T3 finishes (auth pages, most complex templates)
T+25-35:   Merge ceremony
T+35 min:  Prod gate → promote
```

---

## Merge Ceremony (T0 runs this)

**Each terminal completes its own internal merge** (4 agent branches → main, push). T0 orchestrates the cross-terminal merge order.

### Step 1: Verify each terminal pushed to main

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -20
# Verify you see commits from all 4 terminals
```

If a terminal hasn't pushed yet, wait. Do not proceed with partial merges.

### Step 2: Conflict check

```bash
# Each terminal pushed independently to main. If there are conflicts,
# git pull would have flagged them. If all 4 pulled + pushed cleanly,
# the file ownership was respected. Verify:
git diff --stat $(git log --oneline -20 | tail -1 | cut -d' ' -f1)..HEAD
# Eyeball the changed files — do they match the file ownership matrix?
```

**File ownership verification:**
- T1 files: `web/helpers.py`, `web/routes_misc.py`, `web/routes_cron.py`, `web/app.py`, `scripts/prod_gate.py`
- T2 files: `web/static/obsidian.css`, `web/templates/fragments/head_obsidian.html`, `web/templates/landing.html`, `web/templates/search_results_public.html`, `web/templates/results.html`, `web/templates/methodology.html`, `web/templates/about_data.html`, `web/templates/demo.html`, `web/templates/error.html`, `web/templates/fragments/nav.html`
- T3 files: `web/templates/brief.html`, `web/templates/report.html`, `web/templates/portfolio.html`, `web/templates/project_detail.html`, `web/templates/index.html`, `web/templates/auth_login.html`, `web/templates/account_prep.html`, `web/templates/beta_request.html`, `web/templates/fragments/feedback_widget.html`, `web/templates/fragments/watch_button.html`, `web/static/toast.js`
- T4 files: `scripts/component_goldens.py`, `tests/test_*.py`, `docs/`, `scenarios-pending-review-qs7-4d.md`

If an unexpected file appears, investigate before continuing.

### Step 3: Full test suite

```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30
```

**If tests fail:** Check which test file. If it's a T4 test (test_page_cache, test_brief_cache, test_design_lint_integration, test_prod_gate), the interface between T1/T2/T3's implementation and T4's test spec doesn't match. Fix the implementation to match the spec, or fix the test if the spec was wrong. These are quick fixes — 5-10 minutes.

### Step 4: Design lint on core pages

```bash
python scripts/design_lint.py --files web/templates/landing.html web/templates/search_results_public.html web/templates/results.html web/templates/report.html web/templates/brief.html web/templates/portfolio.html web/templates/index.html web/templates/auth_login.html web/templates/error.html --quiet
# Target: 5/5 on all migrated templates
```

If any template scores below 5/5, check the violation report and decide: fix now (quick inline edit) or carry as a score-4 hotfix.

### Step 5: Prod gate

```bash
python scripts/prod_gate.py --quiet
# Expected: PROMOTE (4/5 or 5/5)
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

# Verify /brief cache (may need to log in via browser)
# Verify landing page renders with new design
# Verify error page (hit a nonexistent URL)
```

---

## Report Template

After everything is merged and promoted, fill in and post to Chief:

```
QS7 COMPLETE — Beta Readiness Sprint
============================================
Started: [time]  Finished: [time]  Duration: [N] minutes

Terminal 1 (Speed):
  1A page_cache infrastructure: [PASS/FAIL]
  1B /brief cache integration:  [PASS/FAIL]
  1C cron pre-compute:          [PASS/FAIL]
  1D cache headers + gate v2:   [PASS/FAIL]

Terminal 2 (Public Templates):
  2A obsidian.css:              [PASS/FAIL] lint: [N/5]
  2B landing + search:          [PASS/FAIL] lint: [N/5]
  2C results + content:         [PASS/FAIL] lint: [N/5]
  2D nav + errors:              [PASS/FAIL] lint: [N/5]

Terminal 3 (Auth Templates):
  3A brief + cache UI:          [PASS/FAIL] lint: [N/5]
  3B property report:           [PASS/FAIL] lint: [N/5]
  3C portfolio + index:         [PASS/FAIL] lint: [N/5]
  3D auth + toast + fragments:  [PASS/FAIL] lint: [N/5]

Terminal 4 (Testing):
  4A component goldens:         [PASS/FAIL]
  4B cache tests:               [N passed / M failed]
  4C lint + gate tests:         [N passed / M failed]
  4D docs + scenarios:          [N scenarios processed]

Post-merge:
  Full test suite: [N passed / M failed]
  Design lint (core 9): [N/5]
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
| Merge conflicts | Should not happen with clean file ownership. If it does: the terminal that OWNS the file wins. `git checkout --theirs <file>` for the non-owner. |
| Tests fail after merge | Check which test. If T4 test vs T1-T3 implementation mismatch, fix the implementation (T4 tests define correct behavior). |
| Prod gate returns HOLD | Read the report. If score 2 (user-visible): fix before promoting. If score 3 (notable): promote, mandatory hotfix. |
| Prod deploy fails | Check Railway logs. Most common: missing env var or startup migration error. Fix and push again. |
| Brief cache not working | Verify page_cache table exists: `curl /health` and check table list. Verify cron pre-compute ran: check cron_log. |

---

## Post-Sprint

1. **Update Chief:** Post the report via `chief_add_note`, update STATUS.md
2. **Merge scenario drain:** Append `scenarios-pending-review-qs7-4d.md` to main scenarios file
3. **Clean up worktree branches:** `git branch -d` all agent branches
4. **Announce:** Beta is ready for testers
