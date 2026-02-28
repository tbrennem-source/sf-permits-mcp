# QS11 Terminal 0: Orchestrator

**Sprint:** QS11 — Intelligence-Forward Beta
**Spec:** `chief-brain-state/specs/qs11-intelligence-forward-beta.md` (approved 2026-02-28, 5 amendments)
**Total agents:** 16 across 4 terminals (4×4)
**Status:** APPROVED

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Verify clean state
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# Expect: 4,069+ passed, 0 failed

# Record sprint start commit
SPRINT_START=$(git rev-parse HEAD)
echo "Sprint start: $SPRINT_START"

# Verify prod health
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Verify staging health
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool | head -5

# Stale worktree check
git worktree list
git worktree prune
git branch --merged main | grep -E "worktree|claude/" | xargs git branch -d 2>/dev/null
git branch --no-merged main | grep -E "worktree|claude/"  # report, don't delete

# Design lint baseline (UI sprint)
python scripts/design_lint.py --quiet 2>&1 | tail -5
# Record baseline score for comparison after merge

# Verify QS10 prerequisites exist
ls web/templates/tools/station_predictor.html web/templates/tools/stuck_permit.html \
   web/templates/tools/what_if.html web/templates/tools/cost_of_delay.html
# All 4 should exist

python -c "from web.tier_gate import requires_tier, has_tier; print('tier_gate OK')"
```

---

## Launch Sequence

| Terminal | Prompt File | Theme | Agents | Model | Est. Time |
|---|---|---|---|---|---|
| T1 | `sprint-prompts/qs11-t1-landing-showcase.md` | Landing Intelligence + MCP Demo | 4 | Sonnet (1C=Opus) | 30-40 min |
| T2 | `sprint-prompts/qs11-t2-migration-blitz.md` | Page Migration Blitz | 4 | Sonnet | 20-30 min |
| T3 | `sprint-prompts/qs11-t3-tool-polish.md` | Tool Page Polish + New Pages | 4 | Sonnet | 25-35 min |
| T4 | `sprint-prompts/qs11-t4-tier-gating.md` | Tier Gating + Onboarding | 4 | Sonnet | 20-30 min |

Paste each prompt into a fresh CC terminal. All 4 run in parallel.

---

## Monitoring

- All agents run FOREGROUND — watch for failures
- Expected: T2 finishes first (~20 min), T4 second, T1/T3 longest
- T1 has sequential dependency: 1A → 1B+1C → 1D
- T3 has sequential dependency: 3A+3B+3C → 3D
- If any terminal fails completely, take over manually using the agent prompts

---

## Merge Order (STRICT)

Cross-terminal merge order enforces dependencies:

1. **T2 first** — page migrations establish Obsidian baseline
2. **T1 second** — landing showcase + MCP demo (independent of T2)
3. **T3 third** — tool page polish builds on T2 migrated templates
4. **T4 fourth** — tier gating decorates routes from T3

### MERGE 1 — T2 (page migrations, lightest)

```bash
git pull origin main
# T2's terminal pushed to main. Verify:
git log --oneline -5
# Should see T2's merge commit

# Quick sanity check
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 2 — T1 (landing showcase + MCP demo)

```bash
git pull origin main
# T1's terminal pushed to main. Verify:
git log --oneline -5

# Verify showcase data exists
ls web/static/data/showcase_data.json
python -c "import json; d=json.load(open('web/static/data/showcase_data.json')); print(f'{len(d)} showcases')"

# Quick sanity
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 3 — T3 (tool page polish + share mechanic)

```bash
git pull origin main
git log --oneline -5

# Verify new routes
grep -n "entity-network\|revision-risk\|/api/share" web/routes_search.py web/routes_api.py

# Quick sanity
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 4 — T4 (tier gating + onboarding)

```bash
git pull origin main
git log --oneline -5

# Verify tier gate enhancement
python -c "from web.tier_gate import requires_tier; print('tier_gate OK')"

# Full test suite (final run)
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
```

### POST-MERGE: Apply @requires_tier to existing tool routes

