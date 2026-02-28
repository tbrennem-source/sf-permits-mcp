# QS9 Terminal 2: Test Hardening

You are the orchestrator for Sprint 83. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T2 start: $(git rev-parse --short HEAD)"
```

## File Ownership

| Agent | Files Owned |
|-------|-------------|
| A | `tests/test_landing.py` |
| B | `tests/test_page_cache.py`, `tests/conftest.py` (cleanup fixture ONLY) |
| C | `tests/test_brief_cache.py`, `tests/test_sprint_79_3.py`, any `tests/test_cron_*.py` |
| D | Git operations (worktree prune, branch cleanup), `tests/test_sprint_79_d.py` (minor) |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Fix Stale Landing Tests

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Fix stale landing page test assertions

### File Ownership
- tests/test_landing.py (ONLY this file)

### Read First
- tests/test_landing.py (find test_landing_has_feature_cards and test_landing_has_stats)
- web/templates/landing.html (current landing page — what text actually appears?)

### Build
1. Read current landing.html
2. Find what text/elements ARE present
3. Update the two failing tests to assert on actual content
4. Keep the test intent — just fix the assertions
5. Do NOT delete tests — update them

### Test
source .venv/bin/activate && pytest tests/test_landing.py -v --tb=short

### Scenarios
Write 0-1 scenarios to scenarios-pending-review-sprint-83-a.md:
- Scenario: Landing page displays key feature descriptions to new visitor
- Scenario: Landing page shows data credibility stats

### CHECKCHAT
Summary: tests fixed, all passing, scenarios written. Visual QA Checklist: N/A — test-only change.

### Output Files
- scenarios-pending-review-sprint-83-a.md
- CHANGELOG-sprint-83-a.md

### Commit
fix: update stale landing test assertions for Sprint 69 redesign (Sprint 83-A)
""")
```

---

### Agent B: Fix Page Cache Intra-Session Flakiness

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Fix page_cache test flakiness in full suite runs

### File Ownership
- tests/test_page_cache.py
- tests/conftest.py (ONLY the cleanup fixture — do NOT touch _isolated_test_db)

### Problem
test_page_cache.py passes in isolation (16/16) but test_cache_hit_returns_cached fails in full suite. A preceding test leaves stale data in the session-scoped temp DuckDB.

### Build
Make cleanup more robust — either:
- DELETE FROM page_cache before each test class (not just test:%/brief:% patterns)
- Or use unique cache keys per test via uuid prefix

Verify fix works after other tests:
pytest tests/test_auth.py tests/test_page_cache.py -v --tb=short
pytest tests/test_web.py tests/test_page_cache.py -v --tb=short

### Test
source .venv/bin/activate
pytest tests/test_page_cache.py -v --tb=short
pytest tests/test_auth.py tests/test_brief.py tests/test_page_cache.py -v --tb=short

### Scenarios
Write 0-1 scenarios to scenarios-pending-review-sprint-83-b.md:
- Scenario: Page cache returns cached result on second request
- Scenario: Page cache cleanup prevents cross-test contamination

### CHECKCHAT
Summary: flakiness fixed, verified in multi-file context, scenarios written. Visual QA Checklist: N/A.

### Output Files
- scenarios-pending-review-sprint-83-b.md
- CHANGELOG-sprint-83-b.md

### Commit
fix: eliminate page_cache test flakiness — robust cleanup between tests (Sprint 83-B)
""")
```

---

### Agent C: Audit Cron Tests for CRON_WORKER

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Ensure all cron endpoint tests set CRON_WORKER env var

### File Ownership
- tests/test_brief_cache.py
- tests/test_sprint_79_3.py
- Any tests/test_cron_*.py files

### Problem
CRON_GUARD returns 404 for /cron/* without CRON_WORKER=1. Tests that miss this get 404 instead of expected 403/200.

### Build
1. Grep all test files for /cron/ endpoint calls
2. For every test hitting /cron/: verify monkeypatch.setenv("CRON_WORKER", "1") exists
3. If missing, add it
4. Exception: tests intentionally testing CRON_GUARD behavior

### Test
source .venv/bin/activate
pytest tests/test_brief_cache.py tests/test_sprint_79_3.py -v --tb=short

### Scenarios
Write 0-1 scenarios to scenarios-pending-review-sprint-83-c.md:
- Scenario: Cron endpoint rejects unauthenticated requests with 403
- Scenario: Cron endpoint returns 404 when CRON_WORKER not set (guard behavior)

### CHECKCHAT
Summary: [N] tests fixed, all cron tests passing, scenarios written. Visual QA Checklist: N/A.

### Output Files
- scenarios-pending-review-sprint-83-c.md
- CHANGELOG-sprint-83-c.md

### Commit
fix: add CRON_WORKER env var to all cron endpoint tests (Sprint 83-C)
""")
```

---

### Agent D: Worktree + Branch Cleanup

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Clean up stale worktrees and branches

### Build
1. git worktree prune
2. git branch --merged main | grep worktree-agent | list count
3. Delete merged branches: git branch --merged main | grep worktree-agent | xargs git branch -d
4. Report unmerged branches (DO NOT delete — report only)
5. Fix minor issues in test_sprint_79_d.py if any

### Scenarios
Write 0-1 scenarios to scenarios-pending-review-sprint-83-d.md:
- Scenario: Post-sprint cleanup removes all merged worktree branches

### CHECKCHAT
Summary: [N] branches deleted, [M] worktrees pruned, [K] unmerged branches reported. Visual QA Checklist: N/A.

### Output Files
- CHANGELOG-sprint-83-d.md

### Commit
chore: clean up stale worktree branches from sprints 58-81 (Sprint 83-D)
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
git merge <agent-d-branch> --no-edit
cat scenarios-pending-review-sprint-83-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-sprint-83-*.md >> CHANGELOG.md 2>/dev/null
git push origin main
```

## Report

```
T2 (Test Hardening) COMPLETE
  A: Landing test fix:       [PASS/FAIL]
  B: Page cache flakiness:   [PASS/FAIL]
  C: CRON_WORKER audit:      [PASS/FAIL] ([N] tests fixed)
  D: Worktree cleanup:       [PASS/FAIL] ([N] branches deleted)
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
