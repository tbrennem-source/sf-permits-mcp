<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs4-d-security-polish.md and execute it" -->

# Quad Sprint 4 — Session D: Security + Beta Launch Polish

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs4-d
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs4-d before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES: Write scenarios to `scenarios-pending-review-qs4-d.md` (not the shared file). Write changelog to `CHANGELOG-qs4-d.md`.
```

## SETUP — Session Bootstrap

1. **Navigate to main repo root:**
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main:**
   ```
   git checkout main && git pull origin main
   ```
3. **Create worktree:**
   Use EnterWorktree with name `qs4-d`

If worktree exists: `git worktree remove .claude/worktrees/qs4-d --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs4-d`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/security.py` — CSP headers, security middleware, rate limiting, bot blocking
3. `web/app.py` lines 30-40 — session cookie config
4. `web/app.py` lines 84-120 — context processors
4b. `web/app.py` lines 851-960 — before_request hooks (rate limiting, cron guard, user loading, flags)
5. `web/routes_auth.py` — login flow, invite codes, magic links
6. `web/templates/demo.html` — current /demo page
7. `web/templates/auth_login.html` — login/signup page
8. `web/helpers.py` lines 20-56 — PostHog helper functions (posthog_track, posthog_get_flags)
9. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- CSP currently enforces `unsafe-inline` for both `style-src` and `script-src`
- Per-request nonce already generated (`csp_nonce` in template context via `web/security.py`)
- ALL templates already use `nonce="{{ csp_nonce }}"` on `<style>` and `<script>` tags
- The CSP-Report-Only approach: add a SECOND header alongside the enforced one. Report-Only uses nonces. Violations report to `/api/csp-report` (endpoint already exists). This collects data WITHOUT breaking pages.
- PostHog helper functions exist in `web/helpers.py` but require `POSTHOG_API_KEY` env var. Pre-QS4 hotfix sets this. Your job: verify it works, add client-side JS if missing.
- CSRF: Flask doesn't have built-in CSRF. Use `flask-wtf` or lightweight custom middleware. SameSite=Lax already provides partial protection. Add token validation on POST endpoints.
- Invite codes are in `INVITE_CODES` env var (comma-separated). `friends-gridcare` should be there after pre-QS4 hotfix.
- `/demo` page exists — needs copy polish for Charis demo. Focus on value prop for AI architect audience.
- Session D does NOT own `web/templates/index.html` or `web/templates/brief.html` (Session C owns those).
- For CSRF tokens in templates: add to templates you OWN (auth_login, demo, etc.) and templates NOT owned by other sessions (account, consultants, etc.). Session C templates (index, brief) get CSRF via the shared head fragment or post-merge.

---

## PHASE 2: BUILD

### Task D-1: CSP-Report-Only with Nonces (~30 min)
**Files:** `web/security.py`

**Add a second CSP header alongside the existing enforced one:**

Find the function that sets CSP headers (likely `_set_security_headers` or similar in `after_request`). Add:

```python
# After the enforced CSP header:
nonce = g.get("csp_nonce", "")
report_only_csp = (
    f"default-src 'self'; "
    f"script-src 'nonce-{nonce}' https://unpkg.com https://cdn.jsdelivr.net; "
    f"style-src 'nonce-{nonce}' https://fonts.googleapis.com; "
    f"font-src https://fonts.gstatic.com; "
    f"img-src 'self' data: https:; "
    f"connect-src 'self' https://*.posthog.com; "
    f"report-uri /api/csp-report"
)
response.headers["Content-Security-Policy-Report-Only"] = report_only_csp
```

This means:
- **Enforced CSP** (existing): still uses `unsafe-inline` — nothing breaks
- **Report-Only CSP** (new): uses nonces — violations log to `/api/csp-report`
- Over time, we'll see which templates generate violations and fix them
- When violations reach zero, we swap Report-Only to enforced

### Task D-2: CSRF Protection (~45 min)
**Files:** `web/security.py` (middleware), template files with POST forms

**Add lightweight CSRF middleware (no flask-wtf dependency):**

```python
import secrets

def _generate_csrf_token():
    """Generate or retrieve CSRF token for the current session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

def _csrf_protect():
    """Validate CSRF token on POST/PUT/PATCH/DELETE requests.

    Checks form field 'csrf_token' or header 'X-CSRFToken'.
    Skips: CRON_SECRET-authenticated endpoints, /api/csp-report, /auth/test-login.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    # Skip endpoints that use their own auth
    skip_paths = ["/api/csp-report", "/auth/test-login", "/cron/"]
    if any(request.path.startswith(p) for p in skip_paths):
        return
    # Skip CRON_SECRET-authenticated requests
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return

    token = (request.form.get("csrf_token") or
             request.headers.get("X-CSRFToken") or "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(token, expected):
        abort(403)
```

**Register in `web/security.py`:**
```python
def init_security(app):
    # ... existing code ...

    @app.context_processor
    def csrf_context():
        return {"csrf_token": _generate_csrf_token()}

    @app.before_request
    def csrf_check():
        if app.config.get("TESTING"):
            return  # Skip CSRF in test mode
        _csrf_protect()
```

