# QS10 Terminal 2: Admin QA Tools

**Sprint:** QS10 — Phase A Visual QA Foundation + Intelligence UI + Beta Onboarding
**Terminal theme:** Admin QA Tools — Persona Impersonation + Accept/Reject Log
**Agents:** 2 (sequential — 2B starts ONLY after 2A completes)
**Branch target:** `t2/sprint-87`
**Chief Task:** #385

---

## Pre-Flight (30 seconds)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T2 start: $(git rev-parse --short HEAD)"
```

---

## File Ownership

| Agent | Owns | Mode |
|-------|------|------|
| 2A | `web/admin_personas.py` | CREATE |
| 2A | `web/templates/fragments/feedback_widget.html` | MODIFY (add persona dropdown) |
| 2A | `web/routes_admin.py` | APPEND ONLY (POST /admin/impersonate, GET /admin/reset-impersonation) |
| 2A | `tests/test_admin_impersonation.py` | CREATE |
| 2B | `web/templates/fragments/feedback_widget.html` | MODIFY (add Accept/Reject buttons — after 2A) |
| 2B | `web/routes_admin.py` | APPEND ONLY (POST /admin/qa-decision — after 2A) |
| 2B | `qa-results/review-decisions.json` | CREATE |
| 2B | `tests/test_accept_reject_log.py` | CREATE |

**NEVER TOUCH:** `web/app.py`, `src/server.py`, `scripts/*.py`, `web/routes_search.py`, `CLAUDE.md`, `CHANGELOG.md`

---

## CRITICAL: Sequential Dependency

**Agent 2B MUST NOT start until Agent 2A has completed and its branch is known.**

Run 2A first. Get the branch name from its output. Then launch 2B.

---

## Launch Agent 2A (FOREGROUND)

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Admin Persona Impersonation Dropdown (Agent 2A)

Build server-side persona switching for the admin widget. When ?admin=1 is active, a persona
dropdown appears in the existing feedback_widget.html modal. Selecting a persona injects user
state into the session so Tim can preview any user tier/state without creating real accounts.

### File Ownership (2A ONLY)
- CREATE: web/admin_personas.py
- MODIFY: web/templates/fragments/feedback_widget.html (add persona dropdown section)
- APPEND: web/routes_admin.py (add 2 new endpoints ONLY — no modifications to existing routes)
- CREATE: tests/test_admin_impersonation.py

### DO NOT TOUCH
- web/app.py, src/server.py, scripts/*.py, web/routes_search.py, CLAUDE.md, CHANGELOG.md

### Read First
1. web/templates/fragments/feedback_widget.html — understand existing structure, FAB, modal, CSS tokens
2. web/routes_admin.py — first 30 lines (imports, Blueprint, pattern) only
3. web/helpers.py — login_required, admin_required decorators
4. web/auth.py — add_watch() signature (lines 368-417), subscription_tier field
5. web/app.py — lines 970-979 (how g.user and session["impersonating"] are loaded)
6. docs/DESIGN_TOKENS.md — use ONLY these tokens for any HTML/CSS you add

### DuckDB/Postgres Gotchas (MANDATORY — agents don't read memory)
These apply to ALL DB code you write:
- DuckDB uses `?` placeholders; Postgres uses `%s`
- DuckDB: `conn.execute()`; Postgres: `cursor.execute()`
- `INSERT OR REPLACE` is DuckDB syntax → Postgres uses `ON CONFLICT DO UPDATE`
- Postgres transactions abort on ANY error — use autocommit=True for DDL-style init
- Always check `BACKEND == "postgres"` vs `"duckdb"` and branch accordingly (see auth.py pattern)
- For test isolation: use `monkeypatch.delenv("DATABASE_URL", raising=False)` and a tmp_path duckdb

### Build: web/admin_personas.py

Create this module with a `PERSONAS` dict and an `apply_persona(session, persona_name)` function.

```python
# web/admin_personas.py
\"\"\"Admin persona definitions for QA impersonation.

Each persona injects a specific user state into the Flask session so Tim
can preview any user tier/state without creating real accounts.
\"\"\"
```

Define 6 personas as a list of dicts. Each persona has:
- `id` (str) — machine key used in POST body
- `label` (str) — display name in dropdown
- `tier` (str) — subscription_tier: "free" | "beta" | "power" | "admin"
- `watches` (list of dicts) — watch items to inject (may be empty)
- `search_history` (list of str) — simulated recent searches (may be empty)

The 6 personas:

1. id="anon_new", label="Anonymous New", tier="free", watches=[], search_history=[]
   — No session, fresh visitor. Apply by clearing user_id from session.

2. id="anon_returning", label="Anonymous Returning", tier="free", watches=[],
   search_history=["123 Main St", "555 Market St"]
   — No session but has search history cookie (inject via session key "anon_searches").

3. id="free_auth", label="Free Authenticated", tier="free", watches=[],
   search_history=["Mission District permits"]
   — Authenticated, no watches, free tier.

4. id="beta_empty", label="Beta Empty", tier="beta", watches=[],
   search_history=[]
   — Beta tier, no watches yet.

5. id="beta_active", label="Beta Active (3 watches)", tier="beta",
   watches=[
     {"watch_type": "address", "street_number": "1", "street_name": "Market St", "label": "1 Market St"},
     {"watch_type": "address", "street_number": "525", "street_name": "Market St", "label": "525 Market St"},
     {"watch_type": "address", "street_number": "3251", "street_name": "20th Ave", "label": "3251 20th Ave"},
   ],
   search_history=["seismic retrofit", "ADU permit cost"]
   — Core beta user.

6. id="power_user", label="Power User (12 watches)", tier="power",
   watches=(generate 12 placeholder address watches with varied street names),
   search_history=["Tenderloin SRO", "Mission Victorian", "SOMA ADU"]
   — Power tier, heavy user.

Also define a sentinel persona:
7. id="admin_reset", label="Admin (reset)", tier="admin", watches=[], search_history=[]
   — Clears all impersonation, restores real admin session.

```python
PERSONAS = [...]  # ordered list

def get_persona(persona_id: str) -> dict | None:
    \"\"\"Look up a persona by id. Returns None if not found.\"\"\"

def apply_persona(flask_session, persona: dict) -> None:
    \"\"\"Inject persona state into the Flask session dict.

    Sets session keys:
    - "impersonating": True (so g.is_impersonating is set in _load_user)
    - "persona_id": persona["id"]
    - "persona_tier": persona["tier"]
    - "persona_watches": persona["watches"]  (list of dicts)
    - "anon_searches": persona["search_history"]

    For "admin_reset" persona: clears all impersonation keys.
    Does NOT modify "user_id" — real auth session is preserved.
    \"\"\"
```

### Build: web/routes_admin.py — APPEND ONLY

Append exactly 2 new endpoints to the BOTTOM of routes_admin.py.
Do NOT modify any existing route. Import web.admin_personas inline inside each function.

Endpoint 1: POST /admin/impersonate
- Auth: g.user must be admin (check g.user.get("is_admin"), abort 403 if not)
- Body: form field `persona_id` (str)
- Logic: call get_persona(persona_id), call apply_persona(session, persona), return HTMX snippet
- Response: small HTML span showing active persona label (e.g. "Persona: Beta Active (3 watches)")
  Use --signal-green color on success, --signal-red on unknown persona_id.
- CSRF: include `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` in the form
  that POSTs to this endpoint (in the template, not the route).

Endpoint 2: GET /admin/reset-impersonation
- Auth: g.user must be admin
- Logic: call apply_persona(session, get_persona("admin_reset")), redirect to request.referrer or "/"
- This is the "escape hatch" — navigate here to fully clear persona state.

### Build: web/templates/fragments/feedback_widget.html — ADD persona panel

Read the existing file in full first. Then add a new section INSIDE the modal__body, ABOVE the
existing feedback form. This section is only visible when the user is an admin.

Use Jinja2 to guard it:
```jinja2
{% if g.user and g.user.get('is_admin') %}
<div id="persona-panel" style="margin-bottom:var(--space-4);padding-bottom:var(--space-4);border-bottom:1px solid var(--glass-border);">
  <!-- persona dropdown + impersonate button here -->
</div>
{% endif %}
```

Inside the panel:
- Label: "QA Persona" in `--mono` font, `--text-secondary` color, `var(--text-xs)` size
- A `<select>` element with id="persona-select", class="form-input" (existing token),
  style="margin-top:var(--space-1);"
  Options: one `<option>` per persona in PERSONAS list, value=persona["id"], text=persona["label"]
  Pre-select the currently active persona if `session.get("persona_id")` is set.
- An "Apply" button: class="action-btn", style="margin-top:var(--space-2);width:100%;"
  Uses hx-post="/admin/impersonate", hx-target="#persona-status", hx-swap="innerHTML",
  hx-include="#persona-select", hx-vals='{"csrf_token": "{{ csrf_token }}"}'
- A status line: `<span id="persona-status">` showing current persona if active, else empty.
  If session.get("persona_id") is set: show "Active: {{ session.get('persona_label', '') }}"
  in `--text-xs --mono --signal-green` style.
- A "Reset" link: `<a href="/admin/reset-impersonation">` styled as ghost-cta in `--text-xs`.

DESIGN RULES (mandatory):
- No inline hex colors. Only CSS custom properties from docs/DESIGN_TOKENS.md.
- Font: --mono for labels/status, --sans for prose.
- No invented components. Use form-input, action-btn, ghost-cta from token sheet.

### Build: tests/test_admin_impersonation.py

Write a self-contained pytest file. Pattern from tests/test_admin_health.py:
- _use_duckdb fixture (autouse, monkeypatches SF_PERMITS_DB + BACKEND)
- client fixture (app.config["TESTING"] = True)
- _login_admin() helper (creates admin user, magic-link verify)
- _login_user() helper (creates non-admin user)

Tests to write:
1. test_impersonation_requires_admin
   POST /admin/impersonate as non-admin → 403

2. test_impersonation_beta_active
   POST /admin/impersonate with persona_id="beta_active" as admin
   → response 200, contains "Beta Active" in body
   → session["persona_id"] == "beta_active"
   → session["persona_tier"] == "beta"
   → session["persona_watches"] has 3 items

3. test_impersonation_unknown_persona
   POST /admin/impersonate with persona_id="nonexistent" as admin
   → response contains error color text (--signal-red or "error")

4. test_reset_impersonation
   First apply a persona, then GET /admin/reset-impersonation
   → follows redirect (200 on final page)
   → session["impersonating"] is falsy or absent

5. test_all_personas_have_required_keys
   Import PERSONAS from web.admin_personas
   Assert each has: id, label, tier, watches, search_history

6. test_admin_reset_persona_clears_state
   Import apply_persona, get_persona from web.admin_personas
   Create a mock session dict, apply "beta_active", then apply "admin_reset"
   Assert impersonating key is gone or False after reset

### Test
```bash
source .venv/bin/activate && pytest tests/test_admin_impersonation.py -v --tb=short
```
All 6 tests must pass before committing.

Also run the full suite to verify no regressions:
```bash
source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
```

### Design Lint
```bash
source .venv/bin/activate && python scripts/design_lint.py --files web/templates/fragments/feedback_widget.html --quiet
```
Record score. Target 4/5 or 5/5. If violations found, fix them before committing.

### Scenarios
Write 2-3 scenarios to scenarios-t2-sprint87.md (CREATE this file, do not append to scenarios-pending-review.md):

Format each as:
## SUGGESTED SCENARIO: [name]
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** admin
**Starting state:** [state]
**Goal:** [goal]
**Expected outcome:** [outcome]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

Suggested scenarios:
- Admin switches to "Beta Active" persona and sees 3 watches in the nav
- Admin resets impersonation and returns to their own session state
- Non-admin user cannot access /admin/impersonate endpoint

### Output Files
- scenarios-t2-sprint87.md (CREATE — 2-3 scenarios)
- CHANGELOG-t2-sprint87.md (CREATE — brief entry for 2A work)

### Commit
```bash
git add web/admin_personas.py web/templates/fragments/feedback_widget.html \
        web/routes_admin.py tests/test_admin_impersonation.py \
        scenarios-t2-sprint87.md CHANGELOG-t2-sprint87.md
git commit -m "feat: admin persona impersonation dropdown in feedback widget (QS10 T2-A)"
```

### Report your branch name
After committing, output:
AGENT 2A COMPLETE — branch: [your worktree branch name] — tests: [N passed]
""")
```

---

## Wait for Agent 2A to Complete

**Do NOT launch Agent 2B until Agent 2A outputs its completion line.**

Capture the branch name from Agent 2A's final output (format: `AGENT 2A COMPLETE — branch: claude/XXXX`).

---

## Launch Agent 2B (FOREGROUND — after 2A completes)

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Accept/Reject Log (Agent 2B)

Agent 2A has already added the persona impersonation dropdown to feedback_widget.html.
You are extending that same widget with Accept/Reject/Note buttons for Tim's visual QA review workflow.

Context: T1's vision_score.py writes entries to qa-results/pending-reviews.json when pages score
below 3.0. Tim uses the admin widget to Accept (looks fine), Reject (needs fix), or Note (borderline)
each pending review item. These verdicts are training data — the note field is critical.

Data stored per decision:
{
  "page": "/search",
  "persona": "beta_active",
  "viewport": "desktop",
  "dimension": "cards",
  "pipeline_score": 2.4,
  "tim_verdict": "accept" | "reject" | "note",
  "sprint": "qs10",
  "note": "tight but fine for data tables",
  "timestamp": "2026-02-28T12:34:56Z"
}

Storage: qa-results/review-decisions.json (append-only JSON array, git-tracked)
Badge: read count from qa-results/pending-reviews.json to show pending item count on FAB.

### File Ownership (2B ONLY)
- MODIFY: web/templates/fragments/feedback_widget.html (add Accept/Reject panel — BELOW 2A's persona panel)
- APPEND: web/routes_admin.py (add POST /admin/qa-decision ONLY)
- CREATE: qa-results/review-decisions.json
- CREATE: tests/test_accept_reject_log.py

### DO NOT TOUCH
- web/admin_personas.py (owned by 2A)
- web/app.py, src/server.py, scripts/*.py, web/routes_search.py, CLAUDE.md, CHANGELOG.md

### Read First
1. web/templates/fragments/feedback_widget.html — read the CURRENT state including 2A's persona panel
   (your worktree may not have 2A's changes — that is expected; add your panel assuming 2A's panel
   exists above it, using the same Jinja2 admin guard pattern)
2. web/routes_admin.py — last 50 lines (see 2A's endpoints for pattern)
3. docs/DESIGN_TOKENS.md — use ONLY these tokens
4. qa-results/ directory listing — understand what files T1 will write

### DuckDB/Postgres Gotchas (MANDATORY — agents don't read memory)
These apply to ALL DB code you write:
- DuckDB uses `?` placeholders; Postgres uses `%s`
- DuckDB: `conn.execute()`; Postgres: `cursor.execute()`
- `INSERT OR REPLACE` is DuckDB syntax → Postgres uses `ON CONFLICT DO UPDATE`
- Postgres transactions abort on ANY error — use autocommit=True for DDL-style init
- Always check `BACKEND == "postgres"` vs `"duckdb"` and branch accordingly (see auth.py pattern)
- For test isolation: use `monkeypatch.delenv("DATABASE_URL", raising=False)` and a tmp_path duckdb

### Build: qa-results/review-decisions.json

Create as an empty JSON array. This is the append-only storage file.

```json
[]
```

### Build: web/routes_admin.py — APPEND ONLY

Append exactly 1 new endpoint to the BOTTOM of routes_admin.py. Do NOT touch any existing route.

Endpoint: POST /admin/qa-decision
- Auth: g.user must be admin (check g.user.get("is_admin"), abort 403 if not)
- Body (form fields):
  - `page` (str) — page path e.g. "/search"
  - `persona` (str) — active persona id from session, or "unknown"
  - `viewport` (str) — "desktop" | "mobile" | "tablet"
  - `dimension` (str) — which QA check dimension e.g. "cards", "centering"
  - `pipeline_score` (float) — numeric score from vision_score.py, e.g. 2.4
  - `tim_verdict` (str) — "accept" | "reject" | "note"
  - `sprint` (str) — sprint id, e.g. "qs10"
  - `note` (str, optional) — Tim's note, max 500 chars

Logic:
1. Validate tim_verdict is one of: accept, reject, note
2. Build decision dict (all fields above + "timestamp": datetime.utcnow().isoformat() + "Z")
3. Read qa-results/review-decisions.json (handle missing file gracefully — treat as [])
4. Append new decision, write back atomically (write to .tmp, rename)
5. Also remove the corresponding entry from qa-results/pending-reviews.json if present
   (match on page + dimension + sprint; handle missing file gracefully)
6. Return HTMX snippet: brief confirmation with verdict color
   - accept → --signal-green: "Accepted"
   - reject → --signal-red: "Rejected — flagged for fix"
   - note → --accent: "Noted"

Atomic write pattern:
```python
import json, os, tempfile

def _atomic_write_json(path: str, data) -> None:
    dir_ = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False) as f:
        json.dump(data, f, indent=2)
        tmp = f.name
    os.replace(tmp, path)
```

### Build: web/templates/fragments/feedback_widget.html — ADD review panel

Read the full current file first.

Add a second admin-only section BELOW the persona panel (which 2A added). If 2A's persona panel
is not visible in your worktree's copy of the file, add your panel immediately below the
`{% if g.user and g.user.get('is_admin') %}` block that wraps the form — or create a new one.

Structure:
```jinja2
{% if g.user and g.user.get('is_admin') %}
<div id="qa-review-panel" style="margin-bottom:var(--space-4);padding-bottom:var(--space-4);border-bottom:1px solid var(--glass-border);">
  <!-- pending badge + Accept/Reject/Note controls -->
</div>
{% endif %}
```

Inside the panel:

1. Header row (flex, space-between):
   - Left: "QA Reviews" label in --mono --text-xs --text-secondary
   - Right: badge showing pending count
     ```jinja2
     {% set pending_count = namespace(n=0) %}
     {# Try to read pending-reviews.json count — safe default to 0 #}
     <span id="qa-pending-badge" style="font-family:var(--mono);font-size:var(--text-xs);
       color:var(--accent);background:var(--accent-glow);border:1px solid var(--accent-ring);
       border-radius:3px;padding:1px 6px;">
       {{ pending_count.n }} pending
     </span>
     ```
     Note: the badge count is best served via a server-side context variable. In the route
     that renders the page including feedback_widget.html, inject `qa_pending_count` into the
     template context. For now, default to 0 and note this as a follow-up for T0.

2. Hidden fields (for the HTMX form):
   ```html
   <input type="hidden" id="qa-page" name="page" value="">
   <input type="hidden" id="qa-persona" name="persona" value="">
   <input type="hidden" id="qa-viewport" name="viewport" value="">
   <input type="hidden" id="qa-dimension" name="dimension" value="">
   <input type="hidden" id="qa-score" name="pipeline_score" value="">
   <input type="hidden" id="qa-sprint" name="sprint" value="qs10">
   <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
   ```

3. Context display (what is currently being reviewed):
   `<div id="qa-context" style="font-family:var(--mono);font-size:var(--text-xs);color:var(--text-tertiary);margin-top:var(--space-2);">No item selected</div>`

4. Note input:
   ```html
   <textarea id="qa-note" name="note" rows="2" class="form-input"
     placeholder="Why? (optional — this is training data)"
     style="margin-top:var(--space-2);font-size:var(--text-xs);resize:vertical;"></textarea>
   ```

5. Three verdict buttons (flex row, gap 8px):
   - Accept: class="action-btn", style="flex:1;padding:6px;font-size:var(--text-xs);color:var(--signal-green);border-color:var(--signal-green);"
     hx-post="/admin/qa-decision", hx-target="#qa-result", hx-swap="innerHTML",
     hx-include="#qa-review-panel", hx-vals='{"tim_verdict":"accept"}'
     Text: "Accept"
   - Note: class="action-btn", style same but accent colors
     hx-vals='{"tim_verdict":"note"}', Text: "Note"
   - Reject: class="action-btn", style same but signal-red colors
     hx-vals='{"tim_verdict":"reject"}', Text: "Reject"

6. Result span: `<span id="qa-result" style="font-family:var(--mono);font-size:var(--text-xs);"></span>`

Add a small JS block (inside a `<script nonce="{{ csp_nonce }}">`) to expose a global function
`window.qaLoadItem(item)` that populates the hidden fields and context display:
```javascript
window.qaLoadItem = function(item) {
    document.getElementById('qa-page').value = item.page || '';
    document.getElementById('qa-persona').value = item.persona || '';
    document.getElementById('qa-viewport').value = item.viewport || '';
    document.getElementById('qa-dimension').value = item.dimension || '';
    document.getElementById('qa-score').value = item.pipeline_score || '';
    document.getElementById('qa-sprint').value = item.sprint || 'qs10';
    var ctx = document.getElementById('qa-context');
    if (ctx) {
        ctx.textContent = (item.page || '?') + ' · ' + (item.dimension || '?') + ' · ' + (item.pipeline_score || '?') + '/5';
    }
    document.getElementById('qa-result').textContent = '';
};
```

DESIGN RULES (mandatory):
- No inline hex colors. Only CSS custom properties from docs/DESIGN_TOKENS.md.
- Font: --mono for labels/code/data, --sans for prose.
- Log the new "qa-review-panel" component to docs/DESIGN_COMPONENT_LOG.md if it does not already exist.

### Build: tests/test_accept_reject_log.py

Write a self-contained pytest file. Pattern from tests/test_admin_health.py.

Tests to write:
1. test_qa_decision_requires_admin
   POST /admin/qa-decision as non-admin → 403

2. test_qa_decision_accept_writes_file(tmp_path, monkeypatch)
   Monkeypatch QA_STORAGE_DIR to str(tmp_path)
   POST /admin/qa-decision as admin with tim_verdict="accept", page="/search", dimension="cards",
   pipeline_score="2.4", sprint="qs10", note="looks fine"
   → response 200
   → qa-results/review-decisions.json in tmp_path contains 1 entry
   → entry has tim_verdict="accept", page="/search", "timestamp" key present

3. test_qa_decision_reject_appends(tmp_path, monkeypatch)
   Monkeypatch QA_STORAGE_DIR to str(tmp_path)
   Write an initial review-decisions.json with 1 existing entry in tmp_path/review-decisions.json
   POST /admin/qa-decision with tim_verdict="reject"
   → review-decisions.json now has 2 entries

4. test_qa_decision_invalid_verdict
   POST /admin/qa-decision as admin with tim_verdict="maybe"
   → response 400 or contains error text (invalid verdict)

5. test_qa_decision_missing_file_graceful(tmp_path, monkeypatch)
   Monkeypatch QA_STORAGE_DIR to str(tmp_path) (no existing review-decisions.json)
   POST /admin/qa-decision with tim_verdict="note"
   → response 200 (no crash on missing file)
   → review-decisions.json created with 1 entry

6. test_pending_reviews_pruned_on_decision(tmp_path, monkeypatch)
   Monkeypatch QA_STORAGE_DIR to str(tmp_path)
   Write tmp_path/pending-reviews.json with a matching entry (page="/search", dimension="cards", sprint="qs10")
   POST /admin/qa-decision with matching fields + tim_verdict="accept"
   → pending-reviews.json entry for that item is removed (file still valid JSON, entry gone)

Note on QA_STORAGE_DIR: routes_admin.py defines it as:
`QA_STORAGE_DIR = os.environ.get("QA_STORAGE_DIR", "qa-results")`
Monkeypatch via `monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))` AND patch the module-level
variable: `monkeypatch.setattr(web.routes_admin, "QA_STORAGE_DIR", str(tmp_path))`

### Test
```bash
source .venv/bin/activate && pytest tests/test_accept_reject_log.py -v --tb=short
```
All 6 tests must pass.

Full suite:
```bash
source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
```

### Design Lint
```bash
source .venv/bin/activate && python scripts/design_lint.py --files web/templates/fragments/feedback_widget.html --quiet
```
Record score.

### Scenarios
APPEND to scenarios-t2-sprint87.md (the file 2A created — if it does not exist in your worktree, create it):

Add 2-3 scenarios:
- Tim sees pending review badge count in admin widget
- Tim accepts a borderline visual QA item with a note explaining why
- Tim rejects a layout regression; it remains in pending-reviews.json for fix tracking
- Accept/Reject/Note decisions persist in review-decisions.json as training data

### Output Files
- scenarios-t2-sprint87.md (APPEND — do not overwrite 2A's entries)
- CHANGELOG-t2-sprint87.md (APPEND — brief entry for 2B work)

### Commit
```bash
git add web/templates/fragments/feedback_widget.html web/routes_admin.py \
        qa-results/review-decisions.json tests/test_accept_reject_log.py \
        scenarios-t2-sprint87.md CHANGELOG-t2-sprint87.md docs/DESIGN_COMPONENT_LOG.md
git commit -m "feat: Accept/Reject/Note log in admin widget for visual QA verdicts (QS10 T2-B)"
```

### Report your branch name
After committing, output:
AGENT 2B COMPLETE — branch: [your worktree branch name] — tests: [N passed]
""")
```

---

## Post-Agent: Merge + Push

After BOTH agents complete, run the following from the main repo root:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Collect branch names from agent output lines
# e.g. "AGENT 2A COMPLETE — branch: claude/sharp-abc"
# e.g. "AGENT 2B COMPLETE — branch: claude/cool-xyz"

# Merge 2A first (2B extends 2A's widget work — merge order matters)
git merge <2A-branch> --no-ff --no-edit

# Merge 2B (extends 2A's changes)
git merge <2B-branch> --no-ff --no-edit

# Resolve any conflict in feedback_widget.html:
# Keep both panels — 2A's persona panel above, 2B's review panel below.
# The Jinja2 {% if g.user and g.user.get('is_admin') %} guards are additive.

# Concatenate per-agent output files
cat scenarios-t2-sprint87.md >> scenarios-pending-review.md 2>/dev/null
cat CHANGELOG-t2-sprint87.md >> CHANGELOG.md 2>/dev/null

# Design lint on modified template
source .venv/bin/activate
python scripts/design_lint.py --files web/templates/fragments/feedback_widget.html --quiet

# Full test suite
source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# Expect: all passing (2A added 6 tests, 2B added 6 tests = 12 new)

# Push
git push origin main
```

**Conflict resolution for feedback_widget.html:**
If both agents modified the same section, the correct resolution is:
1. Keep 2A's persona panel (id="persona-panel") as the first admin section
2. Keep 2B's review panel (id="qa-review-panel") as the second admin section
3. Both inside separate `{% if g.user and g.user.get('is_admin') %}` guards
4. Both `<script>` blocks kept (2A's persona JS and 2B's `window.qaLoadItem`)

---

## CHECKQUAD (Terminal 2 Close)

### MERGE
- Both agent branches merged to main
- No conflicts unresolved
- git push origin main confirmed

### ARTIFACT — Session Report

Write `qa-drop/qs10-t2-session.md`:
```
# QS10 T2 Session Report

**Terminal:** T2 — Admin QA Tools
**Sprint:** QS10
**Date:** 2026-02-28

## Agents

| Agent | Task | Status | Tests |
|-------|------|--------|-------|
| 2A | Persona Impersonation Dropdown | PASS/FAIL | N/6 |
| 2B | Accept/Reject Log | PASS/FAIL | N/6 |

## Files Modified
- web/admin_personas.py (NEW)
- web/templates/fragments/feedback_widget.html (MODIFIED)
- web/routes_admin.py (APPENDED: 3 new endpoints)
- qa-results/review-decisions.json (NEW)
- tests/test_admin_impersonation.py (NEW)
- tests/test_accept_reject_log.py (NEW)

## Test Results
- New tests: 12 (6 per agent)
- All passing: YES/NO
- Regressions: NONE / [describe]

## Design Lint
- feedback_widget.html score: [N]/5
- Violations: NONE / [describe]

## Blocked Items
[List any BLOCKED-FIXABLE or BLOCKED-EXTERNAL items, or "none"]

## Visual QA Checklist (for DeskCC Stage 2)
- [ ] ?admin=1 shows persona dropdown in feedback widget modal
- [ ] Selecting "Beta Active" and clicking Apply shows "Persona: Beta Active (3 watches)" status
- [ ] /admin/reset-impersonation clears persona state
- [ ] QA review panel shows "0 pending" badge when no pending-reviews.json
- [ ] Accept/Reject/Note buttons POST to /admin/qa-decision and show verdict confirmation
- [ ] Non-admin users see no persona or review panel in feedback widget
```

### CAPTURE
- scenarios-t2-sprint87.md entries appended to scenarios-pending-review.md
- CHANGELOG-t2-sprint87.md entries appended to CHANGELOG.md
- qa-drop/qs10-t2-session.md written

### HYGIENE CHECK
```bash
git worktree list  # confirm both worktrees are gone after merge
git worktree prune
```

### SIGNAL DONE
Output to T0:
```
T2 DONE
  2A persona impersonation: [PASS/FAIL] — [N]/6 tests
  2B accept/reject log:     [PASS/FAIL] — [N]/6 tests
  Design lint widget:       [N]/5
  Scenarios:                [N] total
  Blocked:                  NONE / [item]
  Branch t2/sprint-87 merged and pushed to main
```

T0 takes over for: full test suite validation, consolidation, prod gate, promotion.
