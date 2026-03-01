> **EXECUTE IMMEDIATELY.** You are T1 for QS14. Do NOT summarize or ask for confirmation — execute now. Enter a worktree, spawn 4 agents, merge them, push your branch.

# QS14 T1 — Intelligence Backends + Search

## Setup

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
```

Then: `EnterWorktree` with name `qs14-t1`

## Your Role

You are T1. You:
1. Enter a worktree
2. Spawn 4 agents in parallel via Task tool (all with `isolation: "worktree"`)
3. Merge agent branches into your worktree branch
4. Push your branch: `git push -u origin <branch>`
5. CHECKQUAD close

**CRITICAL:** T1-B creates `web/intelligence_helpers.py` — this is THE interface contract consumed by T2 and T4. The function signatures MUST match exactly.

## File Ownership Matrix

| File | Owner |
|---|---|
| `web/helpers.py` — `compute_triage_signals()` function ONLY | T1-A |
| `web/intelligence_helpers.py` | T1-B (NEW) |
| `web/templates/search_results.html` | T1-C |
| `web/routes_api.py` | T1-D |

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

### Agent T1-A: Extend compute_triage_signals()

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Extend compute_triage_signals() with stuck diagnosis, violations, complaints

## Read First
1. web/helpers.py — compute_triage_signals() starts at line 912. Read the FULL function (about 100 lines).
2. src/tools/stuck_permit.py — _diagnose_station() at line 290, _fetch_active_stations() at line 174
3. src/db.py — get_connection(), BACKEND, query()

## What to Build

Extend the existing compute_triage_signals() function in web/helpers.py to add three new fields to each permit signal dict:

### New fields per permit:
```python
{
    # ... existing fields (permit_number, status, description, filed_date, current_station, etc.)

    # NEW: Stuck diagnosis (lightweight — just check if days > 2x median)
    "stuck_diagnosis": {
        "is_stuck": True,  # bool
        "severity": "high",  # "low" | "medium" | "high" | "critical"
        "station": "CP-ZOC",  # which station is stuck
        "days": 45,  # days at current station
        "median": 12,  # median for this station
        "ratio": 3.75,  # days / median
    } | None,  # None if not stuck or error

    # NEW: Violation count for this property
    "violation_count": 3,  # int, 0 if none

    # NEW: Complaint count for this property
    "complaint_count": 2,  # int, 0 if none
}
```

### Implementation

1. **Stuck diagnosis**: After the existing station lookup (around line 1010+), add:
   - If days_at_station > 2 * station_median → stuck
   - Severity: ratio > 5x = critical, > 3x = high, > 2x = medium, else low
   - Wrap in try/except → None on failure

2. **Violation count**: Query violations table by block+lot (if we have them from the permit):
   ```sql
   SELECT COUNT(*) FROM violations
   WHERE block = %s AND lot = %s AND status != 'closed'
   ```
   - Get block/lot from the permit row
   - Wrap in try/except → 0 on failure

3. **Complaint count**: Same pattern with complaints table:
   ```sql
   SELECT COUNT(*) FROM complaints
   WHERE block = %s AND lot = %s AND status = 'open'
   ```

### Important
- These are ENHANCEMENTS — they must NEVER break the existing function
- Wrap each new field computation in its own try/except → default on failure
- The function must continue to return the existing fields unchanged
- Performance: these are 2 extra simple COUNT queries per permit, acceptable for max_permits=5

## Output Files
- `web/helpers.py` — MODIFY compute_triage_signals() function ONLY

## Do NOT Touch
- web/intelligence_helpers.py (owned by T1-B, doesn't exist yet)
- web/templates/search_results.html (owned by T1-C)
- web/routes_api.py (owned by T1-D)
- Any file in web/templates/ or web/routes_*.py

## DuckDB / Postgres Gotchas
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- BACKEND is "postgres" in prod. Use _PH variable already in the function.
- The function already has _exec() helper — reuse it.

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

# Quick smoke test
python -c "
from web.helpers import compute_triage_signals
signals = compute_triage_signals(permit_number='202301015555')
if signals:
    s = signals[0]
    print('stuck_diagnosis:', s.get('stuck_diagnosis'))
    print('violation_count:', s.get('violation_count'))
    print('complaint_count:', s.get('complaint_count'))
else:
    print('No signals (OK if permit not in local DB)')
"

## Commit
git add web/helpers.py
git commit -m "feat(T1-A): extend triage signals with stuck diagnosis, violations, complaints"
```

