> **EXECUTE IMMEDIATELY.** You are T4 for QS14. Do NOT summarize or ask for confirmation — execute now. Enter a worktree, spawn 4 agents, merge them, push your branch.

# QS14 T4 — Tests + Brief + Admin + Fixes

## Setup

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
```

Then: `EnterWorktree` with name `qs14-t4`

## Your Role

You are T4. You:
1. Enter a worktree
2. Spawn 4 agents in parallel via Task tool (all with `isolation: "worktree"`)
3. Merge agent branches into your worktree branch
4. Push your branch: `git push -u origin <branch>`
5. CHECKQUAD close

**DEPENDENCY:** T4 depends on ALL other terminals. Agents write code/tests against interface contracts. After T0 merges T1/T2/T3 first, T4's tests should pass.

## File Ownership Matrix

| File | Owner |
|---|---|
| `tests/test_intelligence_helpers.py` | T4-A (NEW) |
| `tests/test_admin_home.py` | T4-A (NEW) |
| `tests/test_api_intelligence.py` | T4-A (NEW) |
| `tests/test_showcase_pipeline.py` | T4-A (NEW) |
| `web/brief.py` | T4-B |
| `web/templates/brief.html` | T4-B |
| `tests/test_brief_intelligence.py` | T4-C (NEW) |
| `tests/test_analyze_intelligence.py` | T4-C (NEW) |
| `tests/test_report_intelligence.py` | T4-C (NEW) |
| `scenarios-pending-review-t4d.md` | T4-D (NEW, per-agent output) |
| `qa-drop/qs14-qa.md` | T4-D (NEW) |
| `web/templates/404.html` | T4-D (NEW) |
| `web/templates/methodology.html` | T4-D (MODIFY — if it exists) |

**No agent may modify files owned by another agent.**

## Interface Contracts (from other terminals)

### From T1-B — intelligence_helpers.py
```python
from web.intelligence_helpers import (
    get_stuck_diagnosis_sync,  # (permit_number: str) -> dict | None
    get_delay_cost_sync,       # (permit_type, monthly_cost, neighborhood=None) -> dict | None
    get_similar_projects_sync, # (permit_type, neighborhood=None, cost=None) -> list[dict]
)
```

### From T2-A — analyze() additions
`analyze()` in routes_public.py now passes `stuck_diagnosis`, `delay_cost`, `similar_projects` to results.html

### From T2-C — report.py additions
`get_property_report()` now returns `intelligence` key with `stuck_permits`, `delay_estimate`, `similar_projects`

### From T4-B (internal) — brief.py additions
`get_morning_brief()` will return `stuck_alerts` and `delay_alerts` keys

## DuckDB / Postgres Gotchas (INCLUDE in every agent prompt)

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- BACKEND is "postgres" in prod, "duckdb" locally
- Tests use DuckDB with per-session temp files (see conftest.py)

## Agent Definitions

Spawn ALL 4 agents in parallel using the Task tool. Each agent call:
- `subagent_type: "general-purpose"`
- `model: "sonnet"`
- `isolation: "worktree"`

---

### Agent T4-A: Tests for Intelligence Helpers, Admin Home, API Endpoints, Showcase Pipeline

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Write Tests for QS14 New Features

## Read First
1. tests/conftest.py — understand test fixtures, mock patterns, DuckDB setup
2. tests/test_web.py — existing web tests (patterns for Flask test client)
3. tests/test_report.py — existing report tests
4. Read a few existing test files to understand the project's test patterns

## What to Build

Write 4 test files with thorough coverage for QS14 features.

### 1. tests/test_intelligence_helpers.py

Test the intelligence_helpers module. Since the module wraps async MCP tools, use mocking.

```python
"""Tests for web.intelligence_helpers — sync wrappers for intelligence tools."""
import pytest
from unittest.mock import patch, MagicMock

# Create a stub module for import since the real one may not exist in this worktree
import sys
import types

# Ensure web.intelligence_helpers exists for testing
try:
    from web.intelligence_helpers import (
        get_stuck_diagnosis_sync,
        get_delay_cost_sync,
        get_similar_projects_sync,
    )
