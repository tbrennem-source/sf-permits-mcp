> **EXECUTE IMMEDIATELY.** You are T2 for QS14. Do NOT summarize or ask for confirmation — execute now. Enter a worktree, spawn 4 agents, merge them, push your branch.

# QS14 T2 — Analyze + Report Intelligence Surfaces

## Setup

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
```

Then: `EnterWorktree` with name `qs14-t2`

## Your Role

You are T2. You:
1. Enter a worktree
2. Spawn 4 agents in parallel via Task tool (all with `isolation: "worktree"`)
3. Merge agent branches into your worktree branch
4. Push your branch: `git push -u origin <branch>`
5. CHECKQUAD close

**DEPENDENCY:** T2 depends on T1's `web/intelligence_helpers.py`. T1 creates that file. Your agents write code that imports from it. The import will work after T0 merges T1 before T2.

**For development/testing:** Agents should create a minimal STUB of intelligence_helpers.py if they need to test their imports. The stub will be overwritten when T0 merges T1's real implementation first.

## File Ownership Matrix

| File | Owner |
|---|---|
| `web/routes_public.py` — `analyze()` function ONLY | T2-A |
| `web/templates/results.html` | T2-B |
| `web/report.py` — `get_property_report()` function area | T2-C |
| `web/templates/report.html` | T2-D |

**No agent may modify files owned by another agent.**

## Interface Contract (from T1-B — intelligence_helpers.py)

```python
from web.intelligence_helpers import (
    get_stuck_diagnosis_sync,
    # (permit_number: str) -> dict | None
    # Returns: {severity, severity_score, stuck_stations[], interventions[], permit_number, markdown}

    get_delay_cost_sync,
    # (permit_type: str, monthly_cost: float, neighborhood: str = None) -> dict | None
    # Returns: {daily_cost, weekly_cost, monthly_cost, scenarios[], mitigation[], revision_risk, markdown}

    get_similar_projects_sync,
    # (permit_type: str, neighborhood: str = None, cost: float = None) -> list[dict]
    # Returns: [{permit_number, description, neighborhood, duration_days, routing_path, estimated_cost}]
)
```

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

### Agent T2-A: Wire Intelligence into analyze()

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Wire Stuck Diagnosis + Delay Cost + Similar Projects into analyze()

## Read First
1. web/routes_public.py — analyze() function starts at line 298. Read the FULL function (about 200+ lines).
2. Understand the flow: analyze() calls 5 MCP tools (predict, timeline, fees, documents, revision_risk), collects results dict, returns template

## What to Build

Add 3 new intelligence sections to the analyze() function AFTER the existing 5 tool calls.

### Add to analyze() — after the existing tool calls (around line 450+):

```python
    # === QS14: Intelligence Wiring ===

    # 6. Stuck Diagnosis — if we can identify a permit number from the address
    stuck_diagnosis = None
    try:
        from web.intelligence_helpers import get_stuck_diagnosis_sync
        # Try to find a permit for this address
        if address:
            from web.helpers import compute_triage_signals
            triage = compute_triage_signals(
                street_number=address.split()[0] if address else None,
                street_name=' '.join(address.split()[1:]) if address else None,
                max_permits=1,
            )
            if triage and triage[0].get("permit_number"):
                stuck_diagnosis = get_stuck_diagnosis_sync(triage[0]["permit_number"])
    except Exception as e:
        logging.warning("Stuck diagnosis in analyze failed: %s", e)

    results["stuck_diagnosis"] = stuck_diagnosis

    # 7. Delay Cost — if we have monthly carrying cost
    delay_cost = None
    if monthly_carrying_cost:
        try:
            from web.intelligence_helpers import get_delay_cost_sync
            delay_cost = get_delay_cost_sync(permit_type, monthly_carrying_cost, neighborhood)
        except Exception as e:
            logging.warning("Delay cost in analyze failed: %s", e)

    results["delay_cost"] = delay_cost

    # 8. Similar Projects
    similar_projects = []
    try:
        from web.intelligence_helpers import get_similar_projects_sync
        similar_projects = get_similar_projects_sync(
            permit_type, neighborhood, estimated_cost
        )
    except Exception as e:
        logging.warning("Similar projects in analyze failed: %s", e)

    results["similar_projects"] = similar_projects

    # === END QS14 ===
