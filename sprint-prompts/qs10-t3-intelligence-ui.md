# QS10 Terminal 3: Intelligence Tool Web UI

**Sprint:** QS10 — Intelligence Tool Standalone Pages
**Chief Task:** #360
**Theme:** Build 4 standalone web tool pages surfacing the intelligence API endpoints already live in `web/routes_api.py`.
**Agents:** 4 (3A, 3B, 3C, 3D) — run in parallel, zero file overlap except `web/routes_search.py`
**Merge order within T3:** A → B → C → D (for `routes_search.py` ordering)

---

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T3 start: $(git rev-parse --short HEAD)"
```

---

## File Ownership

| Agent | Owned Files | Action |
|-------|-------------|--------|
| 3A | `web/templates/tools/station_predictor.html` | CREATE |
| 3A | `tests/test_station_predictor_ui.py` | CREATE |
| 3A | `web/routes_search.py` | APPEND route at EOF |
| 3B | `web/templates/tools/stuck_permit.html` | CREATE |
| 3B | `tests/test_stuck_permit_ui.py` | CREATE |
| 3B | `web/routes_search.py` | APPEND route at EOF (after 3A) |
| 3C | `web/templates/tools/what_if.html` | CREATE |
| 3C | `tests/test_what_if_ui.py` | CREATE |
| 3C | `web/routes_search.py` | APPEND route at EOF (after 3B) |
| 3D | `web/templates/tools/cost_of_delay.html` | CREATE |
| 3D | `tests/test_cost_of_delay_ui.py` | CREATE |
| 3D | `web/routes_search.py` | APPEND route at EOF (after 3C) |

**READ ONLY — DO NOT MODIFY:**
- `web/routes_api.py` — API endpoints already exist here, just call them
- `web/app.py`
- `src/server.py`
- `scripts/*.py`
- `CLAUDE.md`
- `CHANGELOG.md`

---

## Standard Agent Preamble (included verbatim in every agent prompt below)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes of starting.
- DESCOPE RULE: If you cannot complete a task, mark it BLOCKED with reason. Do NOT silently reduce scope.
- READ ONLY FILES: web/routes_api.py, web/app.py, src/server.py, scripts/*.py, CLAUDE.md, CHANGELOG.md
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t3-sprint88.md (write 2-5 scenarios for your feature)
  * CHANGELOG-t3-sprint88.md (your section only)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. DESIGN TOKEN COMPLIANCE — run: python scripts/design_lint.py --changed --quiet
5. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
6. CHECKQUAD — write your session artifact (see CHECKQUAD section at end of your task)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit for DDL init
- CRON_WORKER env var needed for cron endpoint tests
```

---

## Design Requirements (all 4 agents)

All templates MUST follow these requirements. Non-negotiable.

**Read `docs/DESIGN_TOKENS.md` before writing any template.**

### Theme
- Dark obsidian background: `--obsidian` (`#0a0a0f`)
- Glass cards for content containers
- Ghost CTAs for all primary actions
- No hardcoded hex colors — all values via CSS custom properties from DESIGN_TOKENS.md

### Font rules
- `--mono` for: permit numbers, addresses, data values, inputs, placeholders, section labels, CTAs, timestamps
- `--sans` for: page titles, headings, body copy, descriptions, form labels
- NEVER use `--font-display` or `--font-body` — those are legacy aliases that cause lint failures

### Layout
- `{% include "fragments/head_obsidian.html" %}` in `<head>` — provides fonts, CSS links, CSRF meta tag, HTMX configRequest listener
- `{% include "fragments/nav.html" %}` for site navigation
- `.obs-container` (max-width 1000px, margin auto, padding 0 24px) for page content
- Mobile responsive at 375px viewport

### Forms
- HTMX for submission: `hx-post` or `hx-get`, `hx-target="#results"`, `hx-swap="innerHTML"`
- All POST forms MUST include: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
- Note: HTMX CSRF is handled globally by the configRequest listener in head_obsidian.html, but POST forms still need the hidden input for non-HTMX fallback
- Loading state: `hx-indicator` with a spinner element
- Results area: `<div id="results" class="results-area"></div>` below the form

### Auth handling
The API endpoints require authentication. The route you add to `web/routes_search.py` should redirect to login if the user is not authenticated. Check `g.user` (set by `before_request` in `web/app.py`) or use the `login_required` decorator from `web/helpers.py`.

### Template structure (standalone page, no base template extension)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>[Tool Name] — sfpermits.ai</title>
    {% include "fragments/head_obsidian.html" %}
    <script src="https://unpkg.com/htmx.org@1.9.12" nonce="{{ csp_nonce }}"></script>
    <style nonce="{{ csp_nonce }}">
        /* page-specific styles using DESIGN_TOKENS.md custom properties only */
    </style>
</head>
<body>
    {% include "fragments/nav.html" %}
    <main>
        <div class="obs-container">
            <!-- page content -->
        </div>
    </main>
</body>
</html>
```

### Route pattern for `web/routes_search.py`
Add your route at the END of `web/routes_search.py` using this pattern:

```python
# ---------------------------------------------------------------------------
# [Tool Name] — /tools/[tool-slug] (Sprint QS10-T3-[agent])
# ---------------------------------------------------------------------------

@bp.route("/tools/[tool-slug]")
def tools_[tool_function_name]():
    """[One-line description]."""
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))
    return render_template("tools/[template_name].html")