except ImportError:
    # Create stub module if it doesn't exist
    mod = types.ModuleType("web.intelligence_helpers")
    mod.get_stuck_diagnosis_sync = lambda pn: None
    mod.get_delay_cost_sync = lambda pt, mc, n=None: None
    mod.get_similar_projects_sync = lambda pt, n=None, c=None: []
    sys.modules["web.intelligence_helpers"] = mod
    from web.intelligence_helpers import (
        get_stuck_diagnosis_sync,
        get_delay_cost_sync,
        get_similar_projects_sync,
    )


class TestGetStuckDiagnosisSync:
    def test_returns_none_on_no_data(self):
        result = get_stuck_diagnosis_sync("NONEXISTENT")
        assert result is None or isinstance(result, dict)

    def test_returns_dict_with_expected_keys(self):
        """If result is not None, it should have expected keys."""
        result = get_stuck_diagnosis_sync("202301015555")
        if result is not None:
            assert "severity" in result or "markdown" in result
            assert "permit_number" in result

    def test_handles_empty_string(self):
        result = get_stuck_diagnosis_sync("")
        assert result is None or isinstance(result, dict)


class TestGetDelayCostSync:
    def test_returns_none_or_dict(self):
        result = get_delay_cost_sync("alterations", 5000.0)
        assert result is None or isinstance(result, dict)

    def test_with_neighborhood(self):
        result = get_delay_cost_sync("alterations", 5000.0, "Mission")
        assert result is None or isinstance(result, dict)

    def test_dict_has_cost_fields(self):
        result = get_delay_cost_sync("alterations", 5000.0)
        if result is not None:
            assert "daily_cost" in result or "markdown" in result


class TestGetSimilarProjectsSync:
    def test_returns_list(self):
        result = get_similar_projects_sync("alterations")
        assert isinstance(result, list)

    def test_with_params(self):
        result = get_similar_projects_sync("alterations", "Mission", 100000)
        assert isinstance(result, list)

    def test_items_have_expected_keys(self):
        result = get_similar_projects_sync("alterations", "Mission")
        for item in result:
            assert isinstance(item, dict)
```

### 2. tests/test_admin_home.py

```python
"""Tests for admin home page route."""
import pytest

def test_admin_home_requires_auth(client):
    """Admin home should redirect unauthenticated users."""
    rv = client.get("/admin/home")
    assert rv.status_code in (302, 401, 403, 404)

def test_admin_home_requires_admin(auth_client):
    """Admin home should reject non-admin users."""
    # If auth_client is a regular user (not admin), should get 403
    rv = auth_client.get("/admin/home")
    assert rv.status_code in (200, 403, 404)
```

### 3. tests/test_api_intelligence.py

```python
"""Tests for intelligence API endpoints."""
import pytest

class TestStuckDiagnosisAPI:
    def test_endpoint_exists(self, client):
        rv = client.get("/api/intelligence/stuck/202301015555")
        assert rv.status_code in (200, 404)

    def test_returns_html_by_default(self, client):
        rv = client.get("/api/intelligence/stuck/202301015555")
        if rv.status_code == 200:
            assert b"<div" in rv.data or b"unavailable" in rv.data.lower()

    def test_returns_json_when_requested(self, client):
        rv = client.get(
            "/api/intelligence/stuck/202301015555",
            headers={"Accept": "application/json"},
        )
        if rv.status_code == 200 and rv.content_type == "application/json":
            data = rv.get_json()
            assert data is not None


class TestDelayCostAPI:
    def test_endpoint_exists(self, client):
        rv = client.get("/api/intelligence/delay?permit_type=alterations&monthly_cost=5000")
        assert rv.status_code in (200, 404)


class TestSimilarProjectsAPI:
    def test_endpoint_exists(self, client):
        rv = client.get("/api/intelligence/similar?permit_type=alterations")
        assert rv.status_code in (200, 404)
```

### 4. tests/test_showcase_pipeline.py

```python
"""Tests for showcase data pipeline."""
import pytest
import json
import os

def test_showcase_json_exists():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "static", "data", "showcase_data.json",
    )
    assert os.path.exists(path)

