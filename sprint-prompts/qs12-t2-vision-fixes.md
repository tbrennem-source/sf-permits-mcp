# QS12 T2: Vision-Guided Page UX Fixes

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Spawn ALL 4 agents in PARALLEL using the Agent tool (subagent_type="general-purpose", model="sonnet", isolation="worktree"). Do NOT summarize — execute now.

**Sprint:** QS12 — Demo-Ready: Visual Intelligence
**Terminal:** T2 — Vision-Guided Page UX Fixes
**Agents:** 4 (all parallel)
**Theme:** Screenshot → score → fix. NOT a migration sprint — templates are already 5/5 lint.

---

## CRITICAL: This is NOT a migration sprint

QS11 T2 already migrated all these templates to 5/5 design lint. Do NOT re-migrate.
Instead: screenshot each page, evaluate visual quality, fix specific UX issues.

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules

1. **Worktree**: ALREADY in worktree. No checkout main. No merge.
2. **Early commit**: Within 10 minutes.
3. **NEVER merge to main.** T2 orchestrator handles merges.
4. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
5. **Scenario file**: `scenarios-t2-sprint95.md`
6. **Changelog file**: `CHANGELOG-t2-sprint95.md`
7. **Design system**: Read `docs/DESIGN_TOKENS.md`.

---

## Agent 2A Prompt — Search Results Pages

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Fix UX issues in search result pages

These pages are already migrated to Obsidian (5/5 lint). Your job is to fix VISUAL quality
issues that lint doesn't catch.

### Pages
- web/templates/search_results_public.html
- web/templates/results.html
- web/templates/search_results.html

### Known Issues (from persona-amy audit)
1. ISO timestamps (2025-04-28T12:53:40.000) → formatted dates (Apr 28, 2025)
2. Mixed case permit types: "otc alterations permit" vs "Electrical Permit" → title case all
3. Cost field shows "—" for electrical/plumbing — add tooltip or note explaining why
4. Are results scannable for Amy's morning triage of 20 properties? If not, improve density/hierarchy.

### Process
1. Read each template
2. Fix the known issues above
3. Look for any other visual quality problems (text hierarchy, spacing, readability)
4. Run design lint to confirm still 5/5
5. Write tests verifying the fixes (date formatting, case normalization)

### FILES YOU OWN
- MODIFY: web/templates/search_results_public.html
- MODIFY: web/templates/results.html
- MODIFY: web/templates/search_results.html
- CREATE: tests/test_search_ux_fixes.py

### FILES YOU MUST NOT TOUCH
- landing.html, routes_*.py, showcase_*.html, tool pages
```

---

## Agent 2B Prompt — Tool Pages (Station Predictor + Stuck Permit)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Polish station predictor and stuck permit tool pages

### Pages
- web/templates/tools/station_predictor.html
- web/templates/tools/stuck_permit.html

### Focus Areas
1. Does ?permit=202509155257 pre-fill the input and auto-run? Test it.
2. Loading state: is there a skeleton screen or spinner while HTMX fetches?
3. Empty state: does "Enter a permit number" guide the user? Are demo permits suggested?
4. Is the Gantt interactive (click to expand station details)?
5. Is the intervention playbook formatted, not raw JSON?
6. Are reviewer names and phone numbers prominent?

### Process
1. Read each template + associated JS
2. Fix any broken pre-fill, loading state, empty state issues
3. Improve visual hierarchy of results (severity badges, playbook formatting)
4. Write tests

### FILES YOU OWN
- MODIFY: web/templates/tools/station_predictor.html
- MODIFY: web/templates/tools/stuck_permit.html
- MODIFY: web/static/js/gantt-interactive.js (if needed)
- CREATE: tests/test_tool_ux_station_stuck.py
```

---

## Agent 2C Prompt — Tool Pages (What-If + Delay + Entity + Risk)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Polish what-if, cost-of-delay, entity-network, and revision-risk tool pages

### Pages
- web/templates/tools/what_if.html
- web/templates/tools/cost_of_delay.html
- web/templates/tools/entity_network.html
- web/templates/tools/revision_risk.html

### Focus Areas
1. Does ?demo= pre-fill work on what-if and cost-of-delay?
2. Does ?address= work on entity-network?
3. Loading states present?
4. Empty states guide the user with demo suggestions?
5. Entity graph renders (D3)?
6. Risk gauge renders (SVG)?
7. Comparison table in what-if has red/green indicators?

### Process
1. Read each template
2. Fix broken pre-fill, loading, empty states
3. Write tests

### FILES YOU OWN
- MODIFY: web/templates/tools/what_if.html
- MODIFY: web/templates/tools/cost_of_delay.html
- MODIFY: web/templates/tools/entity_network.html
- MODIFY: web/templates/tools/revision_risk.html
- CREATE: tests/test_tool_ux_remaining.py
```

---

## Agent 2D Prompt — Auth + Supporting Pages

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Polish auth and supporting pages

### Pages
- web/templates/auth_login.html
- web/templates/beta_request.html
- web/templates/demo.html
- web/templates/consultants.html

### Known Issues
1. /demo overflows 300px at 375px — .callout elements are display: inline-block with no max-width.
   Fix: add to mobile media query: `.callout { display: block; max-width: 100%; box-sizing: border-box; }`
2. Does the login page feel trustworthy? Professional?
3. Does /demo tell a coherent story about what sfpermits.ai does?

### Process
1. Read each template
2. Fix /demo overflow
3. Check visual quality of auth pages
4. Write tests

### FILES YOU OWN
- MODIFY: web/templates/auth_login.html
- MODIFY: web/templates/beta_request.html
- MODIFY: web/templates/demo.html
- MODIFY: web/templates/consultants.html
- CREATE: tests/test_auth_ux_fixes.py
```

---

## Post-Agent Merge + CHECKQUAD

Standard: escape CWD → merge all 4 (parallel, no conflicts) → test → push → write session artifact → signal done.