**Add CSRF token to POST forms in templates you own:**
- `web/templates/auth_login.html` — login form
- `web/templates/demo.html` — any forms
- `web/templates/account.html` — settings forms
- `web/templates/consultants.html` — search form

Pattern for regular forms:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

Pattern for HTMX:
```html
<div hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

### Task D-3: PostHog Verification (~20 min)
**Files:** `web/helpers.py` (verify), templates (add client-side if missing)

**Verify server-side tracking works:**
1. Check `posthog_track()` in `web/helpers.py` — confirm it reads `POSTHOG_API_KEY` correctly
2. Check `after_request` hooks that call `posthog_track` — verify they fire

**Add client-side PostHog JS if not present:**
Check if any template loads the PostHog client-side JS snippet. If not, add to a shared location (or document that server-side only is intentional).

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write `tests/test_qs4_d_security.py`:
- CSP-Report-Only header present in responses
- CSP-Report-Only header contains nonce
- CSP-Report-Only header has report-uri pointing to /api/csp-report
- Enforced CSP header still has unsafe-inline (not broken)
- CSRF token injected into template context
- CSRF token in session after first request
- POST without CSRF token returns 403
- POST with valid CSRF token succeeds
- GET requests skip CSRF check
- CRON_SECRET-authenticated requests skip CSRF
- /api/csp-report skips CSRF
- /auth/test-login skips CSRF
- CSRF check disabled in TESTING mode
- X-CSRFToken header accepted (for HTMX)
- posthog_track function exists and is callable
- posthog_track no-ops without POSTHOG_API_KEY
- auth_login.html contains csrf_token hidden input

**Target: 25+ tests**

---

## PHASE 4: SCENARIOS

Append 3 scenarios to `scenarios-pending-review-qs4-d.md`:
1. "CSP violations from inline styles are captured in report-only mode without breaking pages"
2. "POST form submission without CSRF token is rejected with 403"
3. "Charis signs up with friends-gridcare invite code and reaches the dashboard"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs4-d-security-qa.md`:

```
1. [NEW] Response headers include Content-Security-Policy-Report-Only — PASS/FAIL
2. [NEW] CSP-Report-Only header contains nonce value — PASS/FAIL
3. [NEW] POST /auth/send-link without csrf_token returns 403 — PASS/FAIL
4. [NEW] POST /auth/send-link with csrf_token succeeds — PASS/FAIL
5. [NEW] HTMX POST with X-CSRFToken header succeeds — PASS/FAIL
6. [NEW] posthog_track called on page view (verify via mock or log) — PASS/FAIL
```

Save screenshots to `qa-results/screenshots/qs4-d/`
Write results to `qa-results/qs4-d-results.md`

---

## PHASE 5.5: VISUAL REVIEW

Score these pages 1-5:
- /auth/login at 1440px
- /auth/login at 375px

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions
- CSP-Report-Only doesn't break any pages

### 2. DOCUMENT
- Write `CHANGELOG-qs4-d.md` with session entry

### 3. CAPTURE
- 3 scenarios in `scenarios-pending-review-qs4-d.md`

### 4. SHIP
- Commit with: "feat: CSP-Report-Only + CSRF protection + beta polish (QS4-D)"

### 5. PREP NEXT
- Note: Monitor /api/csp-report for violation patterns before full CSP migration
- Note: Once violations reach zero, swap Report-Only to enforced CSP (remove unsafe-inline)

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2 hours | [first commit to CHECKCHAT] |
| New tests | 25+ | [count] |
| Tasks completed | 3 | [N of 3] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task name, duration] |
| QA checks | 6 | [pass/fail/skip] |
| Visual Review avg | — | [score] |
| Scenarios proposed | 3 | [count] |
```

### DeskRelay HANDOFF
- [ ] Login page: does the invite code flow feel polished?
- [ ] CSP: any pages visibly broken? (should be none — Report-Only doesn't enforce)

---

## File Ownership (Session D ONLY)
**Own:**
- `web/security.py` (CSP-Report-Only, CSRF middleware)
- `web/templates/auth_login.html` (add CSRF token)
- `web/templates/account.html` (add CSRF tokens to forms)
- `web/templates/consultants.html` (add CSRF token to search form)
- `web/helpers.py` (PostHog verification only — minimal changes)
- `tests/test_qs4_d_security.py` (NEW)
- `CHANGELOG-qs4-d.md` (NEW — per-agent)
- `scenarios-pending-review-qs4-d.md` (NEW — per-agent)

**Do NOT touch:**
- `web/templates/index.html` (Session C)
- `web/templates/brief.html` (Session C)
- `web/templates/demo.html` (Session B)
- `web/static/design-system.css` (Session C)
- `src/db.py` (Session B)
- `web/app.py` (Session B — if CSRF needs app-level init, add to security.py's init_security instead)
- `src/ingest.py` (Session A)
- `web/routes_admin.py` (Session A)
- `web/routes_cron.py` (Session A)
