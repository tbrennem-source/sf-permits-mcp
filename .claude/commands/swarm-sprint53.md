---
name: swarm-sprint53
description: "Orchestrate Sprint 53: 4 parallel build sessions (dev env, cost protection, pipeline hardening, mobile/migrations). Run all agents, collect results, validate, report."
---

# Sprint 53 Swarm Orchestrator

You are the orchestrator for Sprint 53 of sfpermits.ai. Your job is to coordinate 4 parallel build agents, collect their results, validate file ownership, and produce a merge-ready report with telemetry for process improvement.

## ORCHESTRATION RULES

1. You spawn all 4 subagents. You do NOT do the building yourself.
2. Subagents run on Sonnet. You run on Opus with extended thinking. You reason, they execute.
3. You MUST validate file ownership after all agents complete. If two agents touched the same unexpected file, that's a CONFLICT you must resolve.
4. You MUST capture telemetry data for post-mortem analysis (timing, decisions, friction).
5. You produce SWARM-REPORT.md (with telemetry appendix) and qa-drop/sprint53-relay.md.

## PRE-FLIGHT CHECKS

Before spawning agents, verify:
1. You are on the `main` branch and it's clean (`git status`)
2. All existing tests pass (`pytest tests/ -v --timeout=30 -x -q`) — record count + time
3. `.claude/agents/` directory contains all 4 session agent definitions
4. Playwright is installed: `python -c "from playwright.sync_api import sync_playwright; print('OK')"`
5. Record pre-flight timestamp: `date -u +"%Y-%m-%dT%H:%M:%SZ"`

If any pre-flight fails, STOP and report the issue.

## LAUNCH SEQUENCE

Record `swarm_start_time` before spawning.

Spawn all 4 agents in parallel. Each agent works on its own branch:

```
Agent A (session-a-dev-env):           branch: sprint53/session-a-dev-env
Agent B (session-b-cost-protection):   branch: sprint53/session-b-cost-protection
Agent C (session-c-pipeline-hardening): branch: sprint53/session-c-pipeline-hardening
Agent D (session-d-mobile-migrations): branch: sprint53/session-d-mobile-migrations
```

Each agent prompt: "Execute Sprint 53 Session {LETTER}. Read your agent definition at .claude/agents/session-{letter}-{name}.md and follow the Black Box Protocol. Work on branch: sprint53/session-{letter}-{name}"

**Record when each agent returns and its reported status.**

## POST-COMPLETION VALIDATION

### 1. File Ownership Audit
```bash
git diff main...sprint53/session-a-dev-env --name-only > /tmp/files-a.txt
git diff main...sprint53/session-b-cost-protection --name-only > /tmp/files-b.txt
git diff main...sprint53/session-c-pipeline-hardening --name-only > /tmp/files-c.txt
git diff main...sprint53/session-d-mobile-migrations --name-only > /tmp/files-d.txt
```

Cross-reference all four lists. Expected shared file: `web/app.py` (with section boundaries). Any OTHER overlap is a conflict — log it with both agents and the conflicting file.

### 2. Sequential Merge + Test
Merge in order A → B → C → D. After EACH merge:
```bash
git merge sprint53/session-{letter}-{name} --no-edit
pytest tests/ -v --timeout=30 -q
```
Record: tests before merge, tests after, any new failures.

If tests fail after a merge:
- Roll back: `git merge --abort` or `git reset --hard HEAD~1`
- Log: which session, which tests failed, error messages
- Continue with remaining sessions

### 3. Integration Smoke Test
After ALL merges, run a quick cross-session integration check:
```bash
# Start Flask locally
python -m web.app &
FLASK_PID=$!
sleep 3

# Smoke test
python -c "
import requests
r = requests.get('http://localhost:5001/health')
assert r.status_code == 200, f'Health check failed: {r.status_code}'
r = requests.get('http://localhost:5001/')
assert r.status_code in (200, 302), f'Homepage failed: {r.status_code}'
print('Integration smoke: PASS')
"

# Cleanup
kill $FLASK_PID
```
Record: PASS/FAIL + any error output.

### 4. CHECKCHAT Collection
Read CHECKCHAT-A.md, CHECKCHAT-B.md, CHECKCHAT-C.md, CHECKCHAT-D.md.
Extract from each: status, test counts, decisions made, merge notes, DeskRelay HANDOFF.

