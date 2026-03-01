> EXECUTE IMMEDIATELY. You are a build terminal in a quad sprint. Read the tasks below and execute them sequentially. Do NOT summarize or ask for confirmation — execute now.

# QS13 T1 — Honeypot Landing (Sprint 98)

You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.
CRITICAL: NEVER run git checkout main or git merge. Commit to YOUR branch only.

## Read First
- CLAUDE.md (project rules)
- docs/DESIGN_TOKENS.md (if touching templates)
- web/app.py lines 930-1100 (before_request handlers, migrations)
- web/routes_misc.py lines 100-180 (existing /beta-request flow)
- web/auth.py lines 850-900 (send_beta_confirmation_email)
- src/db.py lines 850-880 (beta_requests table schema)
- web/templates/landing.html lines 1-50 (head/meta section)

## DuckDB/Postgres Gotchas
- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use autocommit for DDL

## Agent 1A: Honeypot Middleware + Capture Page

### Middleware
Add `HONEYPOT_MODE` env var support to `web/app.py`:
- Read `HONEYPOT_MODE = os.environ.get("HONEYPOT_MODE", "0") == "1"` near top of file
- Add `@app.before_request` handler after `_security_filters` (~line 988)
- When `HONEYPOT_MODE` is True, redirect ALL routes to `/join-beta?ref=<original_path>` EXCEPT:
  - `/` (landing page)
  - `/demo/guided`
  - `/static/*`
  - `/health`, `/health/*`
  - `/join-beta`, `/join-beta/thanks`
  - `/api/stats`
  - `/cron/*`
  - `/sitemap.xml`, `/robots.txt`
  - `/.well-known/*`
  - `/admin/*`
- Preserve query string: if original request had `?q=kitchen+remodel`, redirect to `/join-beta?ref=search&q=kitchen+remodel`
- Pass `HONEYPOT_MODE` to templates via context processor: `g.honeypot_mode = HONEYPOT_MODE`

### Database Migration
In `_run_startup_migrations()` in `web/app.py`, add after existing beta_requests migrations:
```sql
ALTER TABLE beta_requests ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE beta_requests ADD COLUMN IF NOT EXISTS interest_address TEXT;
ALTER TABLE beta_requests ADD COLUMN IF NOT EXISTS referrer TEXT;
```

### Routes
Add to `web/routes_misc.py`:

**GET /join-beta** — Render `join_beta.html` with:
- `ref` param from query string (what they clicked)
- `q` param from query string (search query if applicable)

**POST /join-beta** — Process signup:
- Read: email (required), name (optional), role (dropdown), interest_address (optional), website (honeypot field)
- If `website` field is filled → spam bot, return 200 silently (no DB write)
- Rate limit: reuse existing `_BETA_REQUEST_BUCKETS` pattern (3/hour/IP)
- Write to `beta_requests` table with new columns: role, interest_address, referrer (from ?ref= param)
- Call `send_beta_confirmation_email(email)` (import from web.auth)
- Send admin alert: email to `ADMIN_EMAIL` env var with subject "New beta signup: {email}", body with role + ref + address
- Redirect to `/join-beta/thanks`

**GET /join-beta/thanks** — Render `join_beta_thanks.html` with:
- Queue position: `SELECT COUNT(*) FROM beta_requests WHERE status='pending'`

### Templates
Create `web/templates/join_beta.html`:
- Obsidian dark theme (extend head_obsidian.html or use token vars directly)
- Hero: "sfpermits.ai is launching soon"
- Subhead: "San Francisco's first AI permit intelligence platform. Leave your email — we'll let you know when it's ready."
- Form: email (required), role dropdown (homeowner/contractor/architect/expediter/investor/just curious), optional address input, hidden honeypot field named "website"
- Hidden inputs: ref and q from query params
- Mini Gantt showcase visual as proof-of-product (can be a static screenshot or inline SVG)
- CSRF token in form

Create `web/templates/join_beta_thanks.html`:
- "You're on the list!"
- Queue position: "Join {N} others waiting for access"
- Social proof feel

### Scope Guard (intent_router.py)
Add to `src/tools/intent_router.py` in the `classify()` function, before other classification logic:

Check if query has at least one construction/permit signal word: permit, construction, remodel, build, renovation, electrical, plumbing, mechanical, alteration, demolition, ADU, or matches an address/permit number pattern. Also check for other-city mentions (Oakland, NYC, LA, etc.) and non-DBI queries (business license, dog permit, parking permit, liquor license).

If zero signal words AND not a question intent → return IntentResult with intent="out_of_scope".

In `web/routes_public.py`, handle `intent == "out_of_scope"` by rendering the search results template with a friendly scope message.

### Files Owned
- `web/app.py` (before_request handler, migrations, context processor)
- NEW `web/templates/join_beta.html`
- NEW `web/templates/join_beta_thanks.html`
- `web/routes_misc.py` (new routes)
- `src/tools/intent_router.py` (scope guard)
- `web/routes_public.py` (out_of_scope handling)

