# Sprint 54 Post-Mortem

**Sprint:** 54 (54A + 54B + 54C)
**Date:** 2026-02-24
**Status:** All 3 sub-sprints COMPLETE, merged, deployed

## What Went Well

- **Parallel agent model works.** Sprint 54A ran 4 build agents in parallel; 54C ran cleanly with proper QA artifacts.
- **Test suite growing.** 1,840 tests collected at HEAD, up from ~1,705 pre-sprint. Zero regressions on main.
- **54B enforcement hooks address the self-certification problem** from 54A (agent skipped Playwright, rushed CHECKCHAT).
- **Data ingest expansion** landed 1.15M new rows across 4 datasets with OOM/timeout fixes.

## What Went Wrong

### P0: CRON_SECRET Auth Failure (cost: ~45 min per sprint, every sprint)

**Symptom:** Every sprint that touches cron endpoints loses 30-60 minutes to CRON_SECRET 403 errors. `railway variable list` shows a value, but curling with that value gets 403. GitHub Actions succeeds.

**Root cause:** Missing `.strip()` in `_check_api_auth()`. Railway env vars can contain trailing whitespace. Python's `os.environ.get()` returns it verbatim. The comparison `"Bearer mysecret" != "Bearer mysecret\n"` fails silently — no logging, just `abort(403)`.

GitHub Actions works because GitHub Secrets auto-trim whitespace at storage time.

**Why it took so long to find:** Zero diagnostic logging on auth failure. Every sprint, the workaround was creating a fresh `MIGRATION_KEY` env var (entered cleanly) instead of investigating the comparison logic.

**Fix applied this session:** Amendment A below.

### P1: Agent Self-Certification (Sprint 54A)

**Symptom:** Sprint 54A's QA agent skipped Playwright entirely and rushed CHECKCHAT without visual evidence.

**Root cause:** No enforcement mechanism. CLAUDE.md says "use Playwright" but nothing stops an agent from substituting curl/pytest and calling it done.

**Fix applied in 54B:** Enforcement hooks (stop-checkchat.sh, block-playwright.sh, detect-descope.sh, plan-accountability.sh).

**Residual gaps:** Hooks enforce artifact *existence* but not *quality*. Screenshot check accepts any PNG (stale or trivial). Scenario check uses `git diff` which breaks if scenarios were committed before CHECKCHAT. One-retry bypass means the hook gets exactly one shot.

### P2: Worktree Test Count Confusion

**Symptom:** CHANGELOG shows 1,793 → 1,757 → 1,696 tests across sub-sprints, appearing to be a regression.

**Root cause:** Worktree branches fork before the previous sprint's tests are merged to main. Sprint 54C's worktree didn't have 54A's 88 new tests. After merge, all tests are present.

**Impact:** False alarm, but wasted investigation time. Could erode trust in test metrics.

### P3: Inline Auth Duplication

**Symptom:** 5 endpoints had copy-pasted auth logic instead of calling `_check_api_auth()`. Any fix to the shared function missed 4 endpoints.

**Root cause:** Organic growth — early endpoints were written before the shared function existed, never refactored.

**Fix applied this session:** Amendment B below.

---

## Amendments

### Amendment A: CRON_SECRET `.strip()` + Diagnostic Logging

**Status: APPLIED**

`_check_api_auth()` now strips whitespace from both the Authorization header and the CRON_SECRET env var. On failure, logs token/expected lengths and the request path (not values, for security).

```python
def _check_api_auth():
    token = request.headers.get("Authorization", "").strip()
    secret = os.environ.get("CRON_SECRET", "").strip()
    expected = f"Bearer {secret}"
    if not secret or token != expected:
        logging.warning(
            "API auth failed: token_len=%d expected_len=%d path=%s",
            len(token), len(expected), request.path,
        )
        abort(403)
```

### Amendment B: Consolidate Inline Auth

**Status: APPLIED**

Replaced 4 inline auth blocks (at `/cron/nightly`, `/cron/send-briefs`, `/cron/rag-ingest`) with calls to `_check_api_auth()`. The `/cron/pipeline-health` POST block kept inline because it has admin-session fallback logic, but now uses `.strip()`.

### Amendment C: CHANGELOG Worktree Annotation

**Status: RECOMMENDATION**

When a sprint runs in a worktree that forked before the previous sprint merged, note this in CHANGELOG:

> `pytest: 1,696 passed (worktree, pre-merge with 54A); full suite after merge: 1,840`

This prevents false regression alarms.

### Amendment D: Enforcement Hook Improvements

**Status: RECOMMENDATIONS FOR NEXT SPRINT**

1. **Screenshot freshness check:** Verify PNGs are <1 hour old or filename contains current sprint ID.
2. **Scenario content check:** Instead of `git diff`, grep for a scenario with `Source:` matching the current feature.
3. **Hook audit log:** Append every invocation to `.claude/hooks/audit.log` (hook name, timestamp, result, reason).
4. **Secrets detection hook:** Add a `PostToolUse:Write` hook that greps for high-entropy hex strings or known env var names in committed files.

### Amendment E: CC Session Memory for CRON_SECRET

**Status: APPLIED (see memory update)**

Updated CC memory files so future sessions know:
- `.strip()` is already applied — CRON_SECRET should now work from local curl
- If auth still fails, check Railway logs for the `API auth failed: token_len=X expected_len=Y` diagnostic line
- No need for MIGRATION_KEY workaround anymore

---

## Metrics

| Sub-Sprint | Tests at Close | QA Checks | Pass | Fail | Skip |
|---|---|---|---|---|---|
| 54A | 1,793 (worktree) | 10 | 9 | 0 | 1 |
| 54B | 1,757 (worktree) | 22 | 22 | 0 | 0 |
| 54C | 1,696 (worktree) | 9 | 9 | 0 | 0 |
| **HEAD (merged)** | **1,840** | — | — | — | — |

## Time Lost to Known Issues

| Issue | Estimated Time Lost | Sprints Affected |
|---|---|---|
| CRON_SECRET mismatch | ~2.5 hours total | 53B, 54A, 54C |
| Agent self-certification | ~1 hour (manual re-QA) | 54A |
| Test count investigation | ~30 min | 54 post-mortem |
| **Total** | **~4 hours** | |

## Cleanup Remaining

- [ ] Prune 16 stale worktree branches
- [ ] Move `qa-results/sprint54-results.md` and `sprint54c-staging-results.md` to `done/`
- [ ] Update Chief STATUS.md to reflect 54C completion
