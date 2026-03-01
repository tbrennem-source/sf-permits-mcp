> **EXECUTE IMMEDIATELY.** You are T3 for QS14. Do NOT summarize or ask for confirmation — execute now. Enter a worktree, spawn 4 agents, merge them, push your branch.

# QS14 T3 — Launchable Landing Page (LEAD terminal, merges first)

## Setup

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
```

Then: `EnterWorktree` with name `qs14-t3`

## Your Role

You are T3. You:
1. Enter a worktree
2. Spawn 4 agents in parallel via Task tool (all with `isolation: "worktree"`)
3. Merge agent branches into your worktree branch
4. Push your branch: `git push -u origin <branch>`
5. CHECKQUAD close

## Read First (YOU, not agents — agents get their own read lists)

- `web/static/mockups/landing-v6.html` — THE landing page spec
- `web/static/mockups/admin-home.html` — admin home spec
- `web/templates/landing.html` — current production template
- `web/routes_public.py` — `index()` at line 66, `_load_showcase_data()` at line 52
- `web/static/data/showcase_data.json` — current showcase data (829 lines)
- `web/templates/components/showcase_*.html` — 6 existing components
- `docs/DESIGN_TOKENS.md` — design system reference

## File Ownership Matrix

| File | Owner |
|---|---|
| `web/templates/landing.html` | T3-A |
| `web/templates/components/showcase_gantt.html` | T3-A |
| `scripts/refresh_showcase.py` | T3-B (NEW) |
| `web/static/data/showcase_data.json` | T3-B |
| `web/routes_public.py` — `_load_showcase_data()` and `index()` | T3-B |
| `web/templates/components/showcase_stuck.html` | T3-C |
| `web/templates/components/showcase_whatif.html` | T3-C |
| `web/templates/components/showcase_risk.html` | T3-C |
| `web/templates/components/showcase_entity.html` | T3-C |
| `web/templates/components/showcase_delay.html` | T3-C |
| `web/templates/admin_home.html` | T3-D (NEW) |
| `web/routes_admin.py` | T3-D |

**No agent may modify files owned by another agent.**

## DuckDB / Postgres Gotchas (INCLUDE in every agent prompt)

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()` (Postgres uses cursors)
- Postgres transactions abort on any error — use autocommit for DDL
- Use `from src.db import BACKEND, query, get_connection` — BACKEND is "postgres" in prod

## Agent Definitions

Spawn ALL 4 agents in parallel using the Task tool. Each agent call:
- `subagent_type: "general-purpose"`
- `model: "sonnet"`
- `isolation: "worktree"`

---