```

### Add to the render_template call:
Make sure stuck_diagnosis, delay_cost, and similar_projects are passed to the template:
```python
return render_template(
    "results.html",
    # ... existing kwargs ...
    stuck_diagnosis=stuck_diagnosis,
    delay_cost=delay_cost,
    similar_projects=similar_projects,
)
```

### Create a stub for development
Since intelligence_helpers.py doesn't exist in your worktree yet, create a minimal stub:
```python
# web/intelligence_helpers.py (STUB — will be replaced by T1-B's real version)
def get_stuck_diagnosis_sync(permit_number):
    return None
def get_delay_cost_sync(permit_type, monthly_cost, neighborhood=None):
    return None
def get_similar_projects_sync(permit_type, neighborhood=None, cost=None):
    return []
```

## Important: Lazy Imports
Use lazy imports (inside the try/except blocks) to avoid circular import issues and to gracefully handle the case where intelligence_helpers.py doesn't exist yet.

## Output Files
- `web/routes_public.py` — MODIFY `analyze()` function ONLY
- `web/intelligence_helpers.py` — STUB only (will be overwritten by T1-B)

## Do NOT Touch
- web/templates/results.html (owned by T2-B)
- web/report.py (owned by T2-C)
- web/templates/report.html (owned by T2-D)

## DuckDB / Postgres Gotchas
- Not directly relevant for this task, but the triage_signals call uses DB
- Lazy imports prevent import-time DB connection issues

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/routes_public.py web/intelligence_helpers.py
git commit -m "feat(T2-A): wire stuck diagnosis, delay cost, similar projects into analyze()"
```

---

### Agent T2-B: Add Intelligence Tabs to results.html

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Add Stuck Analysis + Cost of Delay + Similar Projects Tabs to results.html

## Read First
1. web/templates/results.html — current results template (read FULL file)
2. docs/DESIGN_TOKENS.md — design system reference
3. web/static/mockups/landing-v6.html — for Tailwind styling consistency

## What to Build

Add 3 new tab sections to the results page. The existing results page already has tabs for Permits, Timeline, Fees, Documents, Revision Risk. Add:

### Tab: "Stuck Analysis"
Shows stuck diagnosis data (if available).
```jinja2
{% if stuck_diagnosis %}
<div id="tab-stuck" class="tab-content" style="display:none;">
    <h3>Stuck Permit Analysis</h3>
    <div class="mb-4">
        <span class="badge badge-{{ 'danger' if stuck_diagnosis.severity in ('HIGH', 'CRITICAL') else 'warning' }}">
            {{ stuck_diagnosis.severity }}
        </span>
        {% if stuck_diagnosis.severity_score %}
        <span class="text-sm text-gray-400">Score: {{ stuck_diagnosis.severity_score }}/100</span>
        {% endif %}
    </div>

    {% if stuck_diagnosis.stuck_stations %}
    <h4>Stuck Stations</h4>
    <table>
        <tr><th>Station</th><th>Days</th><th>Baseline</th><th>Status</th></tr>
        {% for s in stuck_diagnosis.stuck_stations %}
        <tr>
            <td>{{ s.station }}</td>
            <td>{{ s.days }}</td>
            <td>{{ s.baseline_p50 }}d</td>
            <td>{{ s.status }}</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}

    {% if stuck_diagnosis.interventions %}
    <h4>Recommended Actions</h4>
    <ol>
        {% for i in stuck_diagnosis.interventions %}
        <li>{{ i.action }}</li>
        {% endfor %}
    </ol>
    {% endif %}
</div>
{% endif %}
```