---

### Agent T1-B: Create intelligence_helpers.py (THE interface contract)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Create web/intelligence_helpers.py — Sync Wrappers for Intelligence Tools

## Read First
1. src/tools/stuck_permit.py — async def diagnose_stuck_permit(permit_number: str) -> str: at line 606
2. src/tools/cost_of_delay.py — async def calculate_delay_cost(permit_type, monthly_carrying_cost, neighborhood=None, triggers=None) -> str: at line 188
3. src/tools/similar_projects.py — async def similar_projects(permit_type, neighborhood=None, estimated_cost=None, supervisor_district=None, limit=5, return_structured=False) -> str|tuple: at line 207
4. web/helpers.py — def run_async() helper that wraps async calls for Flask

## What to Build

Create `web/intelligence_helpers.py` — synchronous wrapper functions that call the async MCP tools and return structured dicts instead of markdown strings.

### EXACT Interface Contract (T2 and T4 depend on these signatures)

```python
"""Synchronous intelligence wrappers for Flask routes.

These wrap the async MCP tool functions into sync calls with structured
dict returns. Used by analyze(), report, brief, and API endpoints.
All wrappers: try/except → None/[] on failure, 3s timeout, warning logged.
"""

from __future__ import annotations
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def get_stuck_diagnosis_sync(permit_number: str) -> dict | None:
    """Get stuck permit diagnosis as a structured dict.

    Returns:
        {
            "severity": "HIGH",  # str: severity label
            "severity_score": 72,  # int: 0-100 score
            "stuck_stations": [  # list of stuck station dicts
                {
                    "station": "CP-ZOC",
                    "days": 45,
                    "baseline_p50": 12,
                    "status": "STALLED",
                }
            ],
            "interventions": [  # ranked intervention steps
                {"step": 1, "action": "Contact plan checker", "contact": "..."}
            ],
            "permit_number": "202301015555",
            "markdown": "..."  # raw markdown for fallback rendering
        }
        or None on failure/timeout.
    """
    ...


def get_delay_cost_sync(
    permit_type: str,
    monthly_cost: float,
    neighborhood: str | None = None,
) -> dict | None:
    """Get delay cost analysis as a structured dict.

    Returns:
        {
            "daily_cost": 166.67,  # float
            "weekly_cost": 1166.67,  # float
            "monthly_cost": 5000.0,  # float (input)
            "scenarios": [  # best/likely/worst
                {"label": "Best case", "months": 2, "total_cost": 10000},
                {"label": "Likely", "months": 4, "total_cost": 20000},
                {"label": "Worst case", "months": 8, "total_cost": 40000},
            ],
            "mitigation": ["strategy1", "strategy2"],
            "revision_risk": 0.12,  # float 0-1, probability
            "markdown": "..."  # raw markdown
        }
        or None on failure/timeout.
    """
    ...


def get_similar_projects_sync(
    permit_type: str,
    neighborhood: str | None = None,
    cost: float | None = None,
) -> list[dict]:
    """Get similar completed projects as structured dicts.

    Returns:
        [
            {
                "permit_number": "202201234567",
                "description": "Kitchen remodel...",
                "neighborhood": "Mission",
                "duration_days": 120,
                "routing_path": ["PERMIT-CTR", "BLDG", "CP-ZOC"],
                "estimated_cost": 85000,
            },
            ...
        ]
        or [] on failure/timeout.
    """
    ...
```

### Implementation Pattern