```

Make sure `web/templates/tools/` directory exists before writing the template. If it doesn't exist, create it (write your template file — Flask will create parent dirs, but you may need to mkdir).

---

## API Contracts (from `web/routes_api.py` — READ ONLY)

### GET /api/predict-next/<permit_number>
Returns:
```json
{"permit_number": "...", "result": "...markdown..."}
```
Or: `{"error": "..."}` with 401 or 500.

### GET /api/stuck-permit/<permit_number>
Returns:
```json
{"permit_number": "...", "result": "...markdown playbook..."}
```
Or: `{"error": "..."}` with 401 or 500.

### POST /api/what-if
Body (JSON):
```json
{
  "base_description": "string (required)",
  "variations": [{"label": "string", "description": "string"}]
}
```
Returns: `{"result": "...markdown comparison table..."}` or `{"error": "..."}`.

### POST /api/delay-cost
Body (JSON):
```json
{
  "permit_type": "string (required, e.g. 'adu', 'restaurant')",
  "monthly_carrying_cost": 5000.0,
  "neighborhood": "string (optional)",
  "triggers": ["string", ...] (optional)
}
```
Returns: `{"result": "...markdown cost breakdown..."}` or `{"error": "..."}`.

**Important:** All 4 endpoints require authentication (`user_id` in session). They return 401 if not logged in. Your pages must handle the 401 case gracefully (show login prompt or redirect).

---

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent 3A: Station Predictor

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes of starting.
- DESCOPE RULE: If you cannot complete a task, mark it BLOCKED with reason. Do NOT silently reduce scope.
- READ ONLY FILES: web/routes_api.py, web/app.py, src/server.py, scripts/*.py, CLAUDE.md, CHANGELOG.md
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t3-sprint88.md (write 2-5 scenarios for your feature)
  * CHANGELOG-t3-sprint88.md (your section only)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. DESIGN TOKEN COMPLIANCE — run: python scripts/design_lint.py --changed --quiet
5. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
6. CHECKQUAD — write your session artifact (see CHECKQUAD section below)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit for DDL init
- CRON_WORKER env var needed for cron endpoint tests

## YOUR TASK: Station Predictor page — /tools/station-predictor

### File Ownership (3A)
- web/templates/tools/station_predictor.html (CREATE)
- tests/test_station_predictor_ui.py (CREATE)
- web/routes_search.py (APPEND route at EOF — do NOT touch existing content)

### Read First
1. docs/DESIGN_TOKENS.md — full file (mandatory before any template work)
2. web/routes_api.py lines 760-795 — the /api/predict-next/<permit_number> endpoint signature and return shape
3. web/routes_search.py — last 40 lines (understand EOF structure before appending)
4. web/templates/fragments/head_obsidian.html — understand what it provides
5. web/templates/fragments/nav.html — understand the nav include
6. web/templates/permit_prep.html — reference for page structure pattern (but DO NOT copy its colors — it uses legacy tokens)
7. tests/test_sprint58c_methodology_ui.py — reference for template-string test pattern

### Build

#### Step 1: Create tools directory if needed
```bash
mkdir -p /Users/timbrenneman/AIprojects/sf-permits-mcp/web/templates/tools
```

#### Step 2: Create web/templates/tools/station_predictor.html

This is a standalone page (no base template extension). Build it from scratch following the design requirements.

**Page purpose:** User enters a permit number, clicks "Predict Next Stations", sees the predicted review sequence returned as formatted markdown.

**Page structure:**
- Page header: h1 "Station Predictor", subtitle "See the likely next review stations for any active SF permit."
- Input form:
  - Text input for permit number (monospace font, obsidian-themed search input style)
  - Submit button "Predict next stations →" (ghost CTA or action-btn)
  - HTMX: hx-get="/api/predict-next/" + permit number (build URL via JS before submit, or use hx-vals), hx-target="#results"
  - Since this is a GET endpoint with a URL parameter (not a body), use JavaScript to build the URL on submit rather than hx-get directly. Pattern: intercept the form submit event, read the input value, call fetch('/api/predict-next/' + permitNumber) directly, then render the result markdown into #results.
  - Loading indicator: a spinner or "Analyzing..." text with htmx-indicator class
- Results area: <div id="results" class="results-area glass-card"></div> — hidden until populated
- Result rendering: parse the JSON response, render result.result (markdown) as HTML using marked.js or a simple <pre> fallback. The API returns markdown text.
- Empty state: show hint text in results area "Enter a permit number above to see predicted routing."
- Error state: show the error message from the API response

**Design tokens to use:**
- Background: var(--obsidian) on body, var(--obsidian-mid) on cards
- Text: var(--text-primary) for headings/values, var(--text-secondary) for labels/descriptions
- Accent: var(--accent) for focus states, hover text
- Input: follow search-input pattern from DESIGN_TOKENS.md §5
- Card: follow glass-card pattern from DESIGN_TOKENS.md §5
- Font: --mono for permit number input, labels like "PERMIT NUMBER"; --sans for page title, description, error messages
- No hardcoded hex colors

**CSRF note:** This page calls a GET endpoint via JavaScript fetch, not a POST form, so no csrf_token hidden input needed. But include head_obsidian.html which sets the csrf-token meta tag.

**Auth handling:** If fetch returns 401, show a message: "Please log in to use this tool." with a link to /auth/login.

**Mobile:** At 375px, form inputs full-width, button full-width below input.

#### Step 3: Append route to web/routes_search.py
Open the file, go to the very end, and APPEND (do not modify existing content):

```python
# ---------------------------------------------------------------------------
# Station Predictor — /tools/station-predictor (Sprint QS10-T3-3A)
# ---------------------------------------------------------------------------

@bp.route("/tools/station-predictor")
def tools_station_predictor():
    """Station Predictor: predicted next review stations for a permit."""
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))
    return render_template("tools/station_predictor.html")
```

#### Step 4: Create tests/test_station_predictor_ui.py

Write template-string tests (no Jinja rendering, no Flask test client needed):

```python
\"\"\"Tests for web/templates/tools/station_predictor.html.

Template-string tests — reads the file and asserts structural requirements.
No Flask test client or Jinja rendering needed.
\"\"\"
import os

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/station_predictor.html"
)