### Tab: "Cost of Delay"
Shows financial impact of delays.
```jinja2
{% if delay_cost %}
<div id="tab-delay" class="tab-content" style="display:none;">
    <h3>Cost of Delay</h3>
    <div class="grid grid-cols-3 gap-4 mb-4">
        <div>
            <div class="text-2xl font-bold text-amber-400">${{ "%.0f"|format(delay_cost.daily_cost) }}</div>
            <div class="text-sm text-gray-400">per day</div>
        </div>
        <div>
            <div class="text-2xl font-bold text-amber-400">${{ "%.0f"|format(delay_cost.weekly_cost) }}</div>
            <div class="text-sm text-gray-400">per week</div>
        </div>
        <div>
            <div class="text-2xl font-bold text-amber-400">${{ "%.0f"|format(delay_cost.monthly_cost) }}</div>
            <div class="text-sm text-gray-400">per month</div>
        </div>
    </div>

    {% if delay_cost.scenarios %}
    <h4>Scenario Analysis</h4>
    <table>
        <tr><th>Scenario</th><th>Duration</th><th>Total Cost</th></tr>
        {% for s in delay_cost.scenarios %}
        <tr>
            <td>{{ s.label }}</td>
            <td>{{ s.months }} months</td>
            <td>${{ "{:,.0f}".format(s.total_cost) }}</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}
</div>
{% endif %}
```

### Tab: "Similar Projects"
Shows comparable completed permits.
```jinja2
{% if similar_projects %}
<div id="tab-similar" class="tab-content" style="display:none;">
    <h3>Similar Completed Projects</h3>
    {% for p in similar_projects[:5] %}
    <div class="mb-3 pb-3 border-b border-gray-700">
        <div class="font-medium">{{ p.description[:100] }}{% if p.description|length > 100 %}...{% endif %}</div>
        <div class="text-sm text-gray-400 mt-1">
            {{ p.neighborhood }} · {{ p.duration_days }} days · ${{ "{:,.0f}".format(p.estimated_cost or 0) }}
        </div>
        {% if p.routing_path %}
        <div class="text-xs text-gray-500 mt-1">Route: {{ p.routing_path | join(' → ') }}</div>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endif %}
```

### Tab Navigation
Add the new tabs to the existing tab bar. Look for the existing tab navigation HTML and add:
```html
{% if stuck_diagnosis %}<button class="tab-btn" data-tab="stuck">Stuck Analysis</button>{% endif %}
{% if delay_cost %}<button class="tab-btn" data-tab="delay">Cost of Delay</button>{% endif %}
{% if similar_projects %}<button class="tab-btn" data-tab="similar">Similar Projects</button>{% endif %}
```

### Graceful Degradation
- Tabs only appear if the data exists
- If stuck_diagnosis is None → no tab
- If delay_cost is None → no tab
- If similar_projects is empty → no tab
- Existing tabs must continue to work unchanged

## Output Files
- `web/templates/results.html` (MODIFY — add 3 tab sections + tab buttons)

## Do NOT Touch
- web/routes_public.py (owned by T2-A)
- web/report.py (owned by T2-C)
- web/templates/report.html (owned by T2-D)

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/results.html
git commit -m "feat(T2-B): add stuck analysis, delay cost, similar projects tabs to results page"
```

---

### Agent T2-C: Add Intelligence to report.py

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Add Intelligence Section to Property Report

## Read First
1. web/report.py — get_property_report() starts at line 853. Read the FULL function.
2. Understand the return dict structure — it has keys like permits, complaints, violations, risk_assessment, etc.

## What to Build

Add an `intelligence` section to the property report data. This enriches the report with stuck diagnosis for active permits, delay estimates, and similar projects.

### Add to get_property_report() — near the end, before the return statement:

```python
    # === QS14: Intelligence enrichment ===
    intelligence = {"stuck_permits": [], "delay_estimate": None, "similar_projects": []}

    try:
        from web.intelligence_helpers import (
            get_stuck_diagnosis_sync,
            get_delay_cost_sync,
            get_similar_projects_sync,
        )

        # Stuck diagnosis for up to 2 active permits
        active_permits = [
            p for p in permits
            if p.get("permit_number")
            and (p.get("status") or "").lower() in ("filed", "plancheck", "issued")
        ][:2]

        for permit in active_permits:
            diag = get_stuck_diagnosis_sync(permit["permit_number"])
            if diag:
                intelligence["stuck_permits"].append(diag)

        # Delay estimate based on most common permit type
        if permits:
            common_type = permits[0].get("permit_type_definition", "alterations")
            # Use a default monthly cost for general estimation
            delay = get_delay_cost_sync(common_type, 5000.0)
            if delay:
                intelligence["delay_estimate"] = delay

        # Similar projects
        if permits:
            common_type = permits[0].get("permit_type_definition", "alterations")
            est_cost = permits[0].get("estimated_cost")
            similar = get_similar_projects_sync(
                common_type, None, float(est_cost) if est_cost else None
            )
            intelligence["similar_projects"] = similar[:5]

    except Exception as e:
        logger.warning("Intelligence enrichment failed for %s/%s: %s", block, lot, e)
    # === END QS14 ===