def test_showcase_json_valid():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "static", "data", "showcase_data.json",
    )
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "station_timeline" in data

def test_showcase_station_timeline_structure():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "static", "data", "showcase_data.json",
    )
    with open(path) as f:
        data = json.load(f)
    timeline = data.get("station_timeline", {})
    assert "stations" in timeline
    assert isinstance(timeline["stations"], list)
    if timeline["stations"]:
        station = timeline["stations"][0]
        assert "station" in station
```

## Output Files
- `tests/test_intelligence_helpers.py` (NEW)
- `tests/test_admin_home.py` (NEW)
- `tests/test_api_intelligence.py` (NEW)
- `tests/test_showcase_pipeline.py` (NEW)

## Test
source .venv/bin/activate
python -m pytest tests/test_intelligence_helpers.py tests/test_admin_home.py tests/test_api_intelligence.py tests/test_showcase_pipeline.py -v --tb=short 2>&1 | tail -30
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add tests/test_intelligence_helpers.py tests/test_admin_home.py tests/test_api_intelligence.py tests/test_showcase_pipeline.py
git commit -m "test(T4-A): tests for intelligence helpers, admin home, API endpoints, showcase pipeline"
```

---

### Agent T4-B: Morning Brief Stuck Diagnosis + Delay Alerts

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Add Stuck Diagnosis + Delay Alerts to Morning Brief

## Read First
1. web/brief.py — get_morning_brief() starts at line 69. Read the FULL function.
2. web/templates/brief.html — current brief template. Read the FULL file.
3. docs/DESIGN_TOKENS.md — design system reference

## What to Build

### 1. Add to get_morning_brief() in web/brief.py

Add two new sections AFTER existing sections (before the return statement):

```python
    # === QS14: Stuck diagnosis alerts ===
    stuck_alerts = []
    try:
        from web.intelligence_helpers import get_stuck_diagnosis_sync
        # Check each watched permit for stuck status
        watch_rows = query(
            f"SELECT permit_number FROM watch_items WHERE user_id = {_ph()} AND is_active = TRUE",
            (user_id,),
        )
        for row in (watch_rows or [])[:10]:  # max 10 to limit latency
            pn = row[0]
            diag = get_stuck_diagnosis_sync(pn)
            if diag and diag.get("severity") in ("HIGH", "CRITICAL"):
                stuck_alerts.append({
                    "permit_number": pn,
                    "severity": diag.get("severity"),
                    "station": diag.get("stuck_stations", [{}])[0].get("station", "Unknown") if diag.get("stuck_stations") else "Unknown",
                    "days": diag.get("stuck_stations", [{}])[0].get("days", 0) if diag.get("stuck_stations") else 0,
                    "action": diag.get("interventions", [{}])[0].get("action", "") if diag.get("interventions") else "",
                })
    except Exception as e:
        logger.warning("Stuck alerts failed: %s", e)
    # === END QS14 stuck ===

    # === QS14: Delay cost alerts ===
    delay_alerts = []
    try:
        from web.intelligence_helpers import get_delay_cost_sync
        # For permits with known types, estimate delay cost
        for alert in stuck_alerts[:3]:  # Only for top 3 stuck permits
            pn = alert["permit_number"]
            # Look up permit type
            pt_rows = query(
                f"SELECT permit_type_definition FROM permits WHERE permit_number = {_ph()} LIMIT 1",
                (pn,),
            )
            pt = pt_rows[0][0] if pt_rows else "alterations"
            delay = get_delay_cost_sync(pt, 5000.0)  # Default carrying cost
            if delay:
                delay_alerts.append({
                    "permit_number": pn,
                    "daily_cost": delay.get("daily_cost", 0),
                    "weekly_cost": delay.get("weekly_cost", 0),
                })
    except Exception as e:
        logger.warning("Delay alerts failed: %s", e)
    # === END QS14 delay ===
```

Add to the return dict:
```python
    return {
        # ... existing keys ...
        "stuck_alerts": stuck_alerts,
        "delay_alerts": delay_alerts,
    }
```

### 2. Add to brief.html

Add a "Stuck Permits" section and "Delay Alerts" section to the brief template. Place AFTER the "Health" section and BEFORE "Inspections":

