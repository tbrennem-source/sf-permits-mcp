<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/sprint-75-ux-beta.md and execute it" -->

# Sprint 75 — UX + Beta Launch

You are the orchestrator for Sprint 75. Spawn 4 parallel build agents, collect results, merge, test, push.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git tag pre-sprint-75
```

## Agent Launch

Spawn all 4 agents in parallel using Task tool:
```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree")
```

Each agent prompt MUST start with:
```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate

RULES:
- Read design-spec.md FIRST before touching any templates.
- MERGE RULE: Do NOT merge to main. Commit to worktree branch only.
- CONFLICT RULE: Do NOT run git checkout <branch> -- <file>. Report conflicts as BLOCKED.
- EARLY COMMIT RULE: First commit within 10 minutes.
- DESCOPE RULE: Mark BLOCKED with reason. Do NOT silently reduce scope.
- TEST FIXUP EXCEPTION: If your code changes cause tests in files you don't own to fail, you MAY fix those tests. Limit fixes to assertion updates. Document in CHANGELOG.
- TEMPLATE RENDERING WARNING: If you add context processors or before_request hooks that depend on `request`, verify email templates still work: pytest tests/ -k "email" -v. Must handle has_request_context() == False.
- APPEND FILES (dual-write):
  * scenarios-pending-review-sprint-75-N.md (per-agent)
  * scenarios-pending-review.md (shared, append only)
  * CHANGELOG-sprint-75-N.md (per-agent)