```

### Add to the return dict:
```python
    return {
        # ... existing keys ...
        "intelligence": intelligence,
    }
```

### Create a stub for development
```python
# web/intelligence_helpers.py (STUB)
def get_stuck_diagnosis_sync(permit_number):
    return None
def get_delay_cost_sync(permit_type, monthly_cost, neighborhood=None):
    return None
def get_similar_projects_sync(permit_type, neighborhood=None, cost=None):
    return []
```

## Output Files
- `web/report.py` — MODIFY get_property_report() function
- `web/intelligence_helpers.py` — STUB only (will be overwritten)

## Do NOT Touch
- web/routes_public.py (owned by T2-A)
- web/templates/results.html (owned by T2-B)
- web/templates/report.html (owned by T2-D)

## DuckDB / Postgres Gotchas
- report.py already uses get_connection() — follow existing patterns
- Lazy imports for intelligence_helpers to avoid circular imports

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/report.py web/intelligence_helpers.py
git commit -m "feat(T2-C): add intelligence enrichment to property report"
```

---

### Agent T2-D: Add Intelligence Section to report.html

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Add Intelligence Section to Property Report Template

## Read First
1. web/templates/report.html — current report template (read FULL file)
2. docs/DESIGN_TOKENS.md — design system reference

## What to Build

Add an "Intelligence" section to the property report template. The data comes from `report.intelligence` dict:

```python
intelligence = {
    "stuck_permits": [  # list of stuck diagnosis dicts
        {
            "permit_number": "...",
            "severity": "HIGH",
            "stuck_stations": [{station, days, baseline_p50, status}],
            "interventions": [{step, action, contact}],
        }
    ],
    "delay_estimate": {  # delay cost dict or None
        "daily_cost": 166.67,
        "weekly_cost": 1166.67,
        "scenarios": [{label, months, total_cost}],
    },
    "similar_projects": [  # list of similar project dicts
        {
            "permit_number": "...",
            "description": "...",
            "neighborhood": "...",
            "duration_days": 120,
            "routing_path": ["PERMIT-CTR", "BLDG"],
            "estimated_cost": 85000,
        }
    ],
}
```

### Template Section

Add this section AFTER the existing risk assessment section:

