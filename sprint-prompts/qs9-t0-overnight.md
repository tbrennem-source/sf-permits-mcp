# QS9 T0: Overnight Orchestrator

You are T0 — the overnight orchestrator for QS9. Tim has launched T1-T4 in separate CC terminals and gone to sleep. Your job:

1. **Poll** for terminal pushes to main
2. **Merge ceremony** when all 4 have pushed
3. **Visual QA scoring** on staging
4. **Broken link scan**
5. **Promote** if clean, leave report if blocked

## Context

Read these files first:
- sprint-prompts/qs9-overnight-spec.md (full spec — 4 terminals, 16 agents)
- CLAUDE.md (project rules, protocols)

QS7, Sprint 78, and QS8 are all in prod. Main is clean at the commit Tim launched from.

4 terminals are running:
- T1: Tool registration + admin health (3 agents)
- T2: Test hardening (4 agents)
- T3: Scaling infra — Redis rate limiter, pool tuning, cache headers (4 agents)
- T4: Cleanup — API routes, scenario drain, stale files, docs (4 agents)

## Step 1: Poll for terminal pushes

Check every 3-5 minutes:
```bash
git pull origin main && git log --oneline -30 | head -30
```

Look for commits containing: QS9-T1, QS9-T2, QS9-T3, QS9-T4. Each terminal pushes once after merging its agents. Track which terminals have pushed:

- [ ] T1 pushed (look for: "QS9-T1" in commit messages)
- [ ] T2 pushed (look for: "QS9-T2" in commit messages)
- [ ] T3 pushed (look for: "QS9-T3" in commit messages)
- [ ] T4 pushed (look for: "QS9-T4" in commit messages)

**Do NOT proceed to Step 2 until all 4 have pushed.** If a terminal hasn't pushed after 30 minutes, check if its worktree branches have commits (it may have finished but failed to push). If worktree branches have commits, merge them yourself.

## Step 2: Merge ceremony

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
```

### 2a: Full test suite
```bash
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -15
```
If failures: check if they're pre-existing (DuckDB contention) or new. New failures → document, do NOT promote.

### 2b: Design lint
```bash
python scripts/design_lint.py --changed --quiet
```

### 2c: Prod gate
```bash
python scripts/prod_gate.py --quiet
```

## Step 3: Visual QA scoring (MANDATORY)

Deploy to staging first (push to main triggers auto-deploy). Wait 2-3 minutes.

```bash
# Verify staging is healthy
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool | head -3
```

### 3a: Capture screenshots + score all pages
```bash
# Get TEST_LOGIN_SECRET for auth pages
export TEST_LOGIN_SECRET=$(railway service link sfpermits-ai-staging 2>/dev/null; railway variables --json 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('TEST_LOGIN_SECRET',''))")

python scripts/visual_qa.py \
  --url https://sfpermits-ai-staging-production.up.railway.app \
  --sprint qs9 \
  --capture-goldens
```

If visual_qa.py fails or isn't available, capture screenshots manually with Playwright or curl, then read each screenshot with the Read tool and score 1-5:
- 5: Polished, production-ready
- 4: Minor issues (spacing, font weight)
- 3: Noticeable issues but usable
- 2: Significant problems — layout broken or off-brand
- 1: Broken — unusable

### 3b: Score each page yourself
Read each screenshot PNG captured in qa-results/screenshots/qs9/. For each:
- Score 1-5
- Note any issues

Write results to qa-results/qs9-visual-scores.md:
```markdown
# QS9 Visual QA Scores

| Page | Desktop | Mobile | Issues |
|------|---------|--------|--------|
| / (landing) | X/5 | X/5 | ... |
| /search | X/5 | X/5 | ... |
| /brief | X/5 | X/5 | ... |
| /report | X/5 | X/5 | ... |
| /portfolio | X/5 | X/5 | ... |
| /admin | X/5 | X/5 | ... |
| /methodology | X/5 | X/5 | ... |
| /demo | X/5 | X/5 | ... |
```

Pages ≤2.0 → add as Chief tasks for design session.

### 3c: Broken link scan
```bash
pytest tests/e2e/test_links.py -v --tb=short 2>&1 | tee qa-results/qs9-link-check.md
```
If test_links.py needs a running server, start one:
```bash
TESTING=1 python -m web.app &
sleep 3
# Then run the link test against localhost
```

Broken links → document in report, add as Chief task.

## Step 4: Promote (if clean)

```bash
git add -f qa-results/qs9-* qa-results/screenshots/ qa-results/filmstrips/ 2>/dev/null
git commit -m "qa: QS9 visual scores + link check results

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
git push origin main

# Promote
git checkout prod && git merge main && git push origin prod && git checkout main
```

Verify prod:
```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -3
```

## Step 5: Report to Chief

```bash
# Post session note via Chief MCP
```

Report template:
```
QS9 OVERNIGHT COMPLETE
======================
Duration: [first push time] to [promote time]

T1 (Registration): [PASS/FAIL]
T2 (Test Hardening): [PASS/FAIL]
T3 (Scaling): [PASS/FAIL]
T4 (Cleanup): [PASS/FAIL]

Post-merge:
  Test suite: [N passed / M failed]
  Design lint: [N/5]
  Prod gate: [PROMOTE/HOLD]

Visual QA:
  Pages scored: [N]
  Average score: [X.X/5]
  Pages ≤2.0 (need design attention): [list]

Link check:
  Total links: [N]
  Broken: [M] [list if any]

Promoted: [commit hash] / NOT PROMOTED: [reason]

Chief tasks added:
  - [any pages ≤2.0]
  - [any broken links]
```

## Step 6: Worktree cleanup

```bash
git worktree prune
git branch --merged main | grep worktree-agent | xargs git branch -d 2>/dev/null
```

## Rules

- Do NOT debug complex failures past 3 attempts
- Do NOT make design decisions
- Do NOT modify production files outside merge ceremony
- Do NOT force-push
- If blocked: document everything, leave report, do NOT promote
- Tim wakes up to a complete report either way