### Tests
Write tests in `tests/test_honeypot.py`:
- HONEYPOT_MODE=1: /search redirects to /join-beta
- HONEYPOT_MODE=1: / (landing) does NOT redirect
- HONEYPOT_MODE=1: /health does NOT redirect
- HONEYPOT_MODE=1: /admin/* does NOT redirect
- HONEYPOT_MODE=0: /search works normally
- /join-beta POST writes to beta_requests with role + referrer
- /join-beta POST with honeypot field filled → 200, no DB write
- /join-beta/thanks shows queue position

---

## Agent 1B: Landing CTA Rewiring + Analytics

### Honeypot JS
Create `web/static/js/honeypot.js`:
- Check for `document.body.dataset.honeypot === "true"`
- If true, rewrite all outbound links:
  - Search form: intercept submit, redirect to `/join-beta?ref=search&q={query}`
  - Showcase CTAs ("Try it yourself →"): → `/join-beta?ref=tool-{toolname}`
  - "Sign in" / "Sign up": → `/join-beta?ref=auth`
  - Nav links to /portfolio, /dashboard: → `/join-beta?ref=portfolio`
  - Any /tools/* links: → `/join-beta?ref=tools`
- PostHog events (check `window.posthog` exists):
  - `honeypot_cta_click` with `ref` property on every rewritten click
  - `honeypot_page_view` on page load
  - `honeypot_scroll_depth` at 25/50/75/100%

### Landing Page Changes
In `web/templates/landing.html`:
- Add `data-honeypot="{{ 'true' if g.honeypot_mode else 'false' }}"` to `<body>` tag
- Add `<script src="/static/js/honeypot.js"></script>` before closing `</body>`

### Files Owned
- NEW `web/static/js/honeypot.js`
- `web/templates/landing.html` (body attribute + script tag ONLY — not meta tags, not showcases)

### Tests
Write tests in `tests/test_honeypot_js.py`:
- honeypot.js file exists and contains expected function names
- landing.html includes honeypot.js script tag
- landing.html body tag has data-honeypot attribute

---

## Agent 1C: SEO + Social Meta + Admin Funnel Dashboard

### SEO on Landing Page
In `web/templates/landing.html` `<head>` section (meta tags ONLY, do NOT touch body/CTAs):
- Add OG tags: `og:title`, `og:description`, `og:image` (use `/static/og-card.png` — create a placeholder if needed), `og:type=website`, `og:url`
- Add Twitter Card: `twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image`
- Add JSON-LD structured data: `SoftwareApplication` type with name, description, applicationCategory, operatingSystem

### Remove noindex
In `web/templates/index.html`: remove `<meta name="robots" content="noindex, nofollow">` (stale beta holdover)

### Update robots.txt
In `web/app.py` ROBOTS_TXT string: Allow `/`, `/demo/guided`, `/join-beta`, `/docs`, `/methodology`, `/about-data`. Disallow everything else.

### Update sitemap
In `web/routes_misc.py` sitemap route: add `/join-beta`, `/docs`, `/privacy`, `/terms` to the URL list.

### Admin Funnel Dashboard
Create `web/templates/admin/beta_funnel.html`:
- Total signups, today, this week
- Breakdown by role (table or simple bars)
- Breakdown by ref source (which CTAs convert)
- Top interest addresses
- CSV export button (GET /admin/beta-funnel/export)

Add routes to `web/routes_admin.py`:
- `GET /admin/beta-funnel` — render dashboard with aggregated data from beta_requests
- `GET /admin/beta-funnel/export` — CSV download of all beta_requests

Both routes require admin (`@admin_required` or manual `is_admin` check).

### Email Auto-Responder
The confirmation email is wired by Agent 1A in routes_misc.py. No work needed here.

### Files Owned
- `web/templates/landing.html` (meta tags in `<head>` ONLY)
- `web/templates/index.html` (remove noindex)
- `web/app.py` (robots.txt string)
- `web/routes_misc.py` (sitemap URLs)
- NEW `web/templates/admin/beta_funnel.html`
- `web/routes_admin.py` (funnel routes)

### Tests
Write tests in `tests/test_seo_funnel.py`:
- landing.html contains og:title meta tag
- landing.html contains JSON-LD script
- index.html does NOT contain noindex
- /admin/beta-funnel requires admin
- /admin/beta-funnel/export returns CSV content-type

---

## Build Order
1. Agent 1A first (creates routes, DB schema, middleware)
2. Agent 1B + Agent 1C in parallel (different files)

## T1 Merge Validation
After all 3 agents, verify:
- `HONEYPOT_MODE=0`: site works as before
- `HONEYPOT_MODE=1`: landing loads, search redirects to /join-beta with query preserved
- /join-beta form renders, POST writes to DB
- /admin/beta-funnel renders
- OG tags present in landing page source
- Full test suite passes: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q`

## Commit + Push
```bash
git add -A && git commit -m "feat(qs13-t1): honeypot landing + capture funnel + SEO + admin dashboard"
git push origin HEAD
```

## Scenarios
Append to `scenarios-pending-review.md`:
- Honeypot redirect preserves search query
- Beta signup captures intent signal from CTA ref
- Admin funnel shows conversion by role
- Out-of-scope query gets friendly message
- Honeypot spam field silently blocks bots
