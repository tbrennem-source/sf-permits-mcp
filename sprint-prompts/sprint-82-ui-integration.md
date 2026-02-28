# Sprint 82 — Intelligence UI Integration (4 agents, 1 terminal)

> Wire QS8's 4 intelligence tools into web routes + templates.
> The data layer is ready — this sprint builds the UI.

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "Sprint 82 start: $(git rev-parse --short HEAD)"
```

## Context

QS8 shipped 4 standalone tools. They return markdown strings, have tests, but NO web routes and NO template sections. This sprint wires them in.

| Tool | Import | Natural Home |
|------|--------|-------------|
| `predict_next_stations(permit_number)` | `src.tools.predict_next_stations` | Property report — per-permit prediction |
| `diagnose_stuck_permit(permit_number)` | `src.tools.stuck_permit` | Property report — triggered when stalled |
| `simulate_what_if(desc, variations)` | `src.tools.what_if_simulator` | Search results — project planning |
| `calculate_delay_cost(type, cost)` | `src.tools.cost_of_delay` | Search results — paired with timeline |

Also: `get_morning_brief()["pipeline_stats"]` exists but brief.html has no section for it.

**Mockups:** Check `web/static/mockups/property-intel.html` for approved property report layout. If no mockup exists for a section, use glass-card + obs-table patterns from DESIGN_TOKENS.md.

## File Ownership Matrix

| Agent | Files Owned |
|-------|-------------|
| A | `web/routes_property.py`, `web/templates/report.html` |
| B | `web/routes_search.py`, `web/templates/results.html`, `web/templates/fragments/what_if_panel.html` (NEW) |
| C | `web/templates/brief.html`, `web/templates/fragments/pipeline_stats.html` (NEW) |
| D | `src/server.py`, `web/routes_admin.py`, `web/templates/fragments/admin_health.html` (NEW) |

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent A: Property Report Intelligence

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Wire predict_next_stations + diagnose_stuck_permit into property report

### File Ownership
- web/routes_property.py
- web/templates/report.html

### Read First
- src/tools/predict_next_stations.py (understand input/output — takes permit_number, returns markdown)
- src/tools/stuck_permit.py (takes permit_number, returns markdown)
- web/routes_property.py (property_report route — understand data flow)
- web/templates/report.html (current template — find where per-permit data is displayed)
- web/report.py (get_property_report — the data assembly function)
- docs/DESIGN_TOKENS.md (for styling — read FULL file)
- web/static/mockups/property-intel.html (if it exists — follow it exactly)

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

### Build

Task A-1: Add intelligence data to property report route in web/routes_property.py:
```python
from src.tools.predict_next_stations import predict_next_stations
from src.tools.stuck_permit import diagnose_stuck_permit
import asyncio

# For each permit in the report that has addenda routing data:
# 1. Run predict_next_stations(permit_number) — async, use asyncio.run() or run_async()
# 2. If severity score > 60 (stalled), also run diagnose_stuck_permit(permit_number)
# 3. Pass results to template context
```

Keep it non-blocking: if tools fail or return errors, show the report without intelligence.
Use try/except — intelligence is additive, never breaks the base report.

Task A-2: Add "What's Next" section to report.html per-permit card:
- Collapsible section (click to expand) — don't clutter the default view
- Header: "Predicted Next Steps" with a subtle icon
- Content: render the markdown from predict_next_stations as HTML
- Use glass-card container, obs-table for the prediction table
- If no data: hide the section entirely (not "no data available")

Task A-3: Add "Stuck Permit Diagnosis" section (conditional):
- Only shows when severity > threshold AND diagnose_stuck_permit returned data
- Red/amber signal color header depending on severity
- Intervention steps as numbered list
- Contact info in a subtle footer

### Test
Write tests/test_sprint_82_a.py:
- test_report_includes_prediction_section (mock tool, verify HTML contains section)
- test_report_hides_prediction_when_no_data
- test_stuck_diagnosis_shows_when_severe (mock severity > 60)
- test_stuck_diagnosis_hidden_when_healthy
- test_tool_failure_doesnt_break_report

### Output Files
- scenarios-pending-review-sprint-82-a.md
- CHANGELOG-sprint-82-a.md

### Commit
feat: wire predict_next_stations + stuck_permit into property report (Sprint 82-A)
""")
```