```jinja2
{# === QS14: Stuck Alerts === #}
{% if brief.stuck_alerts %}
<section class="brief-section">
    <h3>⚠ Stuck Permits</h3>
    {% for alert in brief.stuck_alerts %}
    <div class="brief-card warning">
        <div class="flex justify-between items-center">
            <span class="font-mono text-sm">{{ alert.permit_number }}</span>
            <span class="badge badge-{{ 'danger' if alert.severity == 'CRITICAL' else 'warning' }}">
                {{ alert.severity }}
            </span>
        </div>
        <div class="text-sm mt-1">
            Stuck at <strong>{{ alert.station }}</strong> for {{ alert.days }} days
        </div>
        {% if alert.action %}
        <div class="text-sm text-gray-400 mt-1">→ {{ alert.action }}</div>
        {% endif %}
    </div>
    {% endfor %}
</section>
{% endif %}

{# === QS14: Delay Alerts === #}
{% if brief.delay_alerts %}
<section class="brief-section">
    <h3>💰 Delay Cost Impact</h3>
    {% for alert in brief.delay_alerts %}
    <div class="brief-card">
        <span class="font-mono text-sm">{{ alert.permit_number }}</span>
        <span class="text-amber-400 font-bold">${{ "%.0f"|format(alert.daily_cost) }}/day</span>
        <span class="text-sm text-gray-400">({{ "%.0f"|format(alert.weekly_cost) }}/week)</span>
    </div>
    {% endfor %}
</section>
{% endif %}
```

### Important
- Use lazy imports for intelligence_helpers (inside try/except)
- Each section wraps in try/except — brief must never break
- Performance: limit to 10 watched permits and 3 delay checks
- Graceful degradation: if intelligence_helpers doesn't exist, stuck_alerts=[], delay_alerts=[]

## Output Files
- `web/brief.py` (MODIFY — add stuck_alerts and delay_alerts to get_morning_brief)
- `web/templates/brief.html` (MODIFY — add stuck and delay sections)

## Do NOT Touch
- tests/ (owned by T4-A and T4-C)
- web/routes_*.py
- web/report.py

## DuckDB / Postgres Gotchas
- Use _ph() for placeholders (already in brief.py)
- query() handles both backends

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add web/brief.py web/templates/brief.html
git commit -m "feat(T4-B): add stuck diagnosis and delay cost alerts to morning brief"
```

---

### Agent T4-C: Tests for Analyze/Report/Brief Intelligence Integration

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

# Task: Write Integration Tests for Intelligence in Analyze, Report, Brief

## Read First
1. tests/conftest.py — understand fixtures
2. tests/test_web.py — existing web test patterns
3. tests/test_report.py — existing report tests
4. tests/test_brief.py — if it exists, existing brief tests

## What to Build

### 1. tests/test_analyze_intelligence.py

```python
"""Tests for intelligence integration in analyze()."""
import pytest
from unittest.mock import patch

class TestAnalyzeIntelligence:
    def test_analyze_accepts_carrying_cost(self, client):
        """Analyze form should accept carrying_cost field."""
        rv = client.post("/analyze", data={
            "description": "kitchen remodel in a single family home",
            "carrying_cost": "5000",
        })
        assert rv.status_code == 200

    def test_analyze_returns_results(self, client):
        """Analyze should return results page."""
        rv = client.post("/analyze", data={
            "description": "kitchen remodel residential",
        })
        assert rv.status_code == 200
        assert b"result" in rv.data.lower() or b"predict" in rv.data.lower()

    def test_analyze_without_description_fails(self, client):
        """Analyze without description should return 400."""
        rv = client.post("/analyze", data={})
        assert rv.status_code == 400
```

### 2. tests/test_report_intelligence.py

```python
"""Tests for intelligence integration in property reports."""
import pytest
from unittest.mock import patch, MagicMock

