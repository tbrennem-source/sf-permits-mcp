# QS9 Terminal 4: Cleanup + Documentation + API Routes

You are the orchestrator for Sprint 85. Spawn 4 parallel build agents, collect results, merge, push to main. Do NOT run the full test suite — T0 handles that.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T4 start: $(git rev-parse --short HEAD)"
```

## File Ownership

| Agent | Files Owned |
|-------|-------------|
| A | `web/routes_api.py` |
| B | `scenarios-pending-review.md`, `scenario-design-guide.md` (read-only), delete `scenarios-pending-review-*.md` per-agent files |
| C | Delete stale files in `sprint-prompts/`, `web/static/landing-v5.html`, etc. |
| D | `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, delete `CHANGELOG-qs*.md` files |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Intelligence Tool API Routes

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Expose 4 intelligence tools as JSON API endpoints

### File Ownership
- web/routes_api.py (ONLY this file)

### Read First
- web/routes_api.py (existing API endpoints — follow the pattern)
- src/tools/predict_next_stations.py (function signature)
- src/tools/stuck_permit.py (function signature)
- src/tools/what_if_simulator.py (function signature)
- src/tools/cost_of_delay.py (function signature)
- web/auth.py (login_required decorator)
- web/helpers.py (run_async helper for async-to-sync)

### Build

4 endpoints:
- GET /api/predict-next/<permit_number> → predict_next_stations
- GET /api/stuck-permit/<permit_number> → diagnose_stuck_permit
- POST /api/what-if (JSON body: base_description, variations) → simulate_what_if
- POST /api/delay-cost (JSON body: permit_type, monthly_carrying_cost) → calculate_delay_cost

All require @login_required. Use run_async for async tools. Return jsonify. Input validation → 400 on missing fields. Try/except → 500 with error message.

### Test
Write tests/test_api_intelligence.py:
- test_predict_next_requires_auth
- test_predict_next_returns_json
- test_stuck_permit_returns_json
- test_what_if_requires_post
- test_what_if_returns_json
- test_delay_cost_validates_input
- test_delay_cost_returns_json

### Scenarios
Write 3 scenarios to scenarios-pending-review-sprint-85-a.md:
- Scenario: API client fetches next station prediction for active permit
- Scenario: API rejects unauthenticated request with 401
- Scenario: What-if endpoint compares base vs variation scenarios

### CHECKCHAT
Summary: 4 API endpoints created, auth enforced, tests passing. Visual QA Checklist: N/A — JSON API only.

### Output Files
- scenarios-pending-review-sprint-85-a.md
- CHANGELOG-sprint-85-a.md