### Agent T3-A: Gantt Fix + Landing-v6 → Production Jinja2

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Gantt Parallel Station Fix (#415) + Landing-v6 → Production Jinja2

## Read First
1. web/static/mockups/landing-v6.html — THIS IS THE SPEC. Build from this, not old landing.html.
2. web/templates/landing.html — current production template (will be REPLACED)
3. web/templates/components/showcase_gantt.html — current Gantt (BROKEN: shows parallel stations as sequential)
4. docs/DESIGN_TOKENS.md — design system reference

## What to Build

### 1. Convert landing-v6.html mockup to production Jinja2 template
- landing-v6.html uses Tailwind v4 CDN + Alpine.js — KEEP these (approved Decision 10)
- Convert hardcoded mockup content to Jinja2 template variables
- The template receives `showcase` dict from the route: {{ showcase.station_timeline }}, etc.
- Keep the Tailwind CDN link in the template <head> — this is intentional for the landing page
- Keep Alpine.js CDN link for interactivity
- Preserve ALL sections from the mockup: hero, capability cards, showcase area, search bar, footer
- The search form should POST to /analyze (existing route)

### 2. Fix Gantt to show parallel stations as concurrent
- Current showcase_gantt.html renders stations as a sequential vertical list
- Real permits have stations running IN PARALLEL (e.g., BLDG + SFFD + CP-ZOC all start the same week)
- The showcase_data.json has station data with start_month and width_pct fields
- Render as a HORIZONTAL Gantt where:
  - Y-axis = station names
  - X-axis = time (months)
  - Each station is a horizontal bar positioned at its start_month with width proportional to duration
  - Parallel stations appear on DIFFERENT ROWS at the SAME horizontal position
  - Use Tailwind grid or flexbox for layout
- This is the #1 credibility issue — architects and expediters will immediately see if it's wrong

### 3. Template integration
- The template must work with the existing route: `index()` passes `showcase=_load_showcase_data()`
- Include the showcase components via Jinja2 includes: {% include 'components/showcase_gantt.html' %}
- Make sure the template extends the correct base or is self-contained (landing-v6 is self-contained with its own <html>)

## Output Files
- `web/templates/landing.html` — COMPLETE REWRITE from mockup
- `web/templates/components/showcase_gantt.html` — REWRITE with parallel station rendering

## Do NOT Touch
- web/routes_public.py (owned by T3-B)
- web/static/data/showcase_data.json (owned by T3-B)
- Any showcase_*.html EXCEPT showcase_gantt.html (owned by T3-C)

## DuckDB / Postgres Gotchas
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/landing.html web/templates/components/showcase_gantt.html
git commit -m "feat(T3-A): convert landing-v6 mockup to production Jinja2 + fix Gantt parallel stations"
```

---

### Agent T3-B: Showcase Data Pipeline

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Showcase Data Pipeline (#423)

## Read First
1. web/static/data/showcase_data.json — current showcase data (829 lines, hardcoded)
2. web/routes_public.py — _load_showcase_data() at line 52, index() at line 66
3. src/db.py — database connection utilities
4. web/helpers.py — run_async helper

## What to Build

### 1. Create scripts/refresh_showcase.py
A CLI script that queries REAL permit data from the database and writes showcase_data.json.

The script must:
- Connect to the database (use src.db.get_connection, BACKEND)
- Query for a REAL interesting permit to feature (e.g., large commercial alteration, currently in review, has multiple stations)
- Build the station_timeline structure with REAL data:
  - permit_number, description, address, estimated_cost, permit_type, neighborhood, status, filed_date
  - stations array: query addenda table for the permit's routing history
  - Each station needs: station, name, label, arrive, finish_date, review_results, dwell_days, status, is_current, reviewer
  - Compute start_month and width_pct for Gantt rendering (relative to filed_date)
- Query for REAL showcase numbers:
  - stuck_permit: pick a real permit that's actually stuck (days_at_station > 2x median)
  - entity_network: real entity with connections from the entities/relationships tables
  - what_if: real comparison data from timeline estimates
  - revision_risk: real revision rate from permit data (Decision 12: no claims >2x actual)
  - delay_cost: real cost calculation based on actual timeline data
- Write to web/static/data/showcase_data.json
- All numbers must be DEFENSIBLE — sourced from DB queries or clearly marked as computed
- Decision 12: No claims >2x actual data. If real revision rate is 12%, don't claim 73%.

### 2. Update _load_showcase_data() in routes_public.py
- Currently loads from static JSON file — this is fine for now
- Add a fallback: if showcase_data.json is empty or missing keys, return sensible defaults
- The function is called from index(): `showcase = _load_showcase_data()`

### 3. Wire showcase into index() route
- The index() route already passes `showcase=showcase` to the template
- Verify the showcase dict keys match what the landing template expects
- If the template expects keys like showcase.station_timeline, showcase.stuck_permit, etc., make sure the JSON has those keys

## Database Queries for Showcase Data

Use these patterns (Postgres-compatible):

```python
from src.db import get_connection, BACKEND, query

conn = get_connection()
# For raw queries:
with conn.cursor() as cur:
    cur.execute("SELECT ... FROM permits WHERE ... LIMIT 1")
    row = cur.fetchone()
```

For the station timeline, query the addenda table:
```sql
SELECT station, plan_checked_by, review_result, arrive_date, finish_date,
       addenda_number, hold_description
FROM addenda
WHERE permit_number = %s
ORDER BY addenda_number, arrive_date
```

For stuck permits:
```sql
-- Find permits stuck at a station longer than 2x the median
SELECT p.permit_number, p.description, p.street_number, p.street_name,
       a.station, a.arrive_date,
       EXTRACT(DAY FROM NOW() - a.arrive_date::timestamp) as days_at_station
FROM permits p
JOIN addenda a ON a.permit_number = p.permit_number
WHERE a.finish_date IS NULL
  AND a.arrive_date IS NOT NULL
  AND p.status IN ('filed', 'plancheck')
ORDER BY days_at_station DESC
LIMIT 5
```

### Important: Anonymization
- The landing page is PUBLIC. Do NOT include real people's names.
- Anonymize: reviewer names → "Senior Plan Checker", entity names → use company types
- Addresses and permit numbers are public record — those are fine

## Output Files
- `scripts/refresh_showcase.py` (NEW)
- `web/static/data/showcase_data.json` (REWRITE with real data)
- `web/routes_public.py` — ONLY modify `_load_showcase_data()` and `index()` functions

## Do NOT Touch
- web/templates/landing.html (owned by T3-A)
- web/templates/components/showcase_*.html (owned by T3-A and T3-C)
- web/routes_admin.py (owned by T3-D)

## DuckDB / Postgres Gotchas
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — wrap in try/except
- BACKEND is "postgres" in prod, "duckdb" locally. Code must handle both.

## Test
source .venv/bin/activate
python scripts/refresh_showcase.py  # Should produce valid JSON
python -c "import json; d=json.load(open('web/static/data/showcase_data.json')); print(list(d.keys()))"
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add scripts/refresh_showcase.py web/static/data/showcase_data.json web/routes_public.py
git commit -m "feat(T3-B): showcase data pipeline with real DB-sourced permit data"
```

---

### Agent T3-C: Showcase Card Visual Redesign

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Showcase Card Visual Redesign (#403, #404)

## Read First
1. web/templates/components/showcase_stuck.html — current (raw JSON text dump)
2. web/templates/components/showcase_whatif.html — current
3. web/templates/components/showcase_risk.html — current
4. web/templates/components/showcase_entity.html — current
5. web/templates/components/showcase_delay.html — current
6. web/static/data/showcase_data.json — data structure these cards consume
7. docs/DESIGN_TOKENS.md — design system tokens (MANDATORY reference)
8. web/static/mockups/landing-v6.html — see how cards are styled in the mockup

## What to Build

Redesign ALL 5 showcase card components to be VISUAL-FIRST, not text dumps.

### Design Principles (from Tim)
- Cards should communicate at a glance — a professional sees it and gets the point in 2 seconds
- NO raw JSON or markdown dumps
- Use Tailwind v4 utility classes (the landing page uses Tailwind CDN)
- Each card is an {% include %} component that receives data via the `showcase` template variable

### Card-by-Card Spec

**showcase_stuck.html** — Stuck Permit Diagnosis
- Show: permit status badge, station name, days stuck, severity indicator (red/amber/green)
- Visual: progress bar showing how far through review, red highlight on stuck station
- Data: showcase.stuck_permit.permit_number, .station, .days_at_station, .severity, .intervention

**showcase_whatif.html** — What-If Scenario Comparison
- Show: base scenario vs variation side-by-side
- Visual: comparison table or side-by-side cards with delta indicators (↑↓)
- Data: showcase.what_if.base, showcase.what_if.variation, .delta_days, .delta_cost

**showcase_risk.html** — Revision Risk Assessment
- Show: revision probability percentage, top triggers, mitigation actions
- Visual: risk gauge or meter, bullet list of triggers
- Data: showcase.revision_risk.probability, .triggers, .mitigation

**showcase_entity.html** — Entity Network
- Show: entity name, permit count, top connections
- Visual: simple node diagram or connection list with relationship strength
- Data: showcase.entity_network.name, .permit_count, .connections[]

**showcase_delay.html** — Cost of Delay
- Show: daily/weekly/monthly cost, timeline scenarios (best/likely/worst)
- Visual: cost ticker or stacked bar showing scenario costs
- Data: showcase.delay_cost.daily, .weekly, .scenarios[]

### Tailwind Classes to Use
- Cards: `bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6`
- Headings: `text-lg font-semibold text-white`
- Data values: `text-2xl font-bold text-emerald-400` (or amber/red for warnings)
- Labels: `text-sm text-gray-400`
- Badges: `px-2 py-1 rounded-full text-xs font-medium`
- Status colors: emerald-400 (good), amber-400 (warning), red-400 (critical)

### Graceful Degradation
Each card must handle missing data gracefully:
```jinja2
{% if showcase.stuck_permit %}
  {# render card #}
{% else %}
  <div class="text-gray-500 text-sm italic">Analysis unavailable</div>
{% endif %}
```

## Output Files
- `web/templates/components/showcase_stuck.html` (REWRITE)
- `web/templates/components/showcase_whatif.html` (REWRITE)
- `web/templates/components/showcase_risk.html` (REWRITE)
- `web/templates/components/showcase_entity.html` (REWRITE)
- `web/templates/components/showcase_delay.html` (REWRITE)

## Do NOT Touch
- showcase_gantt.html (owned by T3-A)
- web/templates/landing.html (owned by T3-A)
- web/routes_public.py (owned by T3-B)
- web/static/data/showcase_data.json (owned by T3-B)

## DuckDB / Postgres Gotchas
- Not directly relevant (template-only work), but don't add any DB queries to templates

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/components/showcase_stuck.html web/templates/components/showcase_whatif.html web/templates/components/showcase_risk.html web/templates/components/showcase_entity.html web/templates/components/showcase_delay.html
git commit -m "feat(T3-C): visual-first showcase card redesign for landing page"
```

---

### Agent T3-D: Admin Home from Mockup + MCP Demo Fix

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Admin Home from Approved Mockup + MCP Demo Fix (#407)

## Read First
1. web/static/mockups/admin-home.html — THE admin home spec (approved mockup)
2. web/routes_admin.py — admin blueprint, existing routes
3. web/templates/ — check for any existing admin_home or admin_dashboard templates
4. docs/DESIGN_TOKENS.md — design system tokens

## What to Build

### 1. Admin Home Page
- Convert the admin-home.html mockup to a production Jinja2 template
- The mockup is the spec — follow it exactly
- Route: add or update the admin dashboard route in web/routes_admin.py
- Template: create web/templates/admin_home.html
- Wire real data where possible: user count, feedback count, recent activity
- The page should require admin authentication (use @login_required and check is_admin)

### 2. MCP Demo Fix (#407)
- Check the /demo route or MCP demo section
- Read web/routes_public.py for the demo route (search for "demo")
- Fix whatever is broken — the issue is that the MCP demo doesn't work properly
- Common issues: CORS, endpoint URL, response format

### Admin Route Pattern
```python
@bp.route("/admin/home")
@login_required
def admin_home():
    if not g.user.get("is_admin"):
        abort(403)
    # Gather dashboard data
    stats = _get_admin_stats()
    return render_template("admin_home.html", **stats)
```

## Output Files
- `web/templates/admin_home.html` (NEW)
- `web/routes_admin.py` (MODIFY — add admin_home route)

## Do NOT Touch
- web/templates/landing.html (owned by T3-A)
- web/routes_public.py (owned by T3-B)
- web/templates/components/showcase_*.html (owned by T3-A/C)

## DuckDB / Postgres Gotchas
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/admin_home.html web/routes_admin.py
git commit -m "feat(T3-D): admin home from mockup + MCP demo fix (#407)"
```

---

## After All 4 Agents Complete

### Merge Ceremony (internal to T3)

Merge agents in order: T3-A → T3-B → T3-C → T3-D

```bash
# From your worktree directory
git merge <agent-A-branch> --no-edit
git merge <agent-B-branch> --no-edit
git merge <agent-C-branch> --no-edit
git merge <agent-D-branch> --no-edit
```

If conflicts: resolve by keeping the agent's changes for files they own per the ownership matrix.

### Push

```bash
git push -u origin $(git branch --show-current)
```

### CHECKQUAD Close

**Step 0 — ESCAPE CWD:** `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

1. **MERGE:** All 4 agent branches merged into your worktree branch
2. **ARTIFACT:** Write a brief session report: what was built, any issues
3. **CAPTURE:** Note any scenarios for scenarios-pending-review.md
4. **HYGIENE CHECK:** Verify no files outside ownership matrix were modified
5. **SIGNAL DONE:** Push branch, output "T3 COMPLETE — branch: <name>"

```bash
# Notification
bash scripts/notify.sh terminal-done "T3 landing complete"
```