```python
import asyncio
from web.helpers import run_async

def get_stuck_diagnosis_sync(permit_number: str) -> dict | None:
    try:
        from src.tools.stuck_permit import diagnose_stuck_permit
        # run_async handles the event loop
        raw_markdown = run_async(diagnose_stuck_permit(permit_number))
        # Parse the markdown into structured data
        return _parse_stuck_diagnosis(raw_markdown, permit_number)
    except Exception as e:
        logger.warning("Stuck diagnosis failed for %s: %s", permit_number, e)
        return None


def _parse_stuck_diagnosis(markdown: str, permit_number: str) -> dict | None:
    """Parse diagnose_stuck_permit markdown output into structured dict."""
    if not markdown:
        return None

    result = {
        "permit_number": permit_number,
        "severity": "UNKNOWN",
        "severity_score": 0,
        "stuck_stations": [],
        "interventions": [],
        "markdown": markdown,
    }

    # Parse severity from markdown (look for "Severity: HIGH" or score patterns)
    # Parse stations, interventions from the structured markdown output
    # Be defensive — the markdown format may vary

    # ... regex/string parsing ...

    return result
```

Use the same pattern for delay cost and similar projects. The key insight: the MCP tools return MARKDOWN strings. You need to parse them into structured dicts. Be defensive with parsing — the markdown format isn't guaranteed.

### run_async Usage

```python
from web.helpers import run_async
# run_async takes a coroutine and runs it synchronously
result = run_async(some_async_function(args))
```

### Timeout

Set a 3-second effective timeout. If run_async doesn't support timeout directly, wrap with asyncio.wait_for:

```python
import asyncio

async def _with_timeout(coro, seconds=3):
    return await asyncio.wait_for(coro, timeout=seconds)

raw = run_async(_with_timeout(diagnose_stuck_permit(pn), seconds=3))
```

## Output Files
- `web/intelligence_helpers.py` (NEW — create this file)

## Do NOT Touch
- web/helpers.py (owned by T1-A)
- web/templates/search_results.html (owned by T1-C)
- web/routes_api.py (owned by T1-D)