- TELEMETRY: Use "Scope changes" (not "descoped"), "Waiting on" (not "blocked").
- Test after each task: pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q 2>&1 | tail -5
```

---

### Agent 75-1: Dashboard + Nav Redesign (TOP PRIORITY)

**PHASE 1: READ**
- design-spec.md (the absolute design truth — follow it exactly)
- web/templates/landing.html (reference — THIS is what good looks like)
- web/static/design-system.css (all available tokens and component classes)
- web/templates/fragments/nav.html (current nav — 12 badges, no responsive)
- web/templates/index.html (current dashboard — cramped, no cards)
- web/templates/fragments/head_obsidian.html (the include fragment)

CRITICAL: Check how landing.html includes its header. It may NOT use fragments/nav.html — it may have an inline header. Your nav.html changes must work for BOTH index.html (which includes the fragment) and NOT break landing.html.

**PHASE 2: BUILD**

Task 75-1-1: Redesign nav.html
- Desktop (>768px): sticky header, backdrop-filter: blur(12px), logo left
- Max 5 visible nav badges: Search, Brief, Portfolio, Projects, More (dropdown)
- "More" dropdown: My Analyses, Permit Prep, Consultants, Bottlenecks
- Admin dropdown stays (gear icon)
- Account + Logout right-aligned
- Use design-system.css tokens: --bg-surface, --border, --text-secondary

Task 75-1-2: Mobile nav (<=768px)
- Hamburger button replaces badge row
- Slide-down panel with all nav items stacked vertically
- 48px min-height per touch target
- Close on tap outside or second hamburger tap

Task 75-1-3: Redesign index.html main content
- Search area in .glass-card with var(--space-6) padding
- Heading: var(--font-display), clamp() fluid size
- Search input: .obsidian-input class
- Go button: .obsidian-btn-primary

Task 75-1-4: Quick actions section
- Below search, in separate .glass-card
- Actions as .obsidian-btn-outline in flex row: "Analyze a project", "Look up a permit", "Upload plans", "Draft a reply"
- Mobile: 2-column grid, then stack at 375px

Task 75-1-5: Recent items section
- .glass-card containing recent search chips
- Each chip: small card with address + date, clickable
- Grid layout: 3-col desktop, 2-col tablet, 1-col mobile

Task 75-1-6: Placeholder sections
- "Watched Properties" — empty state .glass-card with muted text "Add properties to your watchlist to see them here" + CTA button
- "Quick Stats" — .stat-block row (permits watched: 0, changes this week: 0)

Task 75-1-7: All content wrapped in .obs-container (max-width centered)

Task 75-1-8: Verify nav works in BOTH landing.html and index.html — do NOT modify landing.html

**PHASE 3: TEST**
tests/test_sprint-75_1.py — 10+ tests: nav renders, hamburger element exists in HTML, obs-container present in index.html, glass-card present, quick actions present, landing page still returns 200, index page returns 200

**PHASE 4: SCENARIOS**
scenarios-pending-review-sprint-75-1.md — 2 scenarios:
1. "Authenticated dashboard displays search, quick actions, and recent items in Obsidian card layout"
2. "Navigation collapses to hamburger menu on mobile viewport"

**PHASE 5: QA**
Grep checks: verify obsidian markers in both templates.
Visual layout assertions (MANDATORY — add these to test_sprint-75_1.py):
- Assert .obs-container exists in index.html with max-width + margin:0 auto in CSS
- Assert visible nav badge count <= 6 (count .badge elements NOT inside dropdown menus)
- Assert hamburger/toggle element exists in nav HTML for mobile
- Assert @media (max-width: 768px) breakpoint exists in nav styles
- Assert no horizontal overflow: render page at 1440px and 375px, check body scrollWidth <= viewport width (Playwright page.evaluate if possible, or CSS inspection)
These are the visual safety net. Sprint 77-4 will also check these from E2E — if 75-1 doesn't fix it, 77-4 fails.

**PHASE 6: CHECKCHAT**
Commit: "feat: dashboard + nav Obsidian redesign (Sprint 75-1)"
CHANGELOG-sprint-75-1.md

**File Ownership:**
Own: web/templates/index.html, web/templates/fragments/nav.html, web/static/design-system.css (add nav classes only), tests/test_sprint-75_1.py (NEW)
DO NOT TOUCH: web/templates/landing.html

---

### Agent 75-2: Beta Approval Email + Onboarding

**PHASE 1: READ**
- design-spec.md
- web/routes_admin.py lines 848-877 (approve endpoint)
- web/auth.py (auth helpers, look for existing email functions)
- web/email_brief.py (SMTP pattern — SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASS)
- web/routes_misc.py lines 77-100 (/beta-request route)
- scripts/release.py (DDL pattern)

**PHASE 2: BUILD**

Task 75-2-1: send_beta_welcome_email(email, magic_link) in web/auth.py — SMTP pattern from email_brief.py
Task 75-2-2: web/templates/emails/beta_approved.html — inline CSS (no external sheets), brand colors, magic link button
Task 75-2-3: Wire into approve_beta_request() in routes_admin.py — generate magic link + send email on approval
Task 75-2-4: ALTER TABLE users ADD COLUMN onboarding_complete BOOLEAN DEFAULT FALSE in release.py (# === Sprint 75-2 ===)
Task 75-2-5: DuckDB DDL equivalent in src/db.py init_user_schema (ALTER TABLE or add column to CREATE)
Task 75-2-6: GET /welcome route in web/routes_misc.py — 3-step onboarding (search, report, watchlist). Obsidian design.
Task 75-2-7: web/templates/welcome.html — head_obsidian, body.obsidian, obs-container, glass-card per step, progress dots
Task 75-2-8: POST /onboarding/dismiss — sets onboarding_complete = True (check if route exists first)

**PHASE 3: TEST**
tests/test_sprint-75_2.py — 10+ tests: mock SMTP, email sent on approval, email contains link, welcome route 200, onboarding flag, dismiss works

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-75-2.md (2 scenarios), CHANGELOG-sprint-75-2.md
Commit: "feat: beta approval email + onboarding (Sprint 75-2)"

**File Ownership:**
Own: web/auth.py (add function), web/routes_admin.py (modify approve), web/routes_misc.py (add /welcome), scripts/release.py (append section), web/templates/emails/beta_approved.html (NEW), web/templates/welcome.html (NEW), tests/test_sprint-75_2.py (NEW)

---

### Agent 75-3: Template Migration Batch 1 (5 User Pages)

**PHASE 1: READ**
- design-spec.md (the absolute design truth)
- web/templates/fragments/head_obsidian.html
- web/static/design-system.css
- web/templates/landing.html (reference for good Obsidian implementation)
- web/templates/brief.html (another migrated reference)
- Each of the 5 target templates (determine if full page or HTMX fragment)

**PHASE 2: BUILD**

Migrate these 5 templates IN PRIORITY ORDER (do #1 first, #5 last — if time runs out, the highest-traffic pages are done):
1. web/templates/search_results.html (HIGHEST PRIORITY — users see this most)
2. web/templates/account.html (user settings page)
3. web/templates/analyze_plans_complete.html
4. web/templates/analyze_plans_results.html
5. web/templates/analyze_plans_polling.html

For EACH template:
- Check: is it a full page (has DOCTYPE) or a fragment (included by another page)?
- Full pages: add {% include "fragments/head_obsidian.html" %} in head, class="obsidian" on body
- Fragments: use Obsidian CSS classes only (parent provides the head include)
- Wrap main content in .obs-container if not already
- Wrap content sections in .glass-card
- Replace raw buttons with .obsidian-btn classes
- Replace raw inputs with .obsidian-input classes
- PRESERVE all Jinja logic, form actions, HTMX attributes — only change styling

**PHASE 3: TEST**
tests/test_sprint-75_3.py — 10+ tests: each route returns 200, response contains obsidian markers

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-75-3.md (1 scenario), CHANGELOG-sprint-75-3.md
Commit: "feat: Obsidian migration — 5 user templates (Sprint 75-3)"

**File Ownership:**
Own: 5 templates listed above, tests/test_sprint-75_3.py (NEW)

---

### Agent 75-4: Demo Enhancement + PWA Polish

**PHASE 1: READ**
- design-spec.md
- web/routes_misc.py lines 294-511 (_get_demo_data, /demo route)
- web/templates/demo.html
- src/severity.py (score_permit function)
- web/static/manifest.json

**PHASE 2: BUILD**

Task 75-4-1: Enhance _get_demo_data() — query parcel_summary for demo parcel (block 3507, lot 004). Use real data if available, keep hardcoded fallbacks.
Task 75-4-2: Integrate severity: import score_permit from src.severity, score active permits, add tier to context
Task 75-4-3: Severity badges in demo.html — colored pills (--signal-red CRITICAL, --signal-amber HIGH, --signal-green GREEN)
Task 75-4-4: Cache TTL 15 min on _get_demo_data (verify _demo_cache has computed_at, add TTL check)
Task 75-4-5: manifest.json — add "purpose": "any maskable" to icon entries, verify all required PWA fields present
Task 75-4-6: Add /demo to sitemap static_pages in routes_misc.py (if not already there)

**PHASE 3: TEST**
tests/test_sprint-75_4.py — 10+ tests: demo route 200, severity in context, manifest valid JSON with maskable, sitemap includes /demo

**PHASE 4-6: SCENARIOS, QA, CHECKCHAT**
scenarios-pending-review-sprint-75-4.md (1 scenario), CHANGELOG-sprint-75-4.md
Commit: "feat: demo severity + PWA polish (Sprint 75-4)"

**File Ownership:**
Own: web/routes_misc.py (modify _get_demo_data), web/templates/demo.html, web/static/manifest.json, tests/test_sprint-75_4.py (NEW)

---

## Post-Agent Merge (Orchestrator)

1. Collect results from all 4 agents
2. Merge branches (Fast Merge Protocol). If nav.html conflict: take Agent 75-1's version.
3. Run: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/test_web.py --ignore=tests/e2e -x -q`
4. `git pull origin main` (get QS6 changes), then `git push origin main`
5. Concatenate changelogs + scenarios
6. Report summary table

## Push Order
Sprint 75 pushes SECOND. Must pull QS6 first.