```jinja2
{% if report.intelligence %}
{% set intel = report.intelligence %}
<section class="report-section" id="intelligence">
    <h2>Intelligence</h2>

    {# Stuck Permits #}
    {% if intel.stuck_permits %}
    <div class="subsection">
        <h3>Stuck Permit Analysis</h3>
        {% for diag in intel.stuck_permits %}
        <div class="card mb-3">
            <div class="flex items-center gap-2 mb-2">
                <span class="badge badge-{{ 'danger' if diag.severity in ('HIGH', 'CRITICAL') else 'warning' }}">
                    {{ diag.severity }}
                </span>
                <span class="text-sm">Permit {{ diag.permit_number }}</span>
            </div>
            {% if diag.stuck_stations %}
            {% for s in diag.stuck_stations %}
            <p class="text-sm">
                <strong>{{ s.station }}</strong>: {{ s.days }} days
                (baseline {{ s.baseline_p50 }}d — {{ (s.days / s.baseline_p50)|round(1) }}x)
            </p>
            {% endfor %}
            {% endif %}
            {% if diag.interventions %}
            <p class="text-sm mt-2"><strong>Recommended:</strong> {{ diag.interventions[0].action }}</p>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {# Delay Cost Estimate #}
    {% if intel.delay_estimate %}
    <div class="subsection">
        <h3>Cost of Delay</h3>
        <div class="grid grid-cols-2 gap-4 mb-3">
            <div>
                <div class="text-xl font-bold">${{ "%.0f"|format(intel.delay_estimate.daily_cost) }}/day</div>
                <div class="text-sm text-gray-400">${{ "%.0f"|format(intel.delay_estimate.weekly_cost) }}/week</div>
            </div>
        </div>
        {% if intel.delay_estimate.scenarios %}
        <table class="w-full text-sm">
            <thead><tr><th>Scenario</th><th>Duration</th><th>Impact</th></tr></thead>
            <tbody>
            {% for s in intel.delay_estimate.scenarios %}
            <tr>
                <td>{{ s.label }}</td>
                <td>{{ s.months }} months</td>
                <td>${{ "{:,.0f}".format(s.total_cost) }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div>
    {% endif %}

    {# Similar Projects #}
    {% if intel.similar_projects %}
    <div class="subsection">
        <h3>Similar Completed Projects</h3>
        {% for p in intel.similar_projects[:5] %}
        <div class="mb-2 pb-2 border-b border-gray-700">
            <div class="font-medium text-sm">{{ p.description[:80] }}{% if p.description|length > 80 %}...{% endif %}</div>
            <div class="text-xs text-gray-400">
                {{ p.neighborhood }} · {{ p.duration_days }}d · ${{ "{:,.0f}".format(p.estimated_cost or 0) }}
            </div>
            {% if p.routing_path %}
            <div class="text-xs text-gray-500">{{ p.routing_path | join(' → ') }}</div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endif %}
</section>
{% endif %}
```

### Navigation Link
Add "Intelligence" to the report's table of contents / section navigation if one exists.

### Graceful Degradation
- If `report.intelligence` doesn't exist → section doesn't render
- If sub-lists are empty → their subsections don't render
- Must work with existing reports that don't have intelligence data

## Output Files
- `web/templates/report.html` (MODIFY — add intelligence section)

## Do NOT Touch
- web/routes_public.py (owned by T2-A)
- web/templates/results.html (owned by T2-B)
- web/report.py (owned by T2-C)

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/report.html
git commit -m "feat(T2-D): add intelligence section to property report template"
```

---

## After All 4 Agents Complete

### Merge Ceremony (internal to T2)

Merge agents in order: T2-A → T2-C → T2-B → T2-D

(Backend before templates — T2-A and T2-C both create stubs that get deduped)

```bash
git merge <agent-A-branch> --no-edit
git merge <agent-C-branch> --no-edit  # May conflict on intelligence_helpers stub — keep either
git merge <agent-B-branch> --no-edit
git merge <agent-D-branch> --no-edit
```

If conflicts on `web/intelligence_helpers.py` (both A and C create stubs): keep either version — it's just a stub that gets overwritten when T0 merges T1.

### Push

```bash
git push -u origin $(git branch --show-current)
```

### CHECKQUAD Close

**Step 0 — ESCAPE CWD:** `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

1. **MERGE:** All 4 agent branches merged into your worktree branch
2. **ARTIFACT:** Write a brief session report
3. **CAPTURE:** Note any scenarios
4. **HYGIENE CHECK:** Verify no files outside ownership matrix were modified
5. **SIGNAL DONE:** Push branch, output "T2 COMPLETE — branch: <name>"

```bash
bash scripts/notify.sh terminal-done "T2 surfaces complete"
```
