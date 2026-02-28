# QS10 Terminal 4: Beta Onboarding + First Tier Gate (Sprint 89)

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn Agent 4A using the Agent tool (subagent_type="general-purpose", model="sonnet", isolation="worktree"). Wait for 4A to complete. Merge 4A to main. Then spawn Agent 4B. Do NOT summarize or ask for confirmation — execute now. After both agents complete, run Post-Agent merge, then CHECKQUAD.

You are the orchestrator for Sprint 89. Spawn 2 SEQUENTIAL build agents — Agent 4A must FULLY COMPLETE (commit + branch pushed) before you spawn Agent 4B. Agent 4B depends on 4A's `web/tier_gate.py` decorator. Do NOT run the full test suite — T0 handles that in the merge ceremony.

## Pre-Flight (30 seconds — T0 already verified tests + prod health)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
echo "T4 start: $(git rev-parse --short HEAD)"
```

## File Ownership Matrix

| Agent | Files Owned | Files Modified |
|-------|-------------|----------------|
| 4A | `web/tier_gate.py` (NEW), `web/templates/onboarding/welcome.html` (NEW), `web/templates/onboarding/add_property.html` (NEW), `web/templates/onboarding/severity_preview.html` (NEW), `web/templates/fragments/tier_gate_teaser.html` (NEW), `tests/test_onboarding_flow.py` (NEW), `tests/test_tier_gate.py` (NEW) | `web/routes_auth.py` (append only — ~60 lines of new routes) |
| 4B | `tests/test_tier_gated_content.py` (NEW) | `web/routes_search.py` (existing AI routes only, NOT new T3 tool routes), `web/routes_property.py` (~15 lines on brief route), `web/templates/portfolio.html` (conditional teaser block), `web/templates/brief.html` (conditional teaser block) |

**Cross-agent overlap: ZERO. 4A and 4B touch different files.**

**DO NOT TOUCH:** `web/app.py`, `src/server.py`, `web/routes_api.py`, `scripts/*.py`, `web/templates/tools/*.html` (T3 owns), `CLAUDE.md`, `CHANGELOG.md`

## Merge Note for Post-Agent

T4 merges LAST in the quad sprint. When 4B modifies `web/routes_search.py`, T3's new tool routes will already be on main. 4B ONLY touches existing AI consultation routes — not the new tool routes added by T3. If there is a merge conflict on `routes_search.py`, resolve by keeping both T3's additions and 4B's changes.

---

## Standard Agent Preamble (verbatim in every agent prompt)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes — even a partial stub.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t4-sprint89.md (your scenarios file — write 2-5 scenarios)
  * CHANGELOG-t4-sprint89.md (your changelog entry)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -15

PROTOCOL — every agent follows this sequence:
1. READ — read all files listed in "Read First"
2. BUILD — implement the tasks
3. TEST — run pytest, fix failures
4. SCENARIOS — write 2-5 scenarios to your per-agent scenarios file
5. DESIGN TOKEN COMPLIANCE — if you created/modified any template:
   run `python scripts/design_lint.py --changed --quiet`
6. CHECKCHAT — write a summary: what shipped, tests added, scenarios written, BLOCKED items,
   Visual QA Checklist (list all pages/states needing human spot-check)

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit or savepoints for DDL
- CRON_WORKER env var needed for cron endpoint tests: monkeypatch.setenv("CRON_WORKER", "1")
- TESTING mode skips CSRF — always test CSRF forms manually on staging
```

---

## SEQUENTIAL EXECUTION: 4A FIRST, THEN 4B

**Spawn Agent 4A now. Wait for it to complete and push its branch before spawning 4B.**

---

## Agent 4A: Onboarding Flow + Tier Enforcement

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes — even a partial stub.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t4-sprint89.md
  * CHANGELOG-t4-sprint89.md
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -15

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- Postgres transactions abort on any error — use autocommit or savepoints for DDL
- TESTING mode skips CSRF — always test CSRF forms manually on staging

## YOUR TASK: Beta Invite Flow + Onboarding Wizard + @requires_tier Decorator

### File Ownership
CREATE (new files):
- web/tier_gate.py
- web/templates/onboarding/welcome.html
- web/templates/onboarding/add_property.html
- web/templates/onboarding/severity_preview.html
- web/templates/fragments/tier_gate_teaser.html
- tests/test_onboarding_flow.py
- tests/test_tier_gate.py

MODIFY (append only):
- web/routes_auth.py (~60 lines of new routes at the end)

DO NOT TOUCH: web/app.py, src/server.py, web/routes_api.py, scripts/*.py,
              web/templates/tools/*.html, CLAUDE.md, CHANGELOG.md

### Read First
- web/routes_auth.py (full file — understand Blueprint pattern, existing onboarding routes,
  existing INVITE_CODES usage, login_required decorator import, session/g patterns)
- web/auth.py (get_user_by_email, create_user, INVITE_CODES, validate_invite_code,
  subscription_tier field — understand what tier values exist: 'free', 'beta', 'premium')
- web/helpers.py (login_required decorator — how it works, what it checks)
- web/templates/fragments/head_obsidian.html (base template — CSRF meta tag location,
  existing htmx configRequest listener for CSRF injection)
- docs/DESIGN_TOKENS.md (FULL FILE — all tokens before writing any template)
- web/templates/onboarding_step1.html (EXISTING — understand the existing onboarding
  wizard pattern so your new templates are consistent in structure)

### Context: What Already Exists

The existing onboarding system (Sprint 64):
- /onboarding/step/1, /step/2, /step/3 — 3-step wizard (add property → preferences → complete)
- onboarding_complete field on user record
- subscription_tier field on user record ('free', 'beta', 'premium')
- The INVITE_CODES env var already controls who can sign up

Your job is to ADD the beta invite endpoint and the @requires_tier decorator. Do NOT rewrite
the existing onboarding wizard — the new onboarding templates in web/templates/onboarding/
are for the NEW beta-specific flow (/beta/join?code=xxx → welcome → add property → preview).

### Build

#### Task A-1: Beta Invite Endpoint (web/routes_auth.py — APPEND ONLY)

Append ~60 lines to web/routes_auth.py. Add a /beta/join route:

```python
# ---------------------------------------------------------------------------
# Beta invite flow (Sprint 89)
# ---------------------------------------------------------------------------

@bp.route("/beta/join")
def beta_join():
    \"\"\"Validate beta invite code and route to onboarding wizard.

    GET /beta/join?code=<invite_code>
    - Valid code + unauthenticated: redirect to login with code preserved
    - Valid code + authenticated free user: upgrade tier to beta, start onboarding
    - Valid code + authenticated beta/premium: redirect to dashboard (already upgraded)
    - Invalid/missing code: render error page
    \"\"\"
    from web.auth import INVITE_CODES, validate_invite_code
    from src.db import execute_write

    code = request.args.get("code", "").strip()

    if not code or not validate_invite_code(code):
        return render_template(
            "onboarding/welcome.html",
            error="Invalid or expired invite code. Please check your invite link.",
            user=g.get("user"),
        ), 400

    if not g.get("user"):
        return redirect(url_for("auth.auth_login") + f"?invite_code={code}&referral_source=beta_invite")

    user = g.user
    current_tier = user.get("subscription_tier", "free")
    if current_tier in ("beta", "premium"):
        return redirect(url_for("index"))

    try:
        execute_write(
            "UPDATE users SET subscription_tier = 'beta' WHERE user_id = %s",
            (user["user_id"],),
        )
        session["tier_just_upgraded"] = True
    except Exception:
        logging.warning("beta_join: failed to upgrade tier", exc_info=True)

    return redirect(url_for("auth.beta_onboarding_welcome"))


@bp.route("/beta/onboarding/welcome")
@login_required
def beta_onboarding_welcome():
    return render_template("onboarding/welcome.html", user=g.user)


@bp.route("/beta/onboarding/add-property")
@login_required
def beta_onboarding_add_property():
    return render_template("onboarding/add_property.html", user=g.user)


@bp.route("/beta/onboarding/severity-preview")
@login_required
def beta_onboarding_severity_preview():
    return render_template("onboarding/severity_preview.html", user=g.user)
```

Import note: `login_required` is already imported at the top of routes_auth.py. Do NOT add
a duplicate import. `session` and `redirect`, `url_for`, `render_template`, `request`, `g`
are already imported. Add only what is missing.

#### Task A-2: @requires_tier Decorator (web/tier_gate.py — NEW FILE)

Create `web/tier_gate.py` — the CRITICAL DELIVERABLE that Agent 4B depends on.

```python
\"\"\"Tier gate decorator for subscription-gated routes.

Provides @requires_tier('beta') and @requires_tier('premium') decorators.
Used to gate content behind subscription tiers.

Tier hierarchy:
  free < beta < premium

Usage:
    from web.tier_gate import requires_tier

    @bp.route('/some-feature')
    @login_required
    @requires_tier('beta')
    def some_feature():
        return render_template('some_feature.html')

    # Or for teaser rendering (non-redirect behavior):
    @bp.route('/portfolio')
    @login_required
    def portfolio():
        if not has_tier(g.user, 'beta'):
            return render_template('portfolio.html', tier_locked=True, ...)
        return render_template('portfolio.html', tier_locked=False, ...)
\"\"\"
import functools
import logging

from flask import g, redirect, render_template, url_for

# Tier hierarchy: index = access level (higher = more access)
_TIER_LEVELS = {
    "free": 0,
    "beta": 1,
    "premium": 2,
}


def _user_tier_level(user: dict) -> int:
    \"\"\"Return numeric tier level for a user dict. Defaults to 0 (free).\"\"\"
    tier = user.get("subscription_tier", "free") or "free"
    return _TIER_LEVELS.get(tier, 0)


def has_tier(user: dict, required_tier: str) -> bool:
    \"\"\"Return True if user meets or exceeds required_tier.\"\"\"
    required_level = _TIER_LEVELS.get(required_tier, 0)
    return _user_tier_level(user) >= required_level


def requires_tier(required_tier: str):
    \"\"\"Decorator: gate a route behind a subscription tier.

    Behavior by user state:
    - Anonymous: redirect to /auth/login
    - Free (below required tier): render tier_gate_teaser.html fragment
    - Beta/Premium (meets required tier): render full content (calls wrapped fn)

    Args:
        required_tier: 'beta' or 'premium'

    Example:
        @bp.route('/tool')
        @login_required
        @requires_tier('beta')
        def tool():
            return render_template('tool.html')
    \"\"\"
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")

            if not user:
                return redirect(url_for("auth.auth_login"))

            if not has_tier(user, required_tier):
                logging.debug(
                    "tier_gate: user %s (tier=%s) blocked from %s (requires %s)",
                    user.get("user_id"),
                    user.get("subscription_tier", "free"),
                    fn.__name__,
                    required_tier,
                )
                return render_template(
                    "fragments/tier_gate_teaser.html",
                    required_tier=required_tier,
                    current_tier=user.get("subscription_tier", "free"),
                    user=user,
                ), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

#### Task A-3: Onboarding Templates (web/templates/onboarding/)

Create `web/templates/onboarding/` directory (mkdir in Python or bash).

**welcome.html** — Step 1: Welcome to Beta
- Extends base or uses head_obsidian.html pattern (match existing onboarding_step1.html)
- Headline: "Welcome to SF Permits AI Beta"
- Subhead: "You're in. Let's get you set up in 2 minutes."
- 3-step progress indicator (step 1 active)
- CTA button: "Get Started" → links to /beta/onboarding/add-property
- If `error` var set: show error message in a glass-card with --signal-warn color
- CSRF token not needed (GET-only page, no form)
- Design tokens: glass-card, --sans font, ghost-cta for CTA, obsidian background

**add_property.html** — Step 2: Add First Property
- Headline: "Add your first property to watch"
- Form: address text input + "Add Property" submit button
- POST to existing /portfolio/import or /add-watch endpoint (check routes_property.py for
  the correct endpoint — do NOT invent a new one; use what exists)
- After submit: redirect to /beta/onboarding/severity-preview
- Progress indicator: step 2 active
- CSRF: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
- Design tokens: glass-card, --mono for input, ghost-cta for submit

**severity_preview.html** — Step 3: Severity Preview
- Headline: "Here's what we track for your properties"
- 3-card grid showing severity signal categories: Inspection History, Complaint Patterns, Permit Status
- Each card: icon (use ASCII/Unicode if no icon system exists), title, 1-sentence description
- CTA: "Go to Dashboard" → url_for('index') — links to /
- Marks onboarding_complete via a HTMX POST or a regular form POST to /onboarding/dismiss
  (existing endpoint in routes_auth.py — do NOT create a duplicate)
- Progress indicator: step 3 active
- Design tokens: glass-card, obs-table for data examples, ghost-cta for CTA

#### Task A-4: Tier Gate Teaser Fragment (web/templates/fragments/tier_gate_teaser.html)

Create `web/templates/fragments/tier_gate_teaser.html`:
- A self-contained fragment (no extends — it's returned directly from the decorator)
- Glass-card container with blur/frosted effect
- Headline: "This feature is available for Beta users"
- 2-sentence value prop: "Get severity analysis, portfolio tracking, and AI consultation..."
- CTA: ghost-cta button → /auth/login or /beta/join (depending on whether user exists)
- Pass `required_tier` and `current_tier` vars for conditional copy
- Design tokens: glass-card with `backdrop-filter: blur(8px)`, ghost-cta, --sans font
- Mobile-responsive at 375px: stack layout, full-width CTA

#### Task A-5: Design Token Compliance

After building all templates:
```bash
source .venv/bin/activate
python scripts/design_lint.py --changed --quiet
```
Fix any violations. Target 4/5 or 5/5.

### Tests (tests/test_onboarding_flow.py + tests/test_tier_gate.py)

**tests/test_onboarding_flow.py:**
- test_beta_join_invalid_code_returns_400
- test_beta_join_unauthenticated_redirects_to_login
- test_beta_join_valid_code_upgrades_tier (mock execute_write, mock INVITE_CODES)
- test_beta_join_already_beta_redirects_to_dashboard
- test_beta_onboarding_welcome_requires_auth
- test_beta_onboarding_add_property_requires_auth
- test_beta_onboarding_severity_preview_requires_auth
- test_beta_onboarding_welcome_renders

**tests/test_tier_gate.py:**
- test_has_tier_free_user_fails_beta_check
- test_has_tier_beta_user_passes_beta_check
- test_has_tier_premium_user_passes_beta_check
- test_has_tier_premium_user_passes_premium_check
- test_has_tier_beta_user_fails_premium_check
- test_requires_tier_anonymous_redirects_to_login
- test_requires_tier_free_user_gets_teaser (mock g.user with free tier, check 403)
- test_requires_tier_beta_user_sees_content (mock g.user with beta tier)
- test_requires_tier_decorator_preserves_function_name

Use Flask test client + app fixture from conftest.py. Mock `g.user` via the test client
session or monkeypatch. Check existing tests for the correct app fixture pattern.

### Scenarios

Write 2-5 scenarios to scenarios-t4-sprint89.md using this exact format:

## SUGGESTED SCENARIO: [name]
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** [expediter | homeowner | architect | admin]
**Starting state:** [what's true before the action]
**Goal:** [what the user is trying to accomplish]
**Expected outcome:** [success criteria]
**Edge cases seen in code:** [optional]
**CC confidence:** high | medium | low
**Status:** PENDING REVIEW

Suggested scenarios:
1. New beta user clicks invite link and completes 3-step onboarding
2. Free user encounters tier gate teaser on gated feature
3. Already-beta user clicks invite link again — no double upgrade
4. Unauthenticated user hits /beta/join — redirected to login with code preserved

### Commit Message
feat: beta invite flow + 3-step onboarding + @requires_tier decorator (Sprint 89-4A)

### CHECKCHAT
Write a summary including:
- What shipped (tier_gate.py, 3 onboarding templates, teaser fragment, routes)
- Test count added
- Design lint score: [N]/5
- Scenarios written (count)
- BLOCKED items (if any)
- Visual QA Checklist:
  - [ ] /beta/join?code=valid-code upgrades tier and redirects to welcome
  - [ ] /beta/join?code=bad-code shows error state on welcome.html
  - [ ] /beta/onboarding/welcome renders correctly (progress step 1)
  - [ ] /beta/onboarding/add-property renders form (progress step 2)
  - [ ] /beta/onboarding/severity-preview renders 3-card grid (progress step 3)
  - [ ] Tier gate teaser renders correctly for free user (glass-card, blur, CTA)
  - [ ] Teaser mobile layout at 375px — full-width CTA, stacked cards
""")
```

---

## WAIT FOR AGENT 4A TO COMPLETE

After Agent 4A finishes and you have its branch name, verify `web/tier_gate.py` exists on the branch:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git fetch origin
git show origin/<agent-4a-branch>:web/tier_gate.py | head -20
# Should show the requires_tier decorator. If empty or error, do NOT spawn 4B yet.
```

Once verified, merge 4A to main BEFORE spawning 4B so 4B can import from `web/tier_gate.py`:

```bash
git checkout main && git pull origin main
git merge <agent-4a-branch> --no-edit
git push origin main
```

Then spawn Agent 4B.

---

## Agent 4B: Tier-Gated Content Application

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. Violating this rule destroys other agents' work.

RULES:
- DO NOT modify ANY file outside your owned list.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- OUTPUT FILES (per-agent — NEVER write to shared files directly):
  * scenarios-t4-sprint89.md (APPEND to existing, do NOT overwrite)
  * CHANGELOG-t4-sprint89.md (APPEND to existing, do NOT overwrite)
- TEST COMMAND: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short 2>&1 | tail -15

CSS VARIABLE MAPPING: --mono for data, --sans for prose. NOT --font-display/--font-body.

Known DuckDB/Postgres Gotchas:
- INSERT OR REPLACE → ON CONFLICT DO UPDATE
- ? placeholders → %s
- conn.execute() → cursor.execute()
- TESTING mode skips CSRF — always test CSRF forms manually on staging

## DEPENDENCY: Agent 4A has already shipped web/tier_gate.py to main.
## web/tier_gate.py contains: has_tier(), requires_tier(), _TIER_LEVELS
## Import it as: from web.tier_gate import has_tier, requires_tier

## YOUR TASK: Apply Tier Gates to Portfolio, Brief, and AI Consultation

### File Ownership
CREATE (new files):
- tests/test_tier_gated_content.py

MODIFY (existing files):
- web/routes_search.py (ONLY existing AI consultation routes — NOT T3's new tool routes)
- web/routes_property.py (~15 lines on the /brief/<id> route)
- web/templates/portfolio.html (add conditional teaser block)
- web/templates/brief.html (add conditional teaser block)

DO NOT TOUCH: web/app.py, src/server.py, web/routes_api.py, scripts/*.py,
              web/templates/tools/*.html (T3 owns), web/tier_gate.py (4A owns),
              web/routes_auth.py (4A owns), CLAUDE.md, CHANGELOG.md

### Read First
- web/tier_gate.py (FULL FILE — understand has_tier(), requires_tier() interface)
- web/routes_property.py (find the /portfolio route at line ~531 and /brief route — read
  the full function signatures and what data they pass to templates)
- web/routes_search.py (find /lookup and /ask routes — lines ~195, ~240, ~317 —
  read full functions to understand how AI results are returned to templates)
- web/templates/portfolio.html (FULL FILE — understand template structure before modifying)
- web/templates/brief.html (FULL FILE — understand template structure before modifying)
- web/templates/fragments/tier_gate_teaser.html (from Agent 4A — understand the fragment
  to know what vars it needs: required_tier, current_tier, user)
- docs/DESIGN_TOKENS.md (FULL FILE — before any template changes)

### IMPORTANT: routes_search.py Merge Constraint

T3's agents added new tool routes to web/routes_search.py. Those routes are at the BOTTOM
of the file or in a clearly-marked section. DO NOT touch T3's routes.

Only modify:
- The /ask route (line ~317) — add tier gate for AI consultation response generation
- The /lookup route (line ~240) — add tier_locked context var for template rendering

If you cannot clearly identify which routes belong to T3 vs. existing routes, only touch
/ask and /lookup. Mark anything uncertain as BLOCKED rather than guessing.

### Build

#### Task B-1: Portfolio Tier Gate (web/routes_property.py + web/templates/portfolio.html)

In web/routes_property.py, find the `portfolio()` function (~line 531).

Add tier check AFTER the login_required check:
```python
from web.tier_gate import has_tier

@bp.route("/portfolio")
@login_required
def portfolio():
    # Tier gate: free users see teaser
    tier_locked = not has_tier(g.user, 'beta')
    if tier_locked:
        return render_template(
            "portfolio.html",
            tier_locked=True,
            required_tier='beta',
            current_tier=g.user.get('subscription_tier', 'free'),
            user=g.user,
            watches=[],
            data={},
        ), 200  # 200 not 403 — page renders, just with teaser content

    # ... existing portfolio logic unchanged below ...
```

In web/templates/portfolio.html, add at the TOP of the main content area (after nav):
```html
{% if tier_locked %}
  {% include 'fragments/tier_gate_teaser.html' %}
{% else %}
  {# existing portfolio content — UNCHANGED #}
{% endif %}
```

The teaser for portfolio should convey: track all your properties, get severity alerts,
see permit activity across your portfolio.

#### Task B-2: Brief Tier Gate (web/routes_property.py + web/templates/brief.html)

Find the morning brief route in web/routes_property.py (look for /brief/<id> or similar).

Add tier check — pass `tier_locked` context to the template:
```python
from web.tier_gate import has_tier  # (already imported from B-1)

# Inside the brief route, before render_template:
tier_locked = not has_tier(g.user, 'beta')
# Pass tier_locked=tier_locked to render_template
# Do NOT block free users from loading the page — just show teaser in template
```

In web/templates/brief.html, find the main severity analysis section and wrap it:
```html
{% if tier_locked %}
  {# Show brief header (property name, date) but blur the body #}
  <div class="brief-header">{{ ... }}</div>
  {% include 'fragments/tier_gate_teaser.html' %}
{% else %}
  {# existing full brief content — UNCHANGED #}
{% endif %}
```

The teaser for brief should convey: full severity analysis, permit change history,
AI-powered risk assessment.

#### Task B-3: AI Consultation Tier Gate (web/routes_search.py)

In the /ask route (line ~317), before the AI synthesis call, add a tier check.
Free users get a teaser response instead of the full AI analysis:

```python
from web.tier_gate import has_tier

# Inside ask() function, before calling _synthesize_with_ai or similar:
user = g.get("user")
if user and not has_tier(user, 'beta'):
    # Return teaser HTML response instead of AI analysis
    teaser_html = render_template(
        "fragments/tier_gate_teaser.html",
        required_tier='beta',
        current_tier=user.get('subscription_tier', 'free'),
        user=user,
    )
    # Return in the same format as existing AI responses
    # (check how the /ask route normally returns — match that format)
    return teaser_html, 200
```

Read the /ask route carefully first — it may return HTML (for HTMX) or JSON. Match the
existing response format. If anonymous: let the existing login check handle it.

#### Task B-4: Design Token Compliance

```bash
source .venv/bin/activate
python scripts/design_lint.py --changed --quiet
```
Fix any violations before committing. Target 4/5 or 5/5.

### Tests (tests/test_tier_gated_content.py)

Write comprehensive tests:
- test_portfolio_free_user_gets_200_with_teaser (tier_locked=True in context)
- test_portfolio_beta_user_sees_full_content (tier_locked=False)
- test_portfolio_requires_login (anonymous → redirect)
- test_brief_free_user_gets_tier_locked_context
- test_brief_beta_user_gets_full_content
- test_ask_free_user_gets_teaser_response (not full AI analysis)
- test_ask_anonymous_user_handled (no crash)
- test_ask_beta_user_proceeds_to_ai (does not get teaser)

Use the Flask test client and app fixture from conftest.py. Mock g.user via session or
monkeypatch to simulate different tier levels. Check existing test files for the correct
pattern — see tests/test_onboarding_flow.py (written by Agent 4A) for the app fixture.

### Scenarios

APPEND 2-3 scenarios to scenarios-t4-sprint89.md (do NOT overwrite what 4A wrote):

## SUGGESTED SCENARIO: Free user hits portfolio tier gate
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** homeowner
**Starting state:** User has free tier account, clicks Portfolio in nav
**Goal:** View their property portfolio
**Expected outcome:** Sees portfolio page with upgrade teaser — clear value prop,
  CTA to upgrade, not a hard 403 error
**Edge cases seen in code:** tier_locked=True still returns 200 so HTMX works correctly
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user asks a question, sees AI teaser
**Source:** Sprint 89 — AI Consultation Tier Gate
**User:** homeowner
**Starting state:** Free tier, types a question in the /ask search box
**Goal:** Get AI analysis of their permit situation
**Expected outcome:** Sees teaser card in search results explaining beta feature,
  with upgrade CTA — not a blank response or error
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user sees full AI consultation
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** expediter
**Starting state:** Beta tier account (upgraded via /beta/join)
**Goal:** Get AI analysis via /ask
**Expected outcome:** Full AI response — no teaser, no tier gate
**CC confidence:** high
**Status:** PENDING REVIEW

### Commit Message
feat: apply tier gates to portfolio, brief, and AI consultation (Sprint 89-4B)

### CHECKCHAT
Write a summary including:
- What shipped (tier gates on 3 surfaces, teaser integration)
- Test count added
- Design lint score: [N]/5
- Scenarios written (count appended to scenarios-t4-sprint89.md)
- BLOCKED items (if any — classify BLOCKED-FIXABLE or BLOCKED-EXTERNAL)
- Visual QA Checklist:
  - [ ] /portfolio — free user sees teaser (not blank, not error)
  - [ ] /portfolio — beta user sees full portfolio content
  - [ ] /brief/<id> — free user sees header + teaser, not full analysis
  - [ ] /brief/<id> — beta user sees full brief
  - [ ] /ask search — free user response contains teaser card
  - [ ] /ask search — beta user gets full AI response
  - [ ] Teaser CTA links work (upgrade flow navigates correctly)
  - [ ] Mobile: teaser readable at 375px on all 3 surfaces
""")
```

---

## Post-Agent: Merge + Push

After both agents complete (4A already merged above — merge 4B now):

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# 4A already merged before 4B was spawned — only merge 4B
git merge <agent-4b-branch> --no-edit

# If conflict on routes_search.py: keep both T3's routes AND 4B's tier gate changes.
# Resolve manually — T3 adds new routes, 4B modifies existing /ask and /lookup routes.

# Design lint on changed templates
source .venv/bin/activate
python scripts/design_lint.py --changed --quiet

# QA gate (Layer 1 — runs structural checks, non-blocking but review failures)
python scripts/qa_gate.py --changed-only 2>/dev/null || echo "qa_gate not available yet — T1 may not be merged"

# Concatenate per-agent output files (4A wrote first, 4B appended — check for dupes)
# scenarios-t4-sprint89.md and CHANGELOG-t4-sprint89.md are SHARED output files.
# Both agents write to the same file — it should already be consolidated.
# Just verify and append to shared files if not already done:
cat scenarios-t4-sprint89.md >> scenarios-pending-review.md 2>/dev/null && \
  echo "scenarios appended" || echo "scenarios-t4-sprint89.md missing"
cat CHANGELOG-t4-sprint89.md >> CHANGELOG.md 2>/dev/null && \
  echo "changelog appended" || echo "CHANGELOG-t4-sprint89.md missing"

git push origin main
```

## CHECKQUAD

```
T4 (Beta Onboarding + Tier Gate) COMPLETE

AGENTS:
  4A: Onboarding Flow + @requires_tier:    [PASS/FAIL]
      - web/tier_gate.py:                  [created/MISSING]
      - 3 onboarding templates:            [created/MISSING]
      - tier_gate_teaser.html fragment:    [created/MISSING]
      - tests/test_onboarding_flow.py:     [N tests]
      - tests/test_tier_gate.py:           [N tests]
      - Design lint:                       [N]/5
  4B: Tier-Gated Content:                  [PASS/FAIL]
      - /portfolio tier gate:              [applied/MISSING]
      - /brief tier gate:                  [applied/MISSING]
      - /ask tier gate:                    [applied/MISSING]
      - tests/test_tier_gated_content.py:  [N tests]
      - Design lint:                       [N]/5

SCENARIOS: [N] total in scenarios-t4-sprint89.md
PUSHED: [commit hash]

BLOCKED ITEMS (if any):
  [item] — BLOCKED-FIXABLE/BLOCKED-EXTERNAL
  [what was tried, why blocked, recommended next step]

VISUAL QA CHECKLIST (for DeskCC Stage 2):
  - [ ] /beta/join?code=<valid> — tier upgraded, redirects to welcome
  - [ ] /beta/join?code=bad — error state, no crash
  - [ ] /beta/onboarding/welcome — renders (step 1 progress)
  - [ ] /beta/onboarding/add-property — renders form (step 2 progress)
  - [ ] /beta/onboarding/severity-preview — renders 3 cards (step 3 progress)
  - [ ] /portfolio free user — teaser visible, not blank
  - [ ] /portfolio beta user — full content visible
  - [ ] /brief/<id> free user — header + teaser, no full analysis
  - [ ] /brief/<id> beta user — full brief
  - [ ] /ask free user — teaser card in search results
  - [ ] /ask beta user — full AI response
  - [ ] Mobile 375px: teaser readable on all 3 surfaces
  - [ ] Teaser CTA links navigate correctly
```