T3 owns routes_search.py and adds `requires_tier` import + decorators to new routes.
T0 verifies the 4 existing tool routes also have tier-appropriate handling.

Check: do existing tool routes still use manual `if not g.user: redirect` pattern?
If so, they work as-is for beta (login-required but not tier-gated).
Tool pages show demo data for anonymous, personal data for logged-in — no hard tier gate needed.

### POST-MERGE: Design lint

```bash
python scripts/design_lint.py --changed --quiet
# Compare against pre-sprint baseline
# Target: improved or maintained score on all changed templates
```

### POST-MERGE: Prod gate

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
- `git pull origin main`
- Read all `qa-drop/qs11-t*-session.md` files
- Tally: total agents (expect 16), pass/fail, blocked items

### Step 2: VERIFY
- Full test suite (already ran per merge)
- Design lint: `python scripts/design_lint.py --changed --quiet`
- Prod gate: (already ran)
- Verify showcase_data.json loads correctly

### Step 3: VISUAL QA
- Deploy staging, verify landing page showcases render
- Verify MCP demo animation plays
- Check 375px viewport for all new content
- Score pages 1-5. Pages ≤ 2.0 → DeskRelay escalation

### Step 4: CONSOLIDATE
- Concatenate scenario files → scenarios-pending-review.md
- Concatenate changelog files → CHANGELOG.md
- Commit consolidation

### Step 5: DOCUMENT + CHIEF TASK DRAIN
- Update STATUS.md + Chief
- `chief_get_brain_state` → complete tasks #367, #319 if verified
- Create new tasks for any BLOCKED items
- Flag stale tasks

### Step 6: HARVEST
- Review terminal artifacts for dforge-worthy patterns
- Landing showcase architecture, MCP demo animation patterns

### Step 7: SHIP + PROMOTE
- Already pushed + promoted in merge ceremony

### Step 8: CLEAN
```bash
git worktree list
git worktree prune
git branch --merged main | grep -E "worktree|claude/" | xargs git branch -d 2>/dev/null
git branch --no-merged main | grep -E "worktree|claude/"
du -sh .claude/worktrees/ 2>/dev/null || echo "Clean"
```

---

## Post-Sprint Diff Audit

```bash
git diff --stat $SPRINT_START..HEAD
# Verify: no unexpected files, all expected files present
# Expected ~30-50 new/modified files across templates, JS, CSS, routes, tests
```

---

## File Ownership Matrix (Cross-Terminal)

| File | T1 | T2 | T3 | T4 |
|---|---|---|---|---|
| web/templates/landing.html | 1D | — | — | — |
| web/routes_public.py | 1D | — | — | — |
| web/routes_search.py | — | — | 3C (append 2 routes at EOF) | — |
| web/routes_api.py | — | — | 3D (append share endpoint) | — |
| web/routes_auth.py | — | — | — | 4C |
| web/tier_gate.py | — | — | — | 4A |
| web/templates/tools/*.html | — | 2B/2D (migrate) | 3A/3B (polish) | — |
| web/templates/components/* | 1B/1C (create) | — | 3D (create share) | 4B (create overlay) |
| web/templates/onboarding_step*.html | — | — | — | 4C |
| scripts/generate_showcase_data.py | 1A | — | — | — |

**Conflicts requiring merge order:**
1. tools/*.html: T2 migrates → T3 polishes (T2 merges first)
2. routes_search.py: Only T3 touches it (no conflict)

---

## Failure Recovery

| Scenario | Action |
|---|---|
| Terminal fails completely | Take over manually using agent prompts from the terminal's prompt file |
| Merge conflict on tools/*.html | T2 merges first, T3 second — T3's polish overrides T2's migration |
| showcase_data.json missing | Run `python scripts/generate_showcase_data.py` manually |
| MCP demo doesn't animate | Check mcp-demo.js, may need Opus debug session |
| Design lint regression | Fix before pushing, but don't block staging |
| Tests regress after merge | Bisect: revert last terminal's merge, re-test |
