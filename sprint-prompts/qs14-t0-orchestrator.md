> **EXECUTE IMMEDIATELY.** You are T0 orchestrator for QS14. Do NOT summarize or ask for confirmation — execute the pre-flight, write the 4 terminal prompts, and present them for launch.

# QS14 — T0 Orchestrator

## Sprint Goal
**Launchable landing page + intelligence wiring. Exit gate: HONEYPOT_MODE=1 on prod.**

## Your Role
You are T0. You NEVER enter a worktree. You operate from the main repo root. You:
1. Run pre-flight checks
2. Write 4 terminal prompts to `sprint-prompts/qs14-t1-*.md` through `qs14-t4-*.md`
3. Present prompts for Tim to paste into 4 CC terminals
4. After all terminals complete: merge in order T3 → T1 → T2 → T4, run tests ONCE, push, promote to prod
5. Set HONEYPOT_MODE=1 on prod Railway service

## Pre-Flight Checklist

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git worktree list  # prune stale worktrees
git worktree prune
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q --tb=line 2>&1 | tail -5  # baseline count
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool  # prod health
```

## Read These First
1. `chief_read_file("specs/qs14-quad-sprint-intelligence-surfaces-site-upgrade-beta-readiness.md")` — the approved spec
2. `CLAUDE.md` — project instructions
3. Memory file at `/Users/timbrenneman/.claude/projects/-Users-timbrenneman-AIprojects-sf-permits-mcp/memory/MEMORY.md`

## Persona Agent Pre-Flight (run in parallel, findings INFORM prompts — do NOT gate)

Spawn these 4 agents in parallel:
- `persona-new-visitor` — landing page first impression
- `persona-amy` — expediter workflow (brief, search, property report)
- `qa-ux-designer` — layout/readability/nav scoring
- `qa-mobile` — 375px + 768px breakpoint testing

Collect findings into `qa-results/qs14-preflight-audit.md`. Embed the worst findings as fix targets in T4-D's prompt.

## Terminal Prompts to Write

After pre-flight, write these 4 files. Each prompt must be self-contained (agent preamble, read list, tasks, interface contracts, test command, CHECKQUAD close). Include DuckDB/Postgres gotchas in every prompt.

### `sprint-prompts/qs14-t3-landing.md` (LEAD terminal — merges first)
**Theme:** Launchable Landing Page
- **T3-A**: Gantt parallel station fix (#415) + landing-v6 → production Jinja2 (Tailwind v4 + Alpine.js)
- **T3-B**: Showcase data pipeline (#423) — nightly curation from DB, `showcase_data.json` with real defensible numbers, wire into `index()` route by name
- **T3-C**: Showcase card visual redesign (#403, #404) — Stuck Permit, What-If, Risk, Entity, Cost as visual-first components
- **T3-D**: Admin home from approved mockup (`web/static/mockups/admin-home.html`) + MCP demo fix (#407)

**Key files to read first:** `web/static/mockups/landing-v6.html`, `web/templates/landing.html`, `web/static/data/showcase_data.json`, `web/templates/components/showcase_*.html`, `web/routes_public.py` (index route), `docs/DESIGN_TOKENS.md`

**Critical rules:**
- Landing-v6 mockup IS the spec. Build from it, not from the old landing.html.
- ALL showcase numbers must be sourced from DB queries or clearly marked as illustrative. Decision 12: no claims >2x actual data.
- Gantt must show parallel stations as concurrent, not sequential. This is the #1 credibility issue.
- Use Tailwind v4 CDN for landing page (approved technology decision, Decision 10).

### `sprint-prompts/qs14-t1-intelligence.md`
**Theme:** Intelligence Backends + Search
- **T1-A**: Extend `compute_triage_signals()` in `web/helpers.py` — add stuck_diagnosis, violation_count, complaint_count
- **T1-B**: Create `web/intelligence_helpers.py` — sync wrappers for stuck/delay/similar (THE interface contract)
- **T1-C**: Update `web/templates/search_results.html` — render stuck diagnosis, violations, complaints
- **T1-D**: Add intelligence API endpoints to `web/routes_api.py` — HTMX fragments

**Interface contract T1-B must produce:**
```python
# web/intelligence_helpers.py
get_stuck_diagnosis_sync(permit_number: str) -> dict | None
# Returns: {severity, stuck_stations, interventions, agency_contacts}

get_delay_cost_sync(permit_type: str, monthly_cost: float, neighborhood: str = None) -> dict | None
# Returns: {daily_cost, weekly_cost, scenarios, mitigation, revision_risk}

get_similar_projects_sync(permit_type: str, neighborhood: str = None, cost: float = None) -> list[dict]
# Returns: [{permit_number, description, neighborhood, duration_days, routing_path}]
```
All wrappers: try/except → None/[] on failure, 3s timeout, warning logged.

**Key files to read first:** `web/helpers.py` (compute_triage_signals at ~line 912), `src/tools/stuck_permit.py`, `src/tools/cost_of_delay.py`, `src/tools/similar_projects.py`, `web/routes_api.py`, `web/templates/search_results.html`

### `sprint-prompts/qs14-t2-surfaces.md`
**Theme:** Analyze + Report Intelligence
- **T2-A**: Wire stuck + delay into `analyze()` function by name in `web/routes_public.py`
- **T2-B**: Add Stuck Analysis + Cost of Delay tabs to `web/templates/results.html`
- **T2-C**: Add intelligence section to `web/report.py` (max 2 stuck diagnoses, delay estimate, 5 similar projects)
- **T2-D**: Add Intelligence section to `web/templates/report.html`

**Depends on T1-B's interface contract.** Import from `web.intelligence_helpers`.

**Key files to read first:** `web/routes_public.py` (analyze function), `web/templates/results.html`, `web/report.py` (get_property_report), `web/templates/report.html`

### `sprint-prompts/qs14-t4-tests.md`
**Theme:** Tests + Brief + Admin + Fixes
- **T4-A**: Tests for intelligence_helpers, admin home, API endpoints, showcase pipeline
- **T4-B**: Morning brief stuck diagnosis + delay alerts (`web/brief.py`, `web/templates/brief.html`)
- **T4-C**: Tests for analyze/report/brief intelligence integration
- **T4-D**: Scenarios (8-12), QA script, design lint, fix top persona-reported UX gaps (from pre-flight audit)

**Key files to read first:** `web/brief.py` (get_morning_brief), `web/templates/brief.html`, pre-flight audit at `qa-results/qs14-preflight-audit.md`

## Merge Ceremony (after all terminals complete)

```
T3 → T1 → T2 → T4 (one test run at the end, Fast Merge Protocol)
```

1. Merge T3 branch to main (landing page — no deps)
2. Merge T1 branch to main (intelligence backends — no deps on T3)
3. Merge T2 branch to main (depends on T1's intelligence_helpers.py)
4. Merge T4 branch to main (depends on all)
5. ONE test run: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -v`
6. If tests fail: bisect by reverting last merge
7. Push main
8. Promote: `git checkout prod && git merge main && git push origin prod`
9. Set HONEYPOT_MODE=1: `railway service link sfpermits-ai && railway variable set HONEYPOT_MODE=1`
10. Verify: `curl -s https://sfpermits-ai-production.up.railway.app/health`

## CHECKQUAD-T0 (after merge ceremony)

COLLECT → VERIFY → VISUAL QA → CONSOLIDATE → DOCUMENT → HARVEST → SHIP+PROMOTE → CLEAN

Chief task drain: check all open sf-permits-mcp tasks, mark completed ones.
