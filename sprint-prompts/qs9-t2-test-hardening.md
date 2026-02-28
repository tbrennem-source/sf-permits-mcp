# QS9 Terminal 2: Test Hardening

You are the orchestrator for QS9-T2. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

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

### Problem
Two tests assert text from before Sprint 69's landing rebuild:
- test_landing_has_feature_cards: asserts "Permit Search" — this text no longer exists
- test_landing_has_stats: asserts "Permits tracked" — this text no longer exists

### Build
1. Read the current landing.html template
2. Find what text/elements ARE present (headings, key phrases, structural elements)
3. Update the two failing tests to assert on actual content
4. Keep the test intent: "landing page has feature descriptions" and "landing page has data stats"
5. Do NOT delete the tests — update their assertions

### Test
```bash
source .venv/bin/activate
pytest tests/test_landing.py -v --tb=short 2>&1 | tail -20
# All tests should pass
```

### Output Files
- scenarios-pending-review-qs9-t2-a.md
- CHANGELOG-qs9-t2-a.md

### Commit
fix: update stale landing test assertions for Sprint 69 redesign (QS9-T2-A)
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
- tests/conftest.py (ONLY the _clear_page_cache or cleanup fixture — do NOT touch _isolated_test_db)

### Problem
test_page_cache.py passes in isolation (16/16) but test_cache_hit_returns_cached fails in the full suite. Root cause: a preceding test leaves stale data in the session-scoped temp DuckDB. The cleanup fixture only deletes rows matching 'test:%' and 'brief:%' but another test inserts rows with different key patterns.

### Build

Task B-1: Make page_cache cleanup more robust in test_page_cache.py:
- Before each test class: DELETE FROM page_cache (clear ALL rows, not just pattern-matched)
- Use a class-scoped or function-scoped fixture that truncates the table
- Alternative: use unique cache keys per test via uuid prefix: f"test:{uuid4().hex[:8]}:miss"

Task B-2: Verify the fix works in a simulated full-suite context:
```bash
# Run page_cache tests after running some other test file (simulates full suite ordering)
pytest tests/test_auth.py tests/test_page_cache.py -v --tb=short
pytest tests/test_web.py tests/test_page_cache.py -v --tb=short
```

### Test
```bash
source .venv/bin/activate
# Must pass BOTH in isolation AND after other tests
pytest tests/test_page_cache.py -v --tb=short
pytest tests/test_auth.py tests/test_brief.py tests/test_page_cache.py -v --tb=short
```

### Output Files
- scenarios-pending-review-qs9-t2-b.md
- CHANGELOG-qs9-t2-b.md

### Commit
fix: eliminate page_cache test flakiness — robust cleanup between test classes (QS9-T2-B)
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
Flask app has a CRON_GUARD before_request hook that returns 404 for /cron/* endpoints unless CRON_WORKER=1 env var is set. Tests that hit cron endpoints without setting this get 404 instead of expected 403 (auth) or 200 (success).

### Build

Task C-1: Grep all test files for /cron/ endpoint calls:
```bash
grep -rn "client.post.*cron\|client.get.*cron" tests/ | grep -v ".pyc"
```

Task C-2: For every test that calls a /cron/ endpoint:
- Verify it has `monkeypatch.setenv("CRON_WORKER", "1")`
- If missing, add it
- Exception: tests that INTENTIONALLY test the CRON_GUARD behavior (test that /cron/ returns 404 without CRON_WORKER)

Task C-3: Run all affected test files to verify fixes.

### Test
```bash
source .venv/bin/activate
pytest tests/test_brief_cache.py tests/test_sprint_79_3.py -v --tb=short 2>&1 | tail -20
# Also run any test_cron_*.py files found
```

### Output Files
- scenarios-pending-review-qs9-t2-c.md
- CHANGELOG-qs9-t2-c.md

### Commit
fix: add CRON_WORKER env var to all cron endpoint tests (QS9-T2-C)
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

### Problem
46+ stale worktree branches from sprints 58-81 accumulated. They clutter git branch output and may hold stale DuckDB locks.

### Build

Task D-1: Document current state:
```bash
git worktree list | wc -l
git branch | grep worktree-agent | wc -l
```

Task D-2: Prune dead worktrees (directories already removed):
```bash
git worktree prune
```

Task D-3: List branches that are safe to delete (already merged to main):
```bash
git branch --merged main | grep worktree-agent
```

Task D-4: Delete merged agent branches:
```bash
git branch --merged main | grep worktree-agent | xargs git branch -d
```

Task D-5: Report any UNMERGED branches (DO NOT delete these — report only):
```bash
git branch --no-merged main | grep worktree-agent
```

Task D-6: Fix any minor test issues in test_sprint_79_d.py if they exist.

### Test
```bash
git worktree list | wc -l  # Should be much smaller
git branch | grep worktree-agent | wc -l  # Should be 0 or near 0
```

### Output Files
- CHANGELOG-qs9-t2-d.md (document how many branches/worktrees cleaned)

### Commit
chore: clean up 46+ stale worktree branches from sprints 58-81 (QS9-T2-D)
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
cat scenarios-pending-review-qs9-t2-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-qs9-t2-*.md >> CHANGELOG.md 2>/dev/null
git push origin main
```

## Report

```
T2 (Test Hardening) COMPLETE
  A: Landing test fix:       [PASS/FAIL]
  B: Page cache flakiness:   [PASS/FAIL]
  C: CRON_WORKER audit:      [PASS/FAIL] ([N] tests fixed)
  D: Worktree cleanup:       [PASS/FAIL] ([N] branches deleted)
  Pushed: [commit hash]
```