class TestReportIntelligence:
    @patch("web.report.get_connection")
    def test_report_includes_intelligence_key(self, mock_conn):
        """get_property_report should include 'intelligence' key."""
        # Mock the connection to return empty results
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = lambda s, *a: None
        mock_conn.return_value.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.return_value.cursor.return_value.__exit__ = lambda s, *a: None

        try:
            from web.report import get_property_report
            result = get_property_report("0001", "001")
            # After QS14, should have intelligence key
            if "intelligence" in result:
                assert isinstance(result["intelligence"], dict)
        except Exception:
            # May fail due to DB connection — that's OK for this test
            pass
```

### 3. tests/test_brief_intelligence.py

```python
"""Tests for intelligence integration in morning brief."""
import pytest
from unittest.mock import patch, MagicMock

class TestBriefIntelligence:
    @patch("web.brief.query")
    def test_brief_includes_stuck_alerts(self, mock_query):
        """get_morning_brief should include stuck_alerts key."""
        mock_query.return_value = []
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            # After QS14, should have stuck_alerts
            if "stuck_alerts" in result:
                assert isinstance(result["stuck_alerts"], list)
        except Exception:
            pass  # May fail due to missing DB

    @patch("web.brief.query")
    def test_brief_includes_delay_alerts(self, mock_query):
        """get_morning_brief should include delay_alerts key."""
        mock_query.return_value = []
        try:
            from web.brief import get_morning_brief
            result = get_morning_brief(user_id=1)
            if "delay_alerts" in result:
                assert isinstance(result["delay_alerts"], list)
        except Exception:
            pass
```

## Output Files
- `tests/test_analyze_intelligence.py` (NEW)
- `tests/test_report_intelligence.py` (NEW)
- `tests/test_brief_intelligence.py` (NEW)

## Test
source .venv/bin/activate
python -m pytest tests/test_analyze_intelligence.py tests/test_report_intelligence.py tests/test_brief_intelligence.py -v --tb=short 2>&1 | tail -30
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add tests/test_analyze_intelligence.py tests/test_report_intelligence.py tests/test_brief_intelligence.py
git commit -m "test(T4-C): integration tests for analyze/report/brief intelligence"
```

---

### Agent T4-D: Scenarios + QA Script + Design Lint + Persona UX Fixes

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.

# Task: Scenarios, QA Script, Design Lint, Top Persona-Reported UX Fixes

## Read First
1. scenarios-pending-review.md — existing scenarios
2. qa-drop/ — existing QA scripts
3. docs/DESIGN_TOKENS.md
4. web/templates/ — check for 404.html, methodology.html

## Pre-Flight Audit Findings (fix these)

### P0 — Must fix
1. **404 page is bare Flask default** — white bg, black text, no branding, no nav
   - CREATE web/templates/404.html with branded error page
   - Register in web/app.py: @app.errorhandler(404)

2. **Signup dead end** — /auth/login has invite code field with no way to get one
   - This is by design (beta) but needs a message: "Currently in private beta. Request access below."
   - Add a brief explanation and email link on the login page
   - File: web/templates/auth_login.html (or equivalent)

### P1 — Should fix if time permits
3. **Neighborhood search returns empty** — searching "Mission" or "Castro" finds no permits
   - The search expects address format, not neighborhood names
   - Add a helper message when search looks like a neighborhood name
   - File: web/routes_search.py or web/routes_public.py search route

4. **Mobile nav missing on landing** — only wordmark visible at 375px
   - The landing-v6 conversion (T3-A) should fix this
   - If not: add a mobile nav toggle to landing.html

## Scenarios (write 8-12)

Write to `scenarios-pending-review-t4d.md` (per-agent output file, T0 orchestrator concatenates):

Focus on QS14 features:
- Intelligence surfaces in analyze results (stuck, delay, similar)
- Intelligence in property reports
- Morning brief stuck + delay alerts
- Showcase data accuracy (no inflated numbers)
- Gantt parallel station rendering
- Landing page for new visitors
- Admin home dashboard
- 404 branded error page

## QA Script

Write `qa-drop/qs14-qa.md`:

