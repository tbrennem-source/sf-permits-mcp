<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs3-d-analytics.md and execute it" -->

# Quad Sprint 3 — Session D: PostHog Analytics + Revenue Polish

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs3-d
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs3-d before any code changes.
```

## SETUP — Session Bootstrap

1. `cd /Users/timbrenneman/AIprojects/sf-permits-mcp`
2. `git checkout main && git pull origin main`
3. Use EnterWorktree with name `qs3-d`
4. `git tag pre-qs3-d`

If worktree exists: `git worktree remove .claude/worktrees/qs3-d --force 2>/dev/null; true`

---

## PHASE 1: READ

1. `CLAUDE.md` — project structure
2. `web/app.py` — before_request/after_request hooks. Session B also touches this file. Mark your changes with `# === QS3-D: POSTHOG TRACKING ===`
3. `web/helpers.py` — where you'll add PostHog helper
4. `web/templates/landing.html` — add PostHog JS + manifest link
5. `web/templates/index.html` — add PostHog JS + manifest link
6. `web/cost_tracking.py` — READ to understand existing cost tracking (DO NOT MODIFY)
7. `web/templates/admin_costs.html` — READ to understand existing cost dashboard (DO NOT MODIFY)
8. `web/routes_auth.py` — understand invite code system (validate_invite_code function)
9. `web/routes_misc.py` — sitemap route (you'll extend)
10. `scripts/release.py` — where you'll add api_usage DDL
11. `web/static/manifest.json` — already exists (Sprint 69 S4)
12. `scenario-design-guide.md` — for scenario-keyed QA

**Pre-flight audit confirmed:**
- `web/cost_tracking.py` EXISTS (250+ lines) — DO NOT REBUILD. Has kill-switch, rate limiting, cost logging.
- `web/templates/admin_costs.html` EXISTS — DO NOT REBUILD
- `/sitemap.xml` route EXISTS in routes_misc.py — you'll extend, not create
- Invite code system EXISTS — 3-tier (shared_link, invited, organic)
- `api_usage` table referenced in cost_tracking.py but NOT in release.py DDL — needs adding
- `manifest.json` EXISTS but no `<link rel="manifest">` in templates
- Landing/index templates are self-contained (inline Obsidian CSS vars, no base.html)

### DO NOT REBUILD
- `web/cost_tracking.py` — kill-switch, rate limiting, cost logging all exist
- `web/templates/admin_costs.html` — cost dashboard exists
- `/sitemap.xml` route — exists, just extend it
- Invite code system — exists, just generate a specific code

---

## PHASE 2: BUILD

### Task D-1: PostHog Integration (~90 min)
**Files:** `web/helpers.py` (posthog helper), `web/app.py` (after_request — `# === QS3-D: POSTHOG TRACKING ===`), `web/templates/landing.html` (JS snippet), `web/templates/index.html` (JS snippet)

**CRITICAL REQUIREMENTS (from c.ai review):**
- PostHog JS: load via `<script async>` — NEVER block rendering
- Server-side `after_request` hook: COMPLETE NO-OP if `POSTHOG_API_KEY` env var not set. Don't even import posthog. Zero overhead.
- Feature flags: create flag name `permit_prep_enabled`. Populate `g.posthog_flags` dict in before_request (or {} if no API key).

**In `web/helpers.py`, add:**
```python
import os

_POSTHOG_KEY = os.environ.get("POSTHOG_API_KEY")

def posthog_enabled() -> bool:
    return bool(_POSTHOG_KEY)

def posthog_track(event: str, properties: dict = None, user_id: str = None):
    """Track server-side event. No-op if POSTHOG_API_KEY not set."""
    if not _POSTHOG_KEY:
        return
    try:
        import posthog
        posthog.api_key = _POSTHOG_KEY
        posthog.host = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
        posthog.capture(
            distinct_id=user_id or "anonymous",
            event=event,
            properties=properties or {},
        )
    except Exception:
        pass  # Never let analytics break the app

def posthog_get_flags(user_id: str) -> dict:
    """Get feature flags for a user. Returns {} if PostHog not configured."""
    if not _POSTHOG_KEY:
        return {}
    try:
        import posthog
        posthog.api_key = _POSTHOG_KEY
        flags = posthog.get_all_flags(user_id)
        return flags or {}
    except Exception:
        return {}
```

**In `web/app.py`, add after_request hook:**
```python
# === QS3-D: POSTHOG TRACKING ===
@app.after_request
def _posthog_track_request(response):
    """Track page views and feature usage. No-op without POSTHOG_API_KEY."""
    from web.helpers import posthog_enabled, posthog_track
    if not posthog_enabled():
        return response
    if response.status_code >= 400:
        return response
    if request.path.startswith(("/static/", "/health", "/cron/", "/api/csp-report")):
        return response

    user_id = str(g.user["user_id"]) if g.user else "anonymous"
    properties = {
        "path": request.path,
        "method": request.method,
        "status": response.status_code,
    }

    # Specific event types
    if request.path == "/search":
        properties["query"] = request.args.get("q", "")
        posthog_track("search", properties, user_id)
    elif request.path.startswith("/analyze"):
        posthog_track("analyze", properties, user_id)
    elif request.path == "/lookup":
        posthog_track("lookup", properties, user_id)
    elif request.path == "/auth/send-link":
        posthog_track("signup_attempt", properties, user_id)
    else:
        posthog_track("page_view", properties, user_id)

    return response
# === END QS3-D ===
```

**In `web/app.py`, add before_request for feature flags:**
```python
# === QS3-D: POSTHOG FLAGS ===
@app.before_request
def _posthog_load_flags():
    """Load PostHog feature flags into g.posthog_flags."""
    from web.helpers import posthog_get_flags
    if g.user:
        g.posthog_flags = posthog_get_flags(str(g.user["user_id"]))
    else:
        g.posthog_flags = {}
# === END QS3-D ===
```

**In templates (landing.html, index.html), add PostHog JS:**
```html
<!-- PostHog analytics (async, non-blocking) -->
{% if posthog_key %}
<script async nonce="{{ csp_nonce }}">
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys onFeatureFlags".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
  posthog.init('{{ posthog_key }}', {api_host: '{{ posthog_host }}'});
</script>
{% endif %}
```

Pass `posthog_key` and `posthog_host` from the route via template context (or make them available via context processor).

**Add `posthog` to requirements:** `pip install posthog` and add to setup.cfg/pyproject.toml if it exists. If not, note it in CHECKCHAT.

### Task D-2: Charis Beta Invite (~20 min)
**Files:** `docs/charis-invite.md` (NEW)

1. Read `web/routes_auth.py` to understand how invite codes work
2. Generate invite code: the system uses env var `INVITE_CODES` (comma-separated). The code `friends-gridcare` needs to be added to that env var on Railway.
3. Write `docs/charis-invite.md`:

```markdown
# Beta Invite: Charis Kaskiris (GridCARE)

## Invite Code
`friends-gridcare`

## Setup
Add to Railway env var INVITE_CODES (comma-separated):
railway variable set INVITE_CODES="existing-codes,friends-gridcare"

## Message Draft
[Draft personal message emphasizing:]
- MCP architecture: 29 tools exposed over Streamable HTTP
- Agentic AI: multi-agent swarm builds, Black Box Protocol
- /methodology page: 3,000+ words of transparent estimation methodology
- Energy-relevant demo: search for addresses with solar permits
  (e.g., "75 Robin Hood Dr" has solar permit S20251030283)
- The depth: 18.4M rows, 576K entity relationship edges, nightly pipeline

## Test on Staging
1. Go to https://sfpermits-ai-staging-production.up.railway.app/auth/login
2. Enter new email, use code friends-gridcare
3. Verify account created with correct tier
```

4. Test the invite flow on staging if possible (may need INVITE_CODES env var set there too)

### Task D-3: PWA + Manifest Polish (~20 min)
**Files:** `web/templates/landing.html`, `web/templates/index.html`, `web/static/icon-192.png`, `web/static/icon-512.png`

Add to `<head>` of both landing.html and index.html:
```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#22D3EE">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/static/icon-192.png">
```

Generate branded icons using Python PIL (if available) or create simple SVGs:
- 192x192: dark background (#0B0F19) + "SF" text in cyan (#22D3EE)
- 512x512: same design, larger

### Task D-4: api_usage DDL + Sitemap Update (~15 min)
**Files:** `scripts/release.py` (append), `web/routes_misc.py` (extend sitemap)

**Add to release.py** (after existing DDL):
```sql
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    endpoint TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DOUBLE PRECISION,
    called_at TIMESTAMP DEFAULT NOW(),
    extra JSONB
);
CREATE INDEX IF NOT EXISTS idx_api_usage_user_date ON api_usage(user_id, called_at);
```

**Extend sitemap in routes_misc.py:**
- Verify /demo is NOT in sitemap (noindex page)
- Add /prep (if it makes sense for SEO — or exclude since it requires auth)
- Verify base URL points to production

---

## PHASE 3: TEST

Write `tests/test_qs3_d_analytics.py`:
- posthog_enabled() returns False when POSTHOG_API_KEY not set
- posthog_enabled() returns True when set
- posthog_track() is no-op without key (doesn't raise)
- posthog_track() calls posthog.capture when key set (mock posthog)
- posthog_get_flags() returns {} without key
- after_request hook doesn't modify response
- after_request hook skips /static/ and /health paths
- after_request hook tracks search events with query
- Feature flag g.posthog_flags populated for auth users
- Feature flag g.posthog_flags empty for anonymous
- landing.html contains posthog script tag when key set
- landing.html does NOT contain posthog script when key not set
- manifest link present in landing.html
- manifest link present in index.html
- theme-color meta tag present
- api_usage DDL in release.py
- sitemap excludes /demo
- docs/charis-invite.md exists and contains friends-gridcare

**Target: 20+ tests**

---

## PHASE 4: SCENARIOS

2 NEW scenarios:
1. "PostHog tracks page views for anonymous visitors without blocking page load"
2. "Feature flag permit_prep_enabled gates Permit Prep feature rollout"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs3-d-analytics-qa.md`:
```
1. [NEW] posthog import safe without API key (no crash) — PASS/FAIL
2. [NEW] landing.html source contains async PostHog script — PASS/FAIL
3. [NEW] landing.html source contains <link rel="manifest"> — PASS/FAIL
4. [NEW] index.html source contains <link rel="manifest"> — PASS/FAIL
5. [NEW] GET /static/manifest.json returns valid JSON — PASS/FAIL
6. [NEW] api_usage CREATE TABLE in release.py — PASS/FAIL
7. [NEW] /sitemap.xml does not contain /demo — PASS/FAIL
8. [NEW] docs/charis-invite.md contains friends-gridcare — PASS/FAIL
9. [NEW] Screenshot landing page at 1440px — no layout breakage from PostHog — PASS/FAIL
```

Save screenshots to `qa-results/screenshots/qs3-d/`
Write results to `qa-results/qs3-d-results.md`

---

## PHASE 5.5: VISUAL REVIEW

Score (1-5): landing page at 375px, 768px, 1440px (verify PostHog + manifest don't break rendering)
≥3.0 = PASS. ≤2.0 = ESCALATE.

---

## PHASE 6: CHECKCHAT

### 1-6: Standard

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2-3 hours | [actual] |
| New tests | 20+ | [count] |
| Total tests | ~3,450 | [pytest output] |
| Tasks completed | 4 | [N of 4] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task, duration] |
| QA checks | 9 | [pass/fail/skip] |
| Visual Review avg | — | [score or N/A] |
| Scenarios proposed | 2 | [count] |
```

### DeskRelay HANDOFF
- [ ] Landing page: does PostHog script break any visual element?
- [ ] Landing page: does manifest link tag cause any rendering change?
- [ ] PWA icons: do they look branded (not placeholder)?

---

## File Ownership (Session D ONLY)
**Own:**
- `web/helpers.py` (posthog helper functions)
- `web/app.py` (`# === QS3-D: POSTHOG TRACKING ===` and `# === QS3-D: POSTHOG FLAGS ===` sections ONLY)
- `web/templates/landing.html` (PostHog JS + manifest link + meta tags)
- `web/templates/index.html` (PostHog JS + manifest link + meta tags)
- `web/static/icon-192.png` (replace placeholder)
- `web/static/icon-512.png` (replace placeholder)
- `web/routes_misc.py` (sitemap extension)
- `scripts/release.py` (api_usage DDL — append AFTER Session A's prep DDL if present)
- `docs/charis-invite.md` (NEW)
- `tests/test_qs3_d_analytics.py` (NEW)

**Do NOT touch:**
- `web/permit_prep.py` (Session A)
- `web/routes_api.py` (Session A)
- `web/routes_property.py` (Session A)
- `web/routes_auth.py` (Session A)
- `web/brief.py` (Session A)
- `web/cost_tracking.py` (EXISTS — do not modify)
- `web/templates/admin_costs.html` (EXISTS — do not modify)
- `src/tools/permit_lookup.py` (Session B)
- `src/db.py` (Session B)
- `web/routes_cron.py` (Session B)
- `tests/e2e/` (Session C)