def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestStationPredictorTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        \"\"\"Template file exists and is non-empty.\"\"\"
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        \"\"\"Template includes the obsidian head fragment.\"\"\"
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        \"\"\"Template includes site navigation.\"\"\"
        assert 'nav.html' in self.html

    def test_page_title_station_predictor(self):
        \"\"\"Page title references Station Predictor.\"\"\"
        assert 'Station Predictor' in self.html

    def test_results_div_present(self):
        \"\"\"Results target div exists with id=results.\"\"\"
        assert 'id="results"' in self.html

    def test_predict_next_api_endpoint(self):
        \"\"\"Template references the predict-next API endpoint.\"\"\"
        assert 'predict-next' in self.html or 'api/predict-next' in self.html

    def test_no_hardcoded_hex_colors(self):
        \"\"\"Template uses CSS custom properties, not hardcoded hex values in style blocks.\"\"\"
        import re
        # Find hex colors in inline style blocks only (not in comments or strings)
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            # Remove comment lines
            block_no_comments = re.sub(r'/\\*.*?\\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors found in style block: {hex_in_values}"

    def test_mono_font_for_input(self):
        \"\"\"Input or permit number element uses --mono font.\"\"\"
        assert '--mono' in self.html

    def test_mobile_viewport_meta(self):
        \"\"\"Template has viewport meta tag for mobile.\"\"\"
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        \"\"\"Template handles 401 / unauthenticated state.\"\"\"
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()
```

Also add a test for the route in the same file:

```python
class TestStationPredictorRoute:
    \"\"\"Route-level tests via Flask test client.\"\"\"

    def test_route_redirects_unauthenticated(self, client):
        \"\"\"GET /tools/station-predictor redirects to login if not authenticated.\"\"\"
        rv = client.get("/tools/station-predictor")
        assert rv.status_code in (302, 301)

    def test_route_renders_for_authenticated_user(self, authed_client):
        \"\"\"GET /tools/station-predictor returns 200 for authenticated user.\"\"\"
        rv = authed_client.get("/tools/station-predictor")
        assert rv.status_code == 200
        assert b'Station Predictor' in rv.data
```

For the route tests, add fixtures at the top of the file:

```python
import pytest
from web.app import app, _rate_buckets

@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()

@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()
```

Note: The authed_client test may fail if the route checks g.user (set by before_request) rather than session['user_id']. If so, mark it xfail with reason="g.user requires full before_request chain" and keep the redirect test passing.

### Test
```bash
source .venv/bin/activate
pytest tests/test_station_predictor_ui.py -v --tb=short
# Also run full suite to catch regressions
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -10
```

Fix any failures. If the authed_client route test fails due to g.user vs session isolation, xfail it rather than deleting it.

### Design Token Compliance
```bash
python scripts/design_lint.py --changed --quiet
```
Record score in your CHECKQUAD artifact. Target: 4/5 or higher.

### Scenarios
Write 2-5 scenarios to scenarios-t3-sprint88.md (create if it doesn't exist):

Use exactly this format:
## SUGGESTED SCENARIO: [short descriptive name]
**Source:** station_predictor.html / tools_station_predictor route
**User:** expediter | architect
**Starting state:** [what's true before the action]
**Goal:** [what the user is trying to accomplish]
**Expected outcome:** [success criteria — no routes, no UI specifics, no colors]
**Edge cases seen in code:** [optional]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

### CHANGELOG-t3-sprint88.md
Write your section:
```
## Agent 3A — Station Predictor UI
- Added /tools/station-predictor page (web/templates/tools/station_predictor.html)
- Added tools_station_predictor route to web/routes_search.py
- Added tests/test_station_predictor_ui.py (N tests)
- Design lint score: N/5
```

### CHECKQUAD
Write a session artifact summary:
```
## CHECKQUAD — Agent 3A (Station Predictor)

### Shipped
- web/templates/tools/station_predictor.html (created)
- web/routes_search.py (route appended at EOF)
- tests/test_station_predictor_ui.py (N tests, N passing)

### Design Token Compliance
- Lint score: N/5
- Violations (if any): [list]

### Test Results
- pytest: N passed, N failed (list failures with reason)

### BLOCKED items (if any)
- [item] — BLOCKED-FIXABLE or BLOCKED-EXTERNAL — [reason]

### Visual QA Checklist (for DeskRelay)
- [ ] Station Predictor page renders correctly at desktop (1200px)
- [ ] Input field has obsidian styling (dark bg, monospace font)
- [ ] Results area appears after mock API response
- [ ] Page renders correctly at 375px mobile width
- [ ] No hardcoded colors visible
```

Commit your work:
```bash
git add web/templates/tools/station_predictor.html tests/test_station_predictor_ui.py web/routes_search.py scenarios-t3-sprint88.md CHANGELOG-t3-sprint88.md
git commit -m "feat(qs10-t3a): add /tools/station-predictor page and route"
```
""")
```

---

### Agent 3B: Stuck Permit Analyzer

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes of starting.
- DESCOPE RULE: If you cannot complete a task, mark it BLOCKED with reason. Do NOT silently reduce scope.
- READ ONLY FILES: web/routes_api.py, web/app.py, src/server.py, scripts/*.py, CLAUDE.md, CHANGELOG.md
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t3-sprint88.md (write 2-5 scenarios for your feature)
  * CHANGELOG-t3-sprint88.md (your section only)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. DESIGN TOKEN COMPLIANCE — run: python scripts/design_lint.py --changed --quiet
5. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
6. CHECKQUAD — write your session artifact (see CHECKQUAD section below)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit for DDL init
- CRON_WORKER env var needed for cron endpoint tests

## YOUR TASK: Stuck Permit Analyzer page — /tools/stuck-permit

### File Ownership (3B)
- web/templates/tools/stuck_permit.html (CREATE)
- tests/test_stuck_permit_ui.py (CREATE)
- web/routes_search.py (APPEND route at EOF — do NOT touch existing content)

### Read First
1. docs/DESIGN_TOKENS.md — full file (mandatory before any template work)
2. web/routes_api.py lines 797-826 — the /api/stuck-permit/<permit_number> endpoint signature and return shape
3. web/routes_search.py — last 40 lines (understand EOF structure before appending)
4. web/templates/fragments/head_obsidian.html — understand what it provides
5. web/templates/fragments/nav.html — understand the nav include
6. tests/test_sprint58c_methodology_ui.py — reference for template-string test pattern

### Build

#### Step 1: Create tools directory if needed
```bash
mkdir -p /Users/timbrenneman/AIprojects/sf-permits-mcp/web/templates/tools
```

#### Step 2: Create web/templates/tools/stuck_permit.html

Standalone page. Build from scratch following design requirements.

**Page purpose:** User enters a permit number, clicks "Diagnose", sees a ranked intervention playbook explaining why the permit may be stuck and what to do about it.

**Page structure:**
- Page header: h1 "Stuck Permit Analyzer", subtitle "Diagnose delays and get a ranked intervention playbook for any SF permit."
- Input form:
  - Text input for permit number (monospace font, obsidian search-input style)
  - Submit button "Diagnose permit →" (action-btn or ghost-cta)
  - This is a GET endpoint: use JavaScript fetch on form submit to call /api/stuck-permit/{permitNumber}
  - Loading state: show "Analyzing..." indicator during fetch
  - Error handling: if response is 401, show login prompt; if 500, show generic error
- Results area: <div id="results" class="results-area glass-card"></div>
- Result rendering: the API returns JSON {permit_number, result} where result is markdown. Render the markdown as pre-formatted text or use a simple marked.js parse.
- Empty state hint: "Enter a permit number to diagnose delays and get intervention steps."

**Design tokens:**
- Background: var(--obsidian), cards: var(--obsidian-mid)
- Text: var(--text-primary) for values/headings, var(--text-secondary) for descriptions/labels
- Status signals: var(--signal-amber) for "stalled" state indicators, var(--signal-red) for blocked states
- Font: --mono for permit number input, data labels; --sans for page title, descriptions, body text
- No hardcoded hex colors

**CSRF:** GET-only endpoint via JS fetch — no POST form, so no csrf_token input needed. head_obsidian.html handles the CSRF meta tag.

**Auth:** On 401 response, render: "This tool requires a free account. [Log in or create account →]"

**Mobile:** Full-width form at 375px.

#### Step 3: Append route to web/routes_search.py
Go to the very end of the file and APPEND:

```python
# ---------------------------------------------------------------------------
# Stuck Permit Analyzer — /tools/stuck-permit (Sprint QS10-T3-3B)
# ---------------------------------------------------------------------------

@bp.route("/tools/stuck-permit")
def tools_stuck_permit():
    """Stuck Permit Analyzer: diagnose delays and get intervention playbook."""
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))
    return render_template("tools/stuck_permit.html")
```

#### Step 4: Create tests/test_stuck_permit_ui.py

```python
\"\"\"Tests for web/templates/tools/stuck_permit.html.

Template-string tests — reads the file and asserts structural requirements.
No Flask test client or Jinja rendering needed (except route tests).
\"\"\"
import os
import re
import pytest

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/stuck_permit.html"
)

def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestStuckPermitTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_stuck_permit(self):
        assert 'Stuck' in self.html or 'stuck' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_stuck_permit_api_referenced(self):
        assert 'stuck-permit' in self.html or 'api/stuck-permit' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\\*.*?\\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex colors in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_signal_color_for_status(self):
        \"\"\"Template uses signal colors for delay/stuck status indicators.\"\"\"
        assert '--signal-amber' in self.html or '--signal-red' in self.html or 'signal' in self.html


class TestStuckPermitRoute:
    def test_route_redirects_unauthenticated(self, client):
        rv = client.get("/tools/stuck-permit")
        assert rv.status_code in (302, 301)

    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/stuck-permit")
        assert rv.status_code == 200
        assert b'Stuck' in rv.data or b'stuck' in rv.data


from web.app import app, _rate_buckets

@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()

@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()
```

Note: If authed_client route test fails because g.user requires full before_request chain, mark with `@pytest.mark.xfail(reason="g.user requires full before_request chain — needs integration fixture")`.

### Test
```bash
source .venv/bin/activate
pytest tests/test_stuck_permit_ui.py -v --tb=short
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -10
```

### Design Token Compliance
```bash
python scripts/design_lint.py --changed --quiet
```

### Scenarios
Write 2-5 scenarios to scenarios-t3-sprint88.md (append if file already exists from Agent 3A):

## SUGGESTED SCENARIO: [name]
**Source:** stuck_permit.html / tools_stuck_permit route
**User:** expediter | homeowner
**Starting state:** [...]
**Goal:** [...]
**Expected outcome:** [...]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

### CHANGELOG-t3-sprint88.md
```
## Agent 3B — Stuck Permit Analyzer UI
- Added /tools/stuck-permit page (web/templates/tools/stuck_permit.html)
- Added tools_stuck_permit route to web/routes_search.py
- Added tests/test_stuck_permit_ui.py (N tests)
- Design lint score: N/5
```

### CHECKQUAD
```
## CHECKQUAD — Agent 3B (Stuck Permit Analyzer)

### Shipped
- web/templates/tools/stuck_permit.html (created)
- web/routes_search.py (route appended at EOF)
- tests/test_stuck_permit_ui.py (N tests, N passing)

### Design Token Compliance
- Lint score: N/5
- Violations (if any): [list]

### Test Results
- pytest: N passed, N failed (list failures with reason)

### BLOCKED items (if any)
- [item] — BLOCKED-FIXABLE or BLOCKED-EXTERNAL — [reason]

### Visual QA Checklist (for DeskRelay)
- [ ] Stuck Permit page renders correctly at desktop (1200px)
- [ ] Status indicators use signal colors (amber/red), not hardcoded hex
- [ ] Results area renders markdown playbook after mock response
- [ ] Page renders correctly at 375px mobile width
```

Commit your work:
```bash
git add web/templates/tools/stuck_permit.html tests/test_stuck_permit_ui.py web/routes_search.py scenarios-t3-sprint88.md CHANGELOG-t3-sprint88.md
git commit -m "feat(qs10-t3b): add /tools/stuck-permit page and route"
```
""")
```

---

### Agent 3C: What-If Simulator

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes of starting.
- DESCOPE RULE: If you cannot complete a task, mark it BLOCKED with reason. Do NOT silently reduce scope.
- READ ONLY FILES: web/routes_api.py, web/app.py, src/server.py, scripts/*.py, CLAUDE.md, CHANGELOG.md
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t3-sprint88.md (write 2-5 scenarios for your feature)
  * CHANGELOG-t3-sprint88.md (your section only)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. DESIGN TOKEN COMPLIANCE — run: python scripts/design_lint.py --changed --quiet
5. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
6. CHECKQUAD — write your session artifact (see CHECKQUAD section below)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit for DDL init
- CRON_WORKER env var needed for cron endpoint tests

## YOUR TASK: What-If Simulator page — /tools/what-if

### File Ownership (3C)
- web/templates/tools/what_if.html (CREATE)
- tests/test_what_if_ui.py (CREATE)
- web/routes_search.py (APPEND route at EOF — do NOT touch existing content)

### Read First
1. docs/DESIGN_TOKENS.md — full file (mandatory before any template work)
2. web/routes_api.py lines 829-873 — the POST /api/what-if endpoint: body schema, return shape
3. web/routes_search.py — last 40 lines (understand EOF structure before appending)
4. web/templates/fragments/head_obsidian.html — understand what it provides
5. web/templates/fragments/nav.html — understand the nav include
6. tests/test_sprint58c_methodology_ui.py — reference for template-string test pattern

### API contract for POST /api/what-if:
Body JSON:
  { "base_description": str (required), "variations": [{"label": str, "description": str}] }
Returns: {"result": "...markdown comparison table..."} or {"error": "..."}
Requires authentication — returns 401 if no session.

### Build

#### Step 1: Create tools directory if needed
```bash
mkdir -p /Users/timbrenneman/AIprojects/sf-permits-mcp/web/templates/tools
```

#### Step 2: Create web/templates/tools/what_if.html

Standalone page. Build from scratch following design requirements.

**Page purpose:** User describes their base project, optionally adds variations to compare, submits to see a side-by-side comparison of how each variation affects timeline, fees, and revision risk.

**Page structure:**
- Page header: h1 "What-If Simulator", subtitle "Compare how project variations change timeline, fees, and revision risk."
- Main form (POST via HTMX to /api/what-if as JSON):
  - "Base Project" section:
    - Textarea: "Describe your project" (placeholder: "e.g. ADU in the backyard, 500 sq ft, Noe Valley")
    - Monospace font for textarea (data input), --sans label
  - "Variations to Compare" section (optional):
    - Up to 3 variation pairs: Label input + Description textarea
    - "Add variation" ghost button that shows/hides additional pairs via JS (start with 1 visible, max 3)
    - Users can leave variations empty to just analyze the base project
  - Submit button "Run simulation →" (action-btn)
  - HTMX: POST to /api/what-if as JSON. Since HTMX sends form-encoded by default, use JavaScript to intercept the form submit, build the JSON body, and call fetch(). Set Content-Type: application/json. Include X-CSRFToken header from meta[name="csrf-token"].
  - Loading state: "Simulating..." indicator
- Results area: <div id="results" class="results-area glass-card"></div>
- Result rendering: parse JSON response, render result.result (markdown table) as HTML
- Error state: show error message; if 401, show login prompt

**CSRF for JSON POST:** Use fetch() with headers:
```javascript
const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
fetch('/api/what-if', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
  body: JSON.stringify({base_description: ..., variations: [...]})
})
```

**Design tokens:**
- Background: var(--obsidian), surface: var(--obsidian-mid), elevated: var(--obsidian-light)
- Text: var(--text-primary) headings/values, var(--text-secondary) labels/descriptions
- Input: search-input style from DESIGN_TOKENS.md §5
- Font: --mono for textarea (project description is data input), --mono for variation labels; --sans for section headings, page title, body descriptions
- No hardcoded hex colors

**Mobile:** Single-column form at 375px. Variation pairs stack vertically.

#### Step 3: Append route to web/routes_search.py
Go to the very end of the file and APPEND:

```python
# ---------------------------------------------------------------------------
# What-If Simulator — /tools/what-if (Sprint QS10-T3-3C)
# ---------------------------------------------------------------------------

@bp.route("/tools/what-if")
def tools_what_if():
    """What-If Simulator: compare project variation impacts on timeline and fees."""
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))
    return render_template("tools/what_if.html")
```

#### Step 4: Create tests/test_what_if_ui.py

```python
\"\"\"Tests for web/templates/tools/what_if.html.\"\"\"
import os
import re
import pytest

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/what_if.html"
)

def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestWhatIfTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_what_if(self):
        assert 'What-If' in self.html or 'what-if' in self.html or 'Simulator' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_what_if_api_referenced(self):
        assert 'api/what-if' in self.html or 'what-if' in self.html

    def test_base_description_input(self):
        \"\"\"Form has a base project description field.\"\"\"
        assert 'base_description' in self.html or 'base-description' in self.html or 'textarea' in self.html

    def test_json_post_with_csrf_header(self):
        \"\"\"Template sends JSON POST with X-CSRFToken header.\"\"\"
        assert 'X-CSRFToken' in self.html or 'csrf' in self.html.lower()
        assert 'application/json' in self.html or 'JSON.stringify' in self.html

    def test_no_hardcoded_hex_in_styles(self):
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\\*.*?\\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_variations_section(self):
        \"\"\"Template includes a variations input section.\"\"\"
        assert 'variation' in self.html.lower()

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()


class TestWhatIfRoute:
    def test_route_redirects_unauthenticated(self, client):
        rv = client.get("/tools/what-if")
        assert rv.status_code in (302, 301)

    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/what-if")
        assert rv.status_code == 200
        assert b'What-If' in rv.data or b'Simulator' in rv.data


from web.app import app, _rate_buckets

@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()

@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()
```

Note: If authed_client route test fails because g.user requires full before_request chain, mark with `@pytest.mark.xfail(reason="g.user requires full before_request chain")`.

### Test
```bash
source .venv/bin/activate
pytest tests/test_what_if_ui.py -v --tb=short
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -10
```

### Design Token Compliance
```bash
python scripts/design_lint.py --changed --quiet
```

### Scenarios
Write 2-5 scenarios to scenarios-t3-sprint88.md (append if file exists):

## SUGGESTED SCENARIO: [name]
**Source:** what_if.html / tools_what_if route
**User:** architect | expediter
**Starting state:** [...]
**Goal:** [...]
**Expected outcome:** [...]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

### CHANGELOG-t3-sprint88.md
```
## Agent 3C — What-If Simulator UI
- Added /tools/what-if page (web/templates/tools/what_if.html)
- Added tools_what_if route to web/routes_search.py
- Added tests/test_what_if_ui.py (N tests)
- Design lint score: N/5
```

### CHECKQUAD
```
## CHECKQUAD — Agent 3C (What-If Simulator)

### Shipped
- web/templates/tools/what_if.html (created)
- web/routes_search.py (route appended at EOF)
- tests/test_what_if_ui.py (N tests, N passing)

### Design Token Compliance
- Lint score: N/5
- Violations (if any): [list]

### Test Results
- pytest: N passed, N failed (list failures with reason)

### BLOCKED items (if any)
- [item] — BLOCKED-FIXABLE or BLOCKED-EXTERNAL — [reason]

### Visual QA Checklist (for DeskRelay)
- [ ] What-If Simulator renders correctly at desktop (1200px)
- [ ] Variation add/remove UI works correctly (JS-driven)
- [ ] Form submits as JSON with CSRF header
- [ ] Results render markdown comparison table
- [ ] Page renders correctly at 375px mobile width
```

Commit your work:
```bash
git add web/templates/tools/what_if.html tests/test_what_if_ui.py web/routes_search.py scenarios-t3-sprint88.md CHANGELOG-t3-sprint88.md
git commit -m "feat(qs10-t3c): add /tools/what-if simulator page and route"
```
""")
```

---

### Agent 3D: Cost of Delay Calculator

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes of starting.
- DESCOPE RULE: If you cannot complete a task, mark it BLOCKED with reason. Do NOT silently reduce scope.
- READ ONLY FILES: web/routes_api.py, web/app.py, src/server.py, scripts/*.py, CLAUDE.md, CHANGELOG.md
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t3-sprint88.md (write 2-5 scenarios for your feature)
  * CHANGELOG-t3-sprint88.md (your section only)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. DESIGN TOKEN COMPLIANCE — run: python scripts/design_lint.py --changed --quiet
5. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
6. CHECKQUAD — write your session artifact (see CHECKQUAD section below)

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit for DDL init
- CRON_WORKER env var needed for cron endpoint tests

## YOUR TASK: Cost of Delay Calculator page — /tools/cost-of-delay

### File Ownership (3D)
- web/templates/tools/cost_of_delay.html (CREATE)
- tests/test_cost_of_delay_ui.py (CREATE)
- web/routes_search.py (APPEND route at EOF — do NOT touch existing content)

### Read First
1. docs/DESIGN_TOKENS.md — full file (mandatory before any template work)
2. web/routes_api.py lines 876-932 — the POST /api/delay-cost endpoint: body schema, validation logic, return shape
3. web/routes_search.py — last 40 lines (understand EOF structure before appending)
4. web/templates/fragments/head_obsidian.html — understand what it provides
5. web/templates/fragments/nav.html — understand the nav include
6. tests/test_sprint58c_methodology_ui.py — reference for template-string test pattern

### API contract for POST /api/delay-cost:
Body JSON:
  {
    "permit_type": str (required, e.g. "adu", "restaurant", "commercial"),
    "monthly_carrying_cost": float (required, > 0),
    "neighborhood": str (optional),
    "triggers": [str, ...] (optional)
  }
Returns: {"result": "...markdown cost breakdown..."} or {"error": "..."}
Requires authentication — returns 401 if no session.
Validation: monthly_carrying_cost must be > 0 (API returns 400 if zero or negative).

### Build

#### Step 1: Create tools directory if needed
```bash
mkdir -p /Users/timbrenneman/AIprojects/sf-permits-mcp/web/templates/tools
```

#### Step 2: Create web/templates/tools/cost_of_delay.html

Standalone page. Build from scratch following design requirements.

**Page purpose:** User enters permit type and monthly carrying cost (the financial cost of delay per month — e.g. loan interest, rent opportunity cost). Optionally specifies neighborhood and known delay triggers. Gets back a markdown breakdown of the total estimated cost of processing delays.

**Page structure:**
- Page header: h1 "Cost of Delay Calculator", subtitle "Calculate the financial cost of SF permit processing delays for your project."
- Main form (POST via JS fetch as JSON to /api/delay-cost):
  - "Permit Type" input: text field (monospace), placeholder "e.g. adu, restaurant, commercial remodel"
  - "Monthly Carrying Cost" input: number field ($), placeholder "e.g. 5000" — note: must be > 0 (validate client-side before submitting)
  - "Neighborhood" input: text field (optional), placeholder "e.g. Mission, Noe Valley, SoMa"
  - "Known Delay Triggers" input: text field (optional), placeholder "e.g. active complaints, incomplete drawings" — comma-separated, split to array before submitting
  - Submit button "Calculate cost →" (action-btn)
  - Client-side validation: show error inline if monthly_carrying_cost is empty, zero, or negative before submitting
  - HTMX approach: use JavaScript fetch() for JSON POST (not native HTMX hx-post, since we need JSON body and custom header handling)
  - Include X-CSRFToken from meta[name="csrf-token"] in fetch headers
  - Loading state: "Calculating..." indicator
- Results area: <div id="results" class="results-area glass-card"></div>
- Result rendering: render result.result (markdown) as pre-formatted or parsed HTML
- Error state: inline error message; if 401, show login prompt

**Fetch pattern:**
```javascript
const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
const triggers = triggersInput.value ? triggersInput.value.split(',').map(s => s.trim()).filter(Boolean) : null;
fetch('/api/delay-cost', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
  body: JSON.stringify({
    permit_type: permitTypeInput.value.trim(),
    monthly_carrying_cost: parseFloat(monthlyCostInput.value),
    neighborhood: neighborhoodInput.value.trim() || null,
    triggers: triggers
  })
})
```

**Design tokens:**
- Background: var(--obsidian), cards: var(--obsidian-mid), elevated inputs: var(--obsidian-light)
- Text: var(--text-primary) for values, var(--text-secondary) for labels
- Cost values in results: var(--signal-amber) for moderate delays, var(--signal-red) for severe — but only if the template renders structured data (markdown display is fine without color coding)
- Font: --mono for all form inputs (they're data entry), --mono for currency values; --sans for page title, descriptions, form field labels
- No hardcoded hex colors

**Mobile:** Single-column form at 375px. Full-width inputs and button.

#### Step 3: Append route to web/routes_search.py
Go to the very end of the file and APPEND:

```python
# ---------------------------------------------------------------------------
# Cost of Delay Calculator — /tools/cost-of-delay (Sprint QS10-T3-3D)
# ---------------------------------------------------------------------------

@bp.route("/tools/cost-of-delay")
def tools_cost_of_delay():
    """Cost of Delay Calculator: financial impact of permit processing delays."""
    from flask import redirect, url_for
    if not g.user:
        return redirect(url_for("auth.login"))
    return render_template("tools/cost_of_delay.html")
```

#### Step 4: Create tests/test_cost_of_delay_ui.py

```python
\"\"\"Tests for web/templates/tools/cost_of_delay.html.\"\"\"
import os
import re
import pytest

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__),
    "../web/templates/tools/cost_of_delay.html"
)

def _read():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


class TestCostOfDelayTemplate:
    def setup_method(self):
        self.html = _read()

    def test_template_exists(self):
        assert len(self.html) > 100

    def test_includes_head_obsidian(self):
        assert 'head_obsidian.html' in self.html

    def test_includes_nav(self):
        assert 'nav.html' in self.html

    def test_page_title_cost_of_delay(self):
        assert 'Cost' in self.html or 'Delay' in self.html

    def test_results_div_present(self):
        assert 'id="results"' in self.html

    def test_delay_cost_api_referenced(self):
        assert 'delay-cost' in self.html or 'api/delay-cost' in self.html

    def test_permit_type_input(self):
        \"\"\"Form has a permit type field.\"\"\"
        assert 'permit_type' in self.html or 'permit-type' in self.html or 'permit type' in self.html.lower()

    def test_monthly_cost_input(self):
        \"\"\"Form has a monthly carrying cost field.\"\"\"
        assert 'monthly_carrying_cost' in self.html or 'monthly' in self.html.lower()

    def test_json_post_with_csrf(self):
        \"\"\"Template sends JSON POST with CSRF token.\"\"\"
        assert 'X-CSRFToken' in self.html or 'csrf' in self.html.lower()
        assert 'application/json' in self.html or 'JSON.stringify' in self.html

    def test_client_side_validation(self):
        \"\"\"Template validates monthly cost > 0 before submission.\"\"\"
        assert 'parseFloat' in self.html or 'validation' in self.html.lower() or '> 0' in self.html or 'must be' in self.html.lower()

    def test_no_hardcoded_hex_in_styles(self):
        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', self.html, re.DOTALL)
        for block in style_blocks:
            block_no_comments = re.sub(r'/\\*.*?\\*/', '', block, flags=re.DOTALL)
            hex_in_values = re.findall(r':\\s*#[0-9a-fA-F]{3,6}', block_no_comments)
            assert not hex_in_values, f"Hardcoded hex in style block: {hex_in_values}"

    def test_mono_font_used(self):
        assert '--mono' in self.html

    def test_viewport_meta(self):
        assert 'viewport' in self.html

    def test_auth_error_handled(self):
        assert '401' in self.html or 'log in' in self.html.lower() or 'login' in self.html.lower()

    def test_optional_neighborhood_field(self):
        \"\"\"Form has optional neighborhood input.\"\"\"
        assert 'neighborhood' in self.html.lower()


class TestCostOfDelayRoute:
    def test_route_redirects_unauthenticated(self, client):
        rv = client.get("/tools/cost-of-delay")
        assert rv.status_code in (302, 301)

    def test_route_renders_for_authenticated_user(self, authed_client):
        rv = authed_client.get("/tools/cost-of-delay")
        assert rv.status_code == 200
        assert b'Cost' in rv.data or b'Delay' in rv.data


from web.app import app, _rate_buckets

@pytest.fixture
def client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()

@pytest.fixture
def authed_client():
    app.config['TESTING'] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-user-123'
        yield c
    _rate_buckets.clear()
```

Note: If authed_client route test fails because g.user requires full before_request chain, mark with `@pytest.mark.xfail(reason="g.user requires full before_request chain")`.

### Test
```bash
source .venv/bin/activate
pytest tests/test_cost_of_delay_ui.py -v --tb=short
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -10
```

### Design Token Compliance
```bash
python scripts/design_lint.py --changed --quiet
```

### Scenarios
Write 2-5 scenarios to scenarios-t3-sprint88.md (append if file exists):

## SUGGESTED SCENARIO: [name]
**Source:** cost_of_delay.html / tools_cost_of_delay route
**User:** expediter | developer | homeowner
**Starting state:** [...]
**Goal:** [...]
**Expected outcome:** [...]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

### CHANGELOG-t3-sprint88.md
```
## Agent 3D — Cost of Delay Calculator UI
- Added /tools/cost-of-delay page (web/templates/tools/cost_of_delay.html)
- Added tools_cost_of_delay route to web/routes_search.py
- Added tests/test_cost_of_delay_ui.py (N tests)
- Design lint score: N/5
```

### CHECKQUAD
```
## CHECKQUAD — Agent 3D (Cost of Delay Calculator)

### Shipped
- web/templates/tools/cost_of_delay.html (created)
- web/routes_search.py (route appended at EOF)
- tests/test_cost_of_delay_ui.py (N tests, N passing)

### Design Token Compliance
- Lint score: N/5
- Violations (if any): [list]

### Test Results
- pytest: N passed, N failed (list failures with reason)

### BLOCKED items (if any)
- [item] — BLOCKED-FIXABLE or BLOCKED-EXTERNAL — [reason]

### Visual QA Checklist (for DeskRelay)
- [ ] Cost of Delay page renders correctly at desktop (1200px)
- [ ] Monthly cost input validates > 0 before submit
- [ ] Results render markdown cost breakdown
- [ ] Optional fields (neighborhood, triggers) are visually distinguished as optional
- [ ] Page renders correctly at 375px mobile width
```

Commit your work:
```bash
git add web/templates/tools/cost_of_delay.html tests/test_cost_of_delay_ui.py web/routes_search.py scenarios-t3-sprint88.md CHANGELOG-t3-sprint88.md
git commit -m "feat(qs10-t3d): add /tools/cost-of-delay calculator page and route"
```
""")
```

---

## Collect Agent Results

Wait for all 4 agents to complete. Confirm each agent pushed a commit to their worktree branch.

```bash
# In the main repo root — check all worktree branches
git worktree list
git branch -a | grep claude
```

If any agent failed, take over manually: cd into its worktree, complete the missed work, commit.

---

## Merge Ceremony (A → B → C → D)

Merge in this order to preserve routes_search.py append ordering (each agent added their route at EOF of the previous state).

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# MERGE 1 — Agent 3A (station predictor)
git merge <3A-branch> --no-ff -m "merge(qs10-t3a): station predictor page + route"
# Verify tools dir exists and 3A route is appended:
grep "tools_station_predictor" web/routes_search.py

# MERGE 2 — Agent 3B (stuck permit)
git merge <3B-branch> --no-ff -m "merge(qs10-t3b): stuck permit analyzer page + route"
grep "tools_stuck_permit" web/routes_search.py

# MERGE 3 — Agent 3C (what-if simulator)
git merge <3C-branch> --no-ff -m "merge(qs10-t3c): what-if simulator page + route"
grep "tools_what_if" web/routes_search.py

# MERGE 4 — Agent 3D (cost of delay)
git merge <3D-branch> --no-ff -m "merge(qs10-t3d): cost of delay calculator page + route"
grep "tools_cost_of_delay" web/routes_search.py
```

If there is a merge conflict on `web/routes_search.py`: Each agent appended a unique section with a section-comment marker (`# Sprint QS10-T3-3[A/B/C/D]`). Accept both sides (keep all appended routes). Do not remove any routes.

---

## Post-Merge Verification

```bash
# 1. Verify all 4 templates exist
ls web/templates/tools/
# Expect: station_predictor.html, stuck_permit.html, what_if.html, cost_of_delay.html

# 2. Verify all 4 routes are in routes_search.py
grep "tools_station_predictor\|tools_stuck_permit\|tools_what_if\|tools_cost_of_delay" web/routes_search.py

# 3. Verify all 4 test files exist
ls tests/test_station_predictor_ui.py tests/test_stuck_permit_ui.py tests/test_what_if_ui.py tests/test_cost_of_delay_ui.py

# 4. Run full test suite
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# Expected: all new tests pass; no regressions

# 5. Design lint — all 4 templates
python scripts/design_lint.py --changed --quiet
# Target: 4/5 or higher for all templates

# 6. Consolidate per-agent output files
cat scenarios-t3-sprint88.md >> scenarios-pending-review.md
# Review before appending — make sure it's in the right format

# 7. Consolidate CHANGELOG entries
cat CHANGELOG-t3-sprint88.md >> CHANGELOG.md
# Add to top of the Sprint QS10 section

# 8. Clean up per-agent temp files
rm -f scenarios-t3-sprint88.md CHANGELOG-t3-sprint88.md
```

---

## Push

```bash
git push origin main
echo "T3 complete. 4 tool pages live on main."
```

---

## CHECKQUAD — Terminal 3

Write this artifact after push completes:

```
## CHECKQUAD — T3 (Intelligence Tool UI)
**Sprint:** QS10
**Agents:** 3A, 3B, 3C, 3D

### MERGE STATUS
- [x] 3A merged: station_predictor.html + route
- [x] 3B merged: stuck_permit.html + route
- [x] 3C merged: what_if.html + route
- [x] 3D merged: cost_of_delay.html + route
- [x] Pushed to main

### ARTIFACTS
- web/templates/tools/ (4 new files)
- web/routes_search.py (4 routes appended)
- tests/test_station_predictor_ui.py
- tests/test_stuck_permit_ui.py
- tests/test_what_if_ui.py
- tests/test_cost_of_delay_ui.py
- scenarios-pending-review.md (N scenarios appended)
- CHANGELOG.md (T3 entries added)

### TEST RESULTS
pytest: N passed, N failed (0 expected)

### DESIGN LINT
- station_predictor.html: N/5
- stuck_permit.html: N/5
- what_if.html: N/5
- cost_of_delay.html: N/5

### BLOCKED (if any)
- [item] — BLOCKED-FIXABLE or BLOCKED-EXTERNAL — [reason]

### SIGNAL TO T0
T3 DONE. 4 routes live: /tools/station-predictor, /tools/stuck-permit, /tools/what-if, /tools/cost-of-delay.
Branch: main. Pushed. Ready for T0 merge ceremony.
```

Signal T0 when done.