---

### Agent B: Search Flow Intelligence

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Wire what-if simulator + cost of delay into search results

### File Ownership
- web/routes_search.py
- web/templates/results.html
- web/templates/fragments/what_if_panel.html (NEW)

### Read First
- src/tools/what_if_simulator.py (takes base_description + variations list, returns markdown)
- src/tools/cost_of_delay.py (takes permit_type + monthly_carrying_cost, returns markdown)
- web/routes_search.py (search route — understand when project descriptions are available)
- web/templates/results.html (current results page — find the permit prediction section)
- docs/DESIGN_TOKENS.md (for styling)

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

### Build

Task B-1: Add "What If?" panel to results page:
- When search results include a permit prediction (from predict_permits), show a "What If?" expandable panel below the prediction
- Pre-populate 3 common variations:
  - "What if I reduce scope to under $50K?" (OTC threshold)
  - "What if I add [related scope]?" (inferred from project type)
  - "What if I move to [different neighborhood]?"
- Each variation is a button. On click, HTMX POST to a new endpoint that runs simulate_what_if
- Response renders as a comparison table in the panel

Task B-2: Add /search/what-if endpoint to web/routes_search.py:
```python
@bp.route("/search/what-if", methods=["POST"])
@login_required
def search_what_if():
    base = request.form.get("base_description")
    variation = request.form.get("variation_description")
    variation_label = request.form.get("variation_label")
    # Run simulate_what_if with base + 1 variation
    # Return HTML fragment for HTMX swap
```

Task B-3: Add cost of delay estimate below timeline predictions:
- When results show a timeline estimate, append: "What does this delay cost you?"
- Expandable section with monthly carrying cost input (default $5,000)
- On input change, HTMX POST to /search/delay-cost → renders cost table
- Use the daily_delay_cost() one-liner as a teaser above the full table

Task B-4: Add /search/delay-cost endpoint:
```python
@bp.route("/search/delay-cost", methods=["POST"])
@login_required
def search_delay_cost():
    permit_type = request.form.get("permit_type", "alterations")
    monthly_cost = float(request.form.get("monthly_cost", 5000))
    # Run calculate_delay_cost
    # Return HTML fragment
```

### Test
Write tests/test_sprint_82_b.py:
- test_what_if_endpoint_returns_html
- test_what_if_requires_auth
- test_delay_cost_endpoint_returns_html
- test_delay_cost_default_values
- test_results_page_has_what_if_buttons (when prediction present)

### Output Files
- scenarios-pending-review-sprint-82-b.md
- CHANGELOG-sprint-82-b.md