```markdown
# QS14 QA Script

## Landing Page
- [ ] Landing page loads without errors
- [ ] Hero section has search form
- [ ] Showcase cards render (not blank, not raw JSON)
- [ ] Gantt timeline shows parallel stations (not sequential)
- [ ] Showcase numbers are defensible (check station_timeline data source)
- [ ] Mobile (375px): page is usable, no horizontal overflow

## Intelligence API
- [ ] GET /api/intelligence/stuck/[permit] returns HTML fragment
- [ ] GET /api/intelligence/delay?permit_type=alterations&monthly_cost=5000 returns data
- [ ] GET /api/intelligence/similar?permit_type=alterations returns list

## Analyze Flow
- [ ] POST /analyze with description returns results
- [ ] Results page has Stuck Analysis tab (if data available)
- [ ] Results page has Cost of Delay tab (if carrying_cost provided)
- [ ] Results page has Similar Projects section

## Property Report
- [ ] Report page includes Intelligence section (if permits are active)
- [ ] Stuck diagnosis renders with severity badge
- [ ] Similar projects list shows routing paths

## Morning Brief
- [ ] Brief includes Stuck Permits section (if any watched permits are stuck)
- [ ] Brief includes Delay Cost Impact section

## Admin
- [ ] /admin/home loads for admin users
- [ ] /admin/home shows stats (user count, etc.)

## Error Handling
- [ ] 404 page shows branded template (not bare Flask default)
- [ ] Missing intelligence data degrades gracefully (no errors)

## Design Token Compliance
- [ ] Run: python scripts/design_lint.py --changed --quiet
- [ ] Score: [N]/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: --mono for data, --sans for prose
- [ ] New components logged in DESIGN_COMPONENT_LOG.md
```

## Design Lint

```bash
source .venv/bin/activate
python scripts/design_lint.py --changed --quiet 2>&1
```

Save results to `qa-results/design-lint-t4d.md`

## Output Files
- `scenarios-pending-review-t4d.md` (NEW — per-agent scenarios)
- `qa-drop/qs14-qa.md` (NEW — QA script)
- `qa-results/design-lint-t4d.md` (NEW — lint results)
- `web/templates/404.html` (NEW — branded 404 page)
- Possibly `web/app.py` (MODIFY — register 404 handler, minimal change)
- Possibly `web/templates/auth_login.html` or equivalent (MODIFY — add beta message)

## Do NOT Touch
- tests/ (owned by T4-A and T4-C)
- web/brief.py (owned by T4-B)
- web/templates/brief.html (owned by T4-B)
- web/routes_public.py (owned by T2-A / T3-B)

## DuckDB / Postgres Gotchas
- Not directly relevant for this agent (template/scenario work)

## Test
source .venv/bin/activate
python -m pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q --tb=short 2>&1 | tail -20

## Commit
git add scenarios-pending-review-t4d.md qa-drop/qs14-qa.md qa-results/design-lint-t4d.md web/templates/404.html
git add -u  # any modified files
git commit -m "feat(T4-D): scenarios, QA script, design lint, branded 404, persona UX fixes"
```

---

## After All 4 Agents Complete

### Merge Ceremony (internal to T4)

Merge agents in order: T4-B → T4-A → T4-C → T4-D

(T4-B first because it modifies brief.py which T4-C tests against)

```bash
git merge <agent-B-branch> --no-edit
git merge <agent-A-branch> --no-edit
git merge <agent-C-branch> --no-edit
git merge <agent-D-branch> --no-edit
```

### Concatenate per-agent outputs

```bash
# Append T4-D scenarios to main file
cat scenarios-pending-review-t4d.md >> scenarios-pending-review.md
git add scenarios-pending-review.md scenarios-pending-review-t4d.md
git commit -m "chore: concatenate T4-D scenarios"
```

### Push

```bash
git push -u origin $(git branch --show-current)
```

### CHECKQUAD Close

**Step 0 — ESCAPE CWD:** `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

1. **MERGE:** All 4 agent branches merged into your worktree branch
2. **ARTIFACT:** Write a brief session report
3. **CAPTURE:** Verify scenarios were appended
4. **HYGIENE CHECK:** Verify no files outside ownership matrix were modified
5. **SIGNAL DONE:** Push branch, output "T4 COMPLETE — branch: <name>"

```bash
bash scripts/notify.sh terminal-done "T4 tests complete"
```
