# QS10 Terminal 0: Orchestrator

**Sprint:** QS10 — Phase A Visual QA Foundation + Intelligence UI + Beta Onboarding
**Spec:** `chief-brain-state/specs/qs10-v3-phase-a-visual-qa-foundation.md` (v3.1)
**Chief Tasks:** #378 (T1), #385 (T2), #360 (T3), #330 (T4)
**Total agents:** 11 across 4 terminals

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Verify clean state
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# Expect: 3,656+ passed, 0 failed

# Record sprint start commit
git log --oneline -1  # save this hash for post-merge diff audit

# Verify prod health
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Stale worktree check
git worktree list  # should show only main
git worktree prune
git branch | grep worktree  # should be empty

# Verify existing scripts (T1 depends on these)
wc -l scripts/visual_qa.py scripts/design_lint.py scripts/vision_score.py
# Expect: ~1023, ~404, ~106 lines respectively
```

---

## Launch Sequence

| Terminal | Prompt File | Theme | Agents |
|---|---|---|---|
| T1 | `sprint-prompts/qs10-t1-qa-pipeline.md` | Visual QA Phase A | 3 |
| T2 | `sprint-prompts/qs10-t2-admin-tools.md` | Admin QA Tools | 2 |
| T3 | `sprint-prompts/qs10-t3-intelligence-ui.md` | Intelligence Tool Pages | 4 |
| T4 | `sprint-prompts/qs10-t4-beta-onboarding.md` | Beta Onboarding + Tier Gate | 2 |

Paste each prompt into a fresh CC terminal. All 4 run in parallel.

---

## Monitoring

- All agents run FOREGROUND — watch for failures
- Expected timeline: 25-35 min for longest terminal (T1 or T3)
- T2 should finish first (~15-20 min)
- If any terminal fails completely, take over its work manually

---

## Merge Ceremony

### MERGE 1 — T2 (admin tools, lightest)
```bash
git pull origin main
git merge t2/sprint-87 --no-ff
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
git push origin main
```
Note: impersonation dropdown and Accept/Reject log now available.

### MERGE 2 — T1 (QA scripts)
```bash
git merge t1/sprint-86 --no-ff
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# Capture initial structural baselines
python scripts/visual_qa.py --structural --baseline
# Run baseline token lint
python scripts/design_lint.py --live
git push origin main
```
Note: Layer 1 now available as merge gate for T3 and T4.

### MERGE 3 — T3 (intelligence tool pages)
```bash
git merge t3/sprint-88 --no-ff
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# LAYER 1 PRE-PUSH GATE (first real use!)
python scripts/qa_gate.py --changed-only
# If FAIL → fix before push
git push origin main
# LAYER 3 POST-PUSH (advisory, non-blocking)
python scripts/vision_score.py --changed
```

### MERGE 4 — T4 (beta onboarding + tier gate)
```bash
git merge t4/sprint-89 --no-ff
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
python scripts/qa_gate.py --changed-only
# If FAIL → fix before push
git push origin main
python scripts/vision_score.py --changed
```

### MERGE 5 — Prod Promotion
```bash
python scripts/prod_gate.py --quiet
# If PROMOTE:
git checkout prod && git merge main && git push origin prod && git checkout main
# Verify:
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5
```

---

## CHECKQUAD-T0 (8 steps)

### Step 1: COLLECT
- Read all `qa-drop/qs10-t*-session.md` files
- Tally: total agents, pass/fail, blocked items

### Step 2: VERIFY
- Full test suite (already ran per merge)
- Design lint: `python scripts/design_lint.py --live`
- Prod gate: (already ran)

### Step 3: VISUAL QA
- Review any pending-reviews.json entries via admin impersonation
- Score pages, Accept/Reject with notes

### Step 4: CONSOLIDATE
- Concatenate scenario files → scenarios-pending-review.md
- Concatenate changelog files → CHANGELOG.md
- Commit consolidation

### Step 5: DOCUMENT + CHIEF TASK DRAIN
- Update STATUS.md + Chief
- `chief_get_brain_state` → complete tasks #378, #385, #360, #330 if verified
- Flag any stale tasks

### Step 6: HARVEST
- Review terminal artifacts for dforge-worthy patterns

### Step 7: SHIP + PROMOTE
- Already pushed + promoted in merge ceremony

### Step 8: CLEAN
```bash
git worktree list
git worktree prune
git branch --merged main | grep worktree | xargs git branch -d 2>/dev/null
git branch --no-merged main | grep worktree
du -sh .claude/worktrees/ 2>/dev/null || echo "Clean"
```

---

## Failure Recovery

| Scenario | Action |
|---|---|
| Terminal fails completely | Take over manually, run tasks from prompt |
| Merge conflict | T3/T4 on routes_search.py: merge T3 first, T4 second |
| Layer 1 gate fails at T3/T4 merge | Fix the regression before pushing |
| Vision score < 3.0 | Write to pending-reviews.json, Tim reviews via admin widget |
| Tests regress after merge | Bisect: revert last merge, re-test |

---

## Post-Sprint

- Report to Chief: session note with agent counts, pass/fail, merged terminals
- Verify staging and prod health
- Open pending-reviews.json in admin widget — first Accept/Reject decisions (training data!)
