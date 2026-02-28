# QS12 Terminal 0: Orchestrator

**Sprint:** QS12 — Demo-Ready: Visual Intelligence
**Spec:** `chief-brain-state/specs/qs12-demo-ready-sprint.md` (v4, merged c.ai + CC)
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
# Expect: 4,433+ passed, 0 failed

# Record sprint start commit
SPRINT_START=$(git rev-parse HEAD)
echo "Sprint start: $SPRINT_START"

# Verify prod health
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5

# Stale worktree check
git worktree list  # should show only main
git worktree prune
git branch --merged main | grep -E "worktree|claude/" | xargs git branch -d 2>/dev/null

# Design lint baseline
source .venv/bin/activate
python scripts/design_lint.py --quiet 2>&1 | tail -5

# Verify QS11 deliverables exist
ls web/templates/components/showcase_gantt.html web/templates/components/showcase_stuck.html
ls web/static/data/showcase_data.json
ls web/static/js/share.js web/static/css/share.css
python -c "from web.tier_gate import requires_tier; print('tier_gate OK')"
```

---

## Launch Sequence

| Terminal | Prompt File | Theme | Agents |
|---|---|---|---|
| T1 | `sprint-prompts/qs12-t1-showcase-redesign.md` | Landing Showcase Visual Redesign | 4 |
| T2 | `sprint-prompts/qs12-t2-vision-fixes.md` | Vision-Guided Page UX Fixes | 4 |
| T3 | `sprint-prompts/qs12-t3-amy-features.md` | Amy's "I Need This" + UX Fixes | 4 |
| T4 | `sprint-prompts/qs12-t4-mobile-demo-notify.md` | Mobile + Demo Script + Notifications | 4 |

Paste each prompt into a fresh CC terminal. All 4 run in parallel.

---

## Monitoring

- All agents FOREGROUND
- T4 should finish first (~20 min)
- T1 has sequential: 1A → 1B+1C → 1D
- T2, T3, T4 all parallel internally
- **landing.html risk:** T1, T3, T4 all touch it. Merge order is strict: T1 → T3 → T4

---

## Merge Order (STRICT)

**landing.html is the highest-risk file — 3 terminals touch it.**

### MERGE 1 — T1 (showcase redesign — owns the big restructure)
```bash
git pull origin main
git log --oneline -5
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 2 — T2 (vision fixes — independent pages, no landing.html)
```bash
git pull origin main
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 3 — T3 (Amy features — touches landing badge/arrow/links + search templates + routes)
```bash
git pull origin main
# May need conflict resolution on landing.html (T1 restructured, T3 changes badge/arrow)
# Also search result templates (T2 vision fixes, T3 adds intelligence signals)
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### MERGE 4 — T4 (mobile + demo + notify — touches landing mobile nav + stats)
```bash
git pull origin main
# May need conflict resolution on landing.html (T1+T3 already merged)
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
```

### POST-MERGE: Full verification
```bash
# Full test suite
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

# Design lint
python scripts/design_lint.py --changed --quiet

# Prod gate
python scripts/prod_gate.py --quiet

# If PROMOTE:
git checkout prod && git merge main && git push origin prod && git checkout main
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool | head -5
```

---

## CHECKQUAD-T0 (8 steps)

### Step 1: COLLECT
Read all `qa-drop/qs12-t*-session.md`. Tally agents, pass/fail, blocked.

### Step 2: VERIFY
Full test suite + design lint + prod gate (already ran per merge).

### Step 3: VISUAL QA
Run persona-amy and qa-mobile against staging post-merge.
Score showcase cards — are they visual-first? Does Amy see intelligence on search results?

### Step 4: CONSOLIDATE
Concatenate scenario + changelog files. Commit.

### Step 5: DOCUMENT + CHIEF TASK DRAIN
Update STATUS.md + Chief. Complete tasks #402-#407 if verified.

### Step 6: HARVEST
Review session artifacts for dforge lessons. Key patterns: Vision-guided fixes, notification hooks.

### Step 7: SHIP + PROMOTE
Push + prod promotion (in merge ceremony above).

### Step 8: CLEAN
```bash
git worktree list
git worktree prune
git branch --merged main | grep -E "worktree|claude/" | xargs git branch -d 2>/dev/null
du -sh .claude/worktrees/ 2>/dev/null || echo "Clean"
```

---

## Failure Recovery

| Scenario | Action |
|---|---|
| landing.html merge conflict | T1 owns structure. T3/T4 changes are additive (badge text, nav, stats). Take T1 structure, re-apply T3/T4 edits. |
| Vision scoring unavailable | Agents fall back to manual inspection + design lint |
| MCP demo unfixable | Agent 1D uses static mockup fallback (principle 6) |
| Tool page auth removal breaks tests | Check for tests that assert redirect behavior — update them |