### Commit
feat: what-if simulator + cost of delay in search results (Sprint 82-B)
""")
```

---

### Agent C: Brief Pipeline Stats

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Add pipeline stats section to morning brief page

### File Ownership
- web/templates/brief.html
- web/templates/fragments/pipeline_stats.html (NEW)

### Read First
- web/brief.py (get_morning_brief — find the pipeline_stats key in returned dict)
- web/templates/brief.html (current template — find where to add new section)
- docs/DESIGN_TOKENS.md (for styling)

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

### Build

Task C-1: Create fragments/pipeline_stats.html:
- Section header: "System Health" with a subtle pulse dot (green=all cron jobs OK, amber=some failed)
- Show last 5 cron job results as a compact table:
  | Job | Last Run | Duration | Status |
  |-----|----------|----------|--------|
  | nightly-changes | 2h ago | 45s | OK |
  | compute-caches | 15m ago | 12s | OK |
- Use obs-table class, --mono for timestamps/durations
- If pipeline_stats is empty or missing: hide section entirely

Task C-2: Include fragment in brief.html:
- Add after the main brief content sections, before the footer
- Wrap in a collapsible section (collapsed by default — this is ops info, not primary)
- Header shows green/amber dot + "System Health" text

Task C-3: Add "Data freshness" indicator:
- Show when permit data was last refreshed (from cron_log)
- "Data as of: 2h ago" in --text-tertiary at the top of the brief
- If > 24h stale: amber warning

### Test
Write tests/test_sprint_82_c.py:
- test_brief_includes_pipeline_section (mock pipeline_stats in context)
- test_brief_hides_pipeline_when_empty
- test_data_freshness_shows_timestamp
- test_data_freshness_warns_when_stale

### Output Files
- scenarios-pending-review-sprint-82-c.md
- CHANGELOG-sprint-82-c.md

### Commit
feat: pipeline stats + data freshness in morning brief (Sprint 82-C)
""")
```

---

### Agent D: Tool Registration + Admin Health

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.

## YOUR TASK: Register 4 intelligence tools in MCP server + admin health dashboard

### File Ownership
- src/server.py
- web/routes_admin.py
- web/templates/fragments/admin_health.html (NEW)

### Read First
- src/server.py (tool registration pattern — see how existing 30 tools are registered)
- src/tools/predict_next_stations.py (function signature + docstring)
- src/tools/stuck_permit.py (function signature + docstring)
- src/tools/what_if_simulator.py (function signature + docstring)
- src/tools/cost_of_delay.py (function signature + docstring)
- web/routes_admin.py (admin dashboard route)
- src/soda_client.py (find the CircuitBreaker class — for admin display)
- src/db.py (get_pool_stats — for admin display)

### Build

Task D-1: Register 4 tools in src/server.py:
- predict_next_stations → tool name: "predict_next_stations"
- diagnose_stuck_permit → tool name: "diagnose_stuck_permit"
- simulate_what_if → tool name: "simulate_what_if"
- calculate_delay_cost → tool name: "calculate_delay_cost"
Follow the exact pattern used by existing tools. Each gets @server.tool() decorator equivalent.
Total tools: 30 → 34.

Task D-2: Add system health panel to admin dashboard in web/routes_admin.py:
- New section on /admin showing:
  - DB pool: connections in use / available / max (from get_pool_stats)
  - SODA circuit breaker: state (closed/open/half-open), failure count, last failure time
  - Page cache: row count, oldest entry, hit rate estimate
- Route: enhance existing /admin or add /admin/health endpoint that returns HTML fragment

Task D-3: Create fragments/admin_health.html:
- 3 glass-cards side by side: Pool, Circuit Breaker, Cache
- Pool card: bar showing used/available, number labels
- Circuit breaker: green dot (closed), red dot (open), amber dot (half-open) + failure count
- Cache: row count + "oldest: Xh ago"
- Auto-refresh via HTMX poll every 30s

### Test
Write tests/test_sprint_82_d.py:
- test_server_has_34_tools (count registered tools)
- test_predict_next_stations_registered
- test_diagnose_stuck_permit_registered
- test_simulate_what_if_registered
- test_calculate_delay_cost_registered
- test_admin_health_requires_auth
- test_admin_health_shows_pool_stats

### Output Files
- scenarios-pending-review-sprint-82-d.md
- CHANGELOG-sprint-82-d.md

### Commit
feat: register 4 intelligence tools + admin health dashboard (Sprint 82-D)
""")
```

---

## Post-Agent: Merge + Push

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge order: D (server.py first), A (report), B (search), C (brief)
git merge <agent-d-branch> --no-edit
git merge <agent-a-branch> --no-edit
git merge <agent-b-branch> --no-edit
git merge <agent-c-branch> --no-edit

cat scenarios-pending-review-sprint-82-*.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-sprint-82-*.md >> CHANGELOG.md 2>/dev/null

git push origin main
```

## Report Template

```
Sprint 82 COMPLETE — Intelligence UI Integration
=================================================
  A: Report intelligence:    [PASS/FAIL] (predict + stuck permit on report page)
  B: Search intelligence:    [PASS/FAIL] (what-if + cost of delay on results)
  C: Brief pipeline stats:   [PASS/FAIL] (system health + data freshness)
  D: Tool registration:      [PASS/FAIL] (30→34 MCP tools + admin health)
  Tests: [N new]
  Pushed: [commit hash]
```