## DuckDB / Postgres Gotchas
- Not directly relevant (you're wrapping existing tools), but the underlying tools use DB
- Ensure imports are lazy (inside functions) to avoid circular import issues

## Test
source .venv/bin/activate

# Unit test the module
python -c "
from web.intelligence_helpers import get_stuck_diagnosis_sync, get_delay_cost_sync, get_similar_projects_sync
print('Module imported OK')

# Test with a real-ish permit number (may return None if not in DB)
result = get_stuck_diagnosis_sync('202301015555')
print('stuck_diagnosis:', type(result), result is not None)

result = get_delay_cost_sync('alterations', 5000.0, 'Mission')
print('delay_cost:', type(result), result is not None)

result = get_similar_projects_sync('alterations', 'Mission', 100000)
print('similar_projects:', type(result), len(result))
"

python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/intelligence_helpers.py
git commit -m "feat(T1-B): create intelligence_helpers.py — sync wrappers for stuck/delay/similar tools"
```

---

### Agent T1-C: Update search_results.html

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Update search_results.html to Render Enriched Triage Signals

## Read First
1. web/templates/search_results.html — current search results template
2. web/helpers.py — compute_triage_signals() (starts at line 912) — understand what fields are available
3. docs/DESIGN_TOKENS.md — design system tokens

## What to Build

Update the search results template to display the NEW triage signal fields added by T1-A:
- `stuck_diagnosis` — dict with severity, station, days, ratio (or None)
- `violation_count` — int
- `complaint_count` — int

### Display Rules

For each permit card in search results:

1. **Stuck diagnosis badge** (if stuck_diagnosis is not None):
   - Red badge: "STUCK at [station] — [days] days ([ratio]x median)"
   - Severity colors: critical = red-500, high = amber-500, medium = yellow-500

2. **Violations indicator** (if violation_count > 0):
   - Warning icon + "[N] active violations"
   - Color: amber-400

3. **Complaints indicator** (if complaint_count > 0):
   - Info icon + "[N] open complaints"
   - Color: orange-400

### Template Pattern

The triage signals are passed to the template as a list. Each permit card already has access to signal data. Add the new indicators to the existing card layout:

```jinja2
{% if signal.stuck_diagnosis %}
<div class="flex items-center gap-1 text-xs mt-1">
    <span class="inline-block w-2 h-2 rounded-full bg-{{ 'red' if signal.stuck_diagnosis.severity == 'critical' else 'amber' }}-400"></span>
    <span class="text-{{ 'red' if signal.stuck_diagnosis.severity == 'critical' else 'amber' }}-400 font-medium">
        Stuck at {{ signal.stuck_diagnosis.station }} — {{ signal.stuck_diagnosis.days }}d ({{ signal.stuck_diagnosis.ratio }}x baseline)
    </span>
</div>
{% endif %}

{% if signal.violation_count and signal.violation_count > 0 %}
<span class="text-xs text-amber-400">⚠ {{ signal.violation_count }} active violation{{ 's' if signal.violation_count != 1 }}</span>
{% endif %}

{% if signal.complaint_count and signal.complaint_count > 0 %}
<span class="text-xs text-orange-400">📋 {{ signal.complaint_count }} open complaint{{ 's' if signal.complaint_count != 1 }}</span>
{% endif %}
```

### Graceful Degradation
- If stuck_diagnosis is None → don't render the badge
- If violation_count is 0 or missing → don't render
- If complaint_count is 0 or missing → don't render
- The page must render correctly even if none of these fields exist (backward compat)

## Output Files
- `web/templates/search_results.html` (MODIFY)

## Do NOT Touch
- web/helpers.py (owned by T1-A)
- web/intelligence_helpers.py (owned by T1-B)
- web/routes_api.py (owned by T1-D)

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/templates/search_results.html
git commit -m "feat(T1-C): render stuck diagnosis, violations, complaints in search results"
```

---

### Agent T1-D: Intelligence API Endpoints

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Add Intelligence API Endpoints to routes_api.py

## Read First
1. web/routes_api.py — existing API blueprint (read full file, note patterns)
2. web/intelligence_helpers.py — DOES NOT EXIST YET. T1-B creates it. Use the interface contract below.
3. web/helpers.py — login_required, run_async, _is_rate_limited

## Interface Contract (from T1-B)

```python
from web.intelligence_helpers import (
    get_stuck_diagnosis_sync,  # (permit_number: str) -> dict | None
    get_delay_cost_sync,       # (permit_type: str, monthly_cost: float, neighborhood: str = None) -> dict | None
    get_similar_projects_sync, # (permit_type: str, neighborhood: str = None, cost: float = None) -> list[dict]
)
```

## What to Build

Add 3 HTMX-compatible API endpoints to web/routes_api.py:

### 1. GET /api/intelligence/stuck/<permit_number>
```python
@bp.route("/api/intelligence/stuck/<permit_number>")
def api_stuck_diagnosis(permit_number):
    """Return stuck diagnosis as HTML fragment (HTMX) or JSON."""
    from web.intelligence_helpers import get_stuck_diagnosis_sync

    result = get_stuck_diagnosis_sync(permit_number)
    if not result:
        return '<div class="text-gray-500 text-sm">No stuck diagnosis available</div>'

    if request.headers.get("Accept") == "application/json":
        return jsonify(result)

    # Return HTML fragment for HTMX
    return render_template("fragments/stuck_diagnosis.html", diagnosis=result)
```

### 2. GET /api/intelligence/delay?permit_type=...&monthly_cost=...&neighborhood=...
```python
@bp.route("/api/intelligence/delay")
def api_delay_cost():
    permit_type = request.args.get("permit_type", "alterations")
    monthly_cost = float(request.args.get("monthly_cost", "5000"))
    neighborhood = request.args.get("neighborhood")

    from web.intelligence_helpers import get_delay_cost_sync
    result = get_delay_cost_sync(permit_type, monthly_cost, neighborhood)

    if not result:
        return '<div class="text-gray-500 text-sm">Delay cost unavailable</div>'

    if request.headers.get("Accept") == "application/json":
        return jsonify(result)

    return render_template("fragments/delay_cost.html", delay=result)
```

### 3. GET /api/intelligence/similar?permit_type=...&neighborhood=...&cost=...
```python
@bp.route("/api/intelligence/similar")
def api_similar_projects():
    permit_type = request.args.get("permit_type", "alterations")
    neighborhood = request.args.get("neighborhood")
    cost = float(request.args.get("cost")) if request.args.get("cost") else None

    from web.intelligence_helpers import get_similar_projects_sync
    results = get_similar_projects_sync(permit_type, neighborhood, cost)

    if not results:
        return '<div class="text-gray-500 text-sm">No similar projects found</div>'

    if request.headers.get("Accept") == "application/json":
        return jsonify(results)

    return render_template("fragments/similar_projects.html", projects=results)
```

### 4. Create HTML Fragment Templates

Create 3 minimal fragment templates for HTMX responses:

**web/templates/fragments/stuck_diagnosis.html**
```html
<div class="space-y-2">
    <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-red-400">Severity: {{ diagnosis.severity }}</span>
        {% if diagnosis.severity_score %}
        <span class="text-xs text-gray-400">({{ diagnosis.severity_score }}/100)</span>
        {% endif %}
    </div>
    {% for station in diagnosis.stuck_stations %}
    <div class="text-sm">
        <span class="text-white">{{ station.station }}</span>:
        {{ station.days }} days (baseline: {{ station.baseline_p50 }}d)
    </div>
    {% endfor %}
    {% if diagnosis.interventions %}
    <div class="mt-2 text-sm text-gray-300">
        <strong>Next step:</strong> {{ diagnosis.interventions[0].action }}
    </div>
    {% endif %}
</div>
```

**web/templates/fragments/delay_cost.html**
```html
<div class="space-y-2">
    <div class="text-2xl font-bold text-amber-400">${{ "%.0f"|format(delay.daily_cost) }}/day</div>
    <div class="text-sm text-gray-400">${{ "%.0f"|format(delay.weekly_cost) }}/week · ${{ "%.0f"|format(delay.monthly_cost) }}/month</div>
    {% if delay.scenarios %}
    <div class="mt-2 space-y-1">
        {% for s in delay.scenarios %}
        <div class="flex justify-between text-sm">
            <span class="text-gray-400">{{ s.label }}</span>
            <span class="text-white">{{ s.months }}mo · ${{ "{:,.0f}".format(s.total_cost) }}</span>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</div>
```

**web/templates/fragments/similar_projects.html**
```html
<div class="space-y-3">
    {% for p in projects[:5] %}
    <div class="border-b border-white/10 pb-2">
        <div class="text-sm font-medium text-white">{{ p.description[:80] }}{% if p.description|length > 80 %}...{% endif %}</div>
        <div class="text-xs text-gray-400 mt-1">
            {{ p.neighborhood }} · {{ p.duration_days }}d · ${{ "{:,.0f}".format(p.estimated_cost or 0) }}
        </div>
        {% if p.routing_path %}
        <div class="text-xs text-gray-500 mt-1">{{ p.routing_path | join(' → ') }}</div>
        {% endif %}
    </div>
    {% endfor %}
</div>
```

### Rate Limiting
- These endpoints should NOT require login (they're for HTMX fragments on public pages)
- But DO add basic rate limiting: use `_is_rate_limited` if available, or a simple counter
- No auth required — these are read-only data views

### Ensure fragments/ directory exists
```bash
mkdir -p web/templates/fragments
```

## Output Files
- `web/routes_api.py` (MODIFY — add 3 endpoints)
- `web/templates/fragments/stuck_diagnosis.html` (NEW)
- `web/templates/fragments/delay_cost.html` (NEW)
- `web/templates/fragments/similar_projects.html` (NEW)

## Do NOT Touch
- web/helpers.py (owned by T1-A)
- web/intelligence_helpers.py (owned by T1-B, will exist after merge)
- web/templates/search_results.html (owned by T1-C)

## DuckDB / Postgres Gotchas
- Not directly relevant (API endpoints call intelligence_helpers which calls MCP tools)
- Lazy imports inside route functions to avoid circular imports

## Test
source .venv/bin/activate
mkdir -p web/templates/fragments
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/routes_api.py web/templates/fragments/
git commit -m "feat(T1-D): intelligence API endpoints with HTMX fragment templates"
```

---

## After All 4 Agents Complete

### Merge Ceremony (internal to T1)

Merge agents in order: T1-B → T1-A → T1-C → T1-D

(T1-B first because it creates intelligence_helpers.py which T1-D imports)

```bash
git merge <agent-B-branch> --no-edit
git merge <agent-A-branch> --no-edit
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
5. **SIGNAL DONE:** Push branch, output "T1 COMPLETE — branch: <name>"

```bash
bash scripts/notify.sh terminal-done "T1 intelligence complete"
```