### Commit
feat: expose 4 intelligence tools as JSON API endpoints (Sprint 85-A)
""")
```

---

### Agent B: Scenario Consolidation + Drain

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Consolidate and categorize 100+ pending scenarios

### File Ownership
- scenarios-pending-review.md
- scenario-design-guide.md (READ ONLY — for dedup checking)
- Delete all scenarios-pending-review-qs*.md and scenarios-pending-review-sprint-*.md files

### Read First
- scenario-design-guide.md (73 approved — dedup against these)
- scenarios-pending-review.md (current pending)
- ls root for all per-agent scenario files

### Build

1. Consolidate all per-agent files into scenarios-pending-review.md (skip duplicates)
2. Add summary table at top: count by category (Property Intelligence, Search, Onboarding, Performance, Admin, Data)
3. Flag near-duplicates with **DUPLICATE OF:** [title]
4. Delete all per-agent scenario files
5. Count total unique scenarios

### Test
ls scenarios-pending-review-*.md 2>/dev/null | wc -l  # Should be 0
grep -c "SUGGESTED SCENARIO" scenarios-pending-review.md

### CHECKCHAT
Summary: [N] unique scenarios, [M] duplicates flagged, [K] per-agent files deleted. Visual QA Checklist: N/A.

### Commit
chore: consolidate 100+ scenarios — [N] unique, [M] duplicates flagged (Sprint 85-B)
""")
```

---

### Agent C: Stale File Cleanup

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Delete stale/obsolete files

### File Ownership
- sprint-prompts/ (DELETE stale files only — NOT qs8-* or qs9-* or sprint-79/80/81)
- web/static/landing-v5.html (DELETE)
- .claude/hooks/.stop_hook_fired (DELETE)
- scenarios-reviewed-sprint69.md (DELETE)
- scripts/public_qa_checks.py (DELETE if nothing imports it)
- scripts/sprint69_visual_qa.py (DELETE if nothing imports it)

### Rules
- Grep for imports before deleting scripts
- Do NOT delete qs8-*, qs9-*, sprint-79-*, sprint-80-*, sprint-81-*, sprint-82-* (current/recent)

### Build
Delete stale sprint prompts: qs3-*, sprint-68*, sprint-69-*
Delete stale artifacts: landing-v5.html, scenarios-reviewed-sprint69.md, .stop_hook_fired
Check + delete obsolete scripts

### Test
ls sprint-prompts/qs3-* sprint-prompts/sprint-68* sprint-prompts/sprint-69-* 2>/dev/null | wc -l  # 0
test -f web/static/landing-v5.html && echo "EXISTS" || echo "DELETED"

### Scenarios
Write 1 scenario to scenarios-pending-review-sprint-85-c.md:
- Scenario: New developer finds clean sprint-prompts/ with only current/recent sprints

### CHECKCHAT
Summary: [N] files deleted. Visual QA Checklist: N/A.

### Output Files
- scenarios-pending-review-sprint-85-c.md
- CHANGELOG-sprint-85-c.md

### Commit
chore: delete [N] stale files — old sprint prompts + prototype artifacts (Sprint 85-C)
""")
```

---

### Agent D: Documentation Update

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Update project docs with QS7/QS8/Sprint 78 results

### File Ownership
- README.md
- docs/ARCHITECTURE.md
- CHANGELOG.md
- Delete all CHANGELOG-qs*.md per-agent files

### Read First
- README.md (key numbers, tool list)
- docs/ARCHITECTURE.md (tool inventory, data flow)
- CHANGELOG.md (format, latest entries)
- ls for CHANGELOG-qs*.md files

### Build

1. Consolidate CHANGELOG-qs*.md files into CHANGELOG.md, delete per-agent files
2. Update README.md: tools 30→34, tests ~3,782+, tables 65, add intelligence tools
3. Update ARCHITECTURE.md: add Intelligence Tools section, update tool count, add page_cache + circuit breaker
4. Add QS7/Sprint 78/QS8 entries to CHANGELOG if missing

### Test
grep "34" README.md  # Updated tool count
grep -i "intelligence" docs/ARCHITECTURE.md  # New section
ls CHANGELOG-qs*.md 2>/dev/null | wc -l  # 0

### Scenarios
Write 2 scenarios to scenarios-pending-review-sprint-85-d.md:
- Scenario: New developer reads README and finds accurate project stats
- Scenario: Architecture doc describes all 34 tools with one-line summaries

### CHECKCHAT
Summary: docs updated, per-agent files consolidated + deleted. Visual QA Checklist: N/A.

### Output Files
- scenarios-pending-review-sprint-85-d.md
- CHANGELOG-sprint-85-d.md

### Commit
docs: update README, ARCHITECTURE, CHANGELOG — 34 tools, 3782+ tests (Sprint 85-D)
""")
```

---

## Post-Agent: Merge + Push

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
# A first (API routes), D (docs), B (scenarios — needs clean CHANGELOG), C (deletions last)
git merge <agent-a-branch> --no-edit
git merge <agent-d-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit
cat scenarios-pending-review-sprint-85-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-sprint-85-*.md >> CHANGELOG.md 2>/dev/null
git push origin main
```

## Report

```
T4 (Cleanup + Docs + API) COMPLETE
  A: API routes:             [PASS/FAIL] (4 new /api/ endpoints)
  B: Scenario consolidation: [PASS/FAIL] ([N] unique, [M] duplicates)
  C: Stale file cleanup:     [PASS/FAIL] ([N] files deleted)
  D: Documentation update:   [PASS/FAIL]
  Scenarios: [N] across 4 files
  Pushed: [commit hash]
```