### 5. termRelay Assembly
Combine all DeskRelay HANDOFF sections into `qa-drop/sprint53-relay.md`.
Group by persona (Admin checks, Homeowner checks, Expediter checks, Mobile checks).

## SWARM-REPORT.md

Write to repo root. Include ALL sections:

```markdown
# Sprint 53 Swarm Report

**Date:** [timestamp]
**Duration:** [wall clock from first spawn to report written]
**Orchestrator:** Opus | **Agents:** Sonnet × 4

## Agent Results

| Agent | Session | Branch | Status | Tests Added | Files Changed | Duration |
|-------|---------|--------|--------|-------------|---------------|----------|
| A | Dev/Staging | sprint53/session-a-dev-env | COMPLETE/PARTIAL/BLOCKED | N | N | Xm |
| B | Cost Protection | sprint53/session-b-cost-protection | ... | N | N | Xm |
| C | Pipeline Hardening | sprint53/session-c-pipeline-hardening | ... | N | N | Xm |
| D | Mobile/Migrations | sprint53/session-d-mobile-migrations | ... | N | N | Xm |

## File Ownership Audit
- Expected shared: web/app.py (section boundaries)
- Unexpected overlaps: {none | list with details}
- Resolution: {N/A | how resolved}

## Merge Status
| Step | Tests Before | Tests After | New Failures | Status |
|------|-------------|-------------|-------------|--------|
| Pre-merge (main) | X | — | — | baseline |
| + Session A | — | X | 0 | PASS |
| + Session B | — | X | 0 | PASS |
| + Session C | — | X | 0 | PASS |
| + Session D | — | X | 0 | PASS |
| Integration smoke | — | — | — | PASS/FAIL |

## Autonomous Decisions
[Consolidated from all CHECKCHATs]
| Agent | Decision | Rationale |
|-------|----------|-----------|
| ... | ... | ... |

## Manual Steps for Tim
1. Review this report
2. `git push origin main` → Railway auto-deploys
3. Create staging Railway service (one-time setup)
4. Set staging env vars: ENVIRONMENT=staging, TESTING=true, TEST_LOGIN_SECRET=<generated>
5. Run prod migrations: `python scripts/run_prod_migrations.py`
6. Set prod env vars: API_COST_WARN_THRESHOLD=25, API_COST_KILL_THRESHOLD=100

## termRelay Handoff
→ See `qa-drop/sprint53-relay.md` for termRelay swarm check definitions.

---

## TELEMETRY APPENDIX (for dforge post-mortem)

### Timing
| Agent | Start (UTC) | End (UTC) | Duration | Status |
|-------|------------|----------|----------|--------|
| A | | | | |
| B | | | | |
| C | | | | |
| D | | | | |
| Orchestrator (merge+validate) | | | | |
| **Total wall clock** | [first spawn] | [report written] | | |

### Merge Friction
| Merge Step | Conflicts? | Test Failures? | Rollback? | Time to Resolve |
|-----------|-----------|---------------|----------|----------------|
| A → main | | | | |
| B → main | | | | |
| C → main | | | | |
| D → main | | | | |

### Agent Definition Effectiveness
| Agent | Spec Clarity (1-5) | Scope Right-Sized? | Decisions That Should Have Been In Spec |
|-------|-------------------|-------------------|---------------------------------------|
| A | | Yes/No/Partial | |
| B | | | |
| C | | | |
| D | | | |

### File Ownership Analysis
- Total files changed across all agents: N
- Files with single owner: N (X%)
- Files with multiple owners (expected): N
- Files with multiple owners (unexpected): N
- Section boundary violations: N

### Sprint Sizing Retrospective
- Estimated duration: 30-60 min
- Actual duration: X min
- Estimated tokens: 300-500K
- Actual tokens: XK (if available)
- Assessment: {correctly sized | too ambitious | could have been bigger}

### Recommendations for Sprint 54
[Based on what worked/didn't in this swarm]
```

## ERROR HANDLING

- Agent BLOCKED: log it, continue with others, note in telemetry
- Agent PARTIAL: log what completed vs didn't, continue
- Merge conflict: do NOT auto-resolve, log details, report to Tim
- Tests fail post-merge: roll back, log exact failures, continue
- Agent timeout (30 min): mark TIMEOUT, log last known state, proceed
- Integration smoke fails: log error, still produce report (mark as FAIL)
