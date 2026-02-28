<!-- LAUNCH: Paste into any CC terminal (fresh or reused from a previous sprint):
     "Read sprint-prompts/sprint-69-session1-design-landing.md and execute it" -->

# Sprint 69 — Session 1: Design System + Landing Rewrite

You are a build agent for Sprint 69 of sfpermits.ai, following the **Black Box Protocol**.

## SETUP — Session Bootstrap

Before doing anything else, ensure you are on a clean worktree branched from latest main:

1. **Navigate to the main repo root** (escape any old worktree):
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main** (includes all prior sprint merges):
   ```
   git checkout main && git pull origin main
   ```
3. **Create your worktree:**
   Use EnterWorktree with name `sprint-69-s1`

If EnterWorktree fails because a worktree with that name already exists, remove it first:
```
git worktree remove .claude/worktrees/sprint-69-s1 --force 2>/dev/null; true
```
Then retry EnterWorktree.

---

## PHASE 1: READ

Before writing any code, read these files to understand current state:
1. `CLAUDE.md` — project structure, deployment, rules
2. `STATUS.md` (via Chief if available, or local)
3. `web/templates/landing.html` — the current landing page you'll rewrite
4. `web/static/style.css` — current shared CSS (148 lines, utility classes)
5. `web/static/mobile.css` — current responsive overrides
6. `web/routes_api.py` — where you'll add /api/stats
7. `web/helpers.py` — shared decorators and utilities

**Architecture notes from audit:**
- Templates are SELF-CONTAINED (no base.html, no Jinja inheritance)
- Each template has inline `<style>` with duplicated `:root` vars
- Currently uses system fonts only (no Google Fonts)
- Current palette: `--bg: #0f1117`, `--surface: #1a1d27`, `--accent: #4f8ff7`

---

## PHASE 2: BUILD

### The "Obsidian Intelligence" Design System

This is the visual identity for sfpermits.ai. You create the canonical CSS file that all other Sprint 69 sessions reference. Embed these EXACT tokens:

```css
/* ── Obsidian Intelligence Design System ── */

/* Foundation */
--bg-deep:        #0B0F19;    /* Near-black with blue undertone */
--bg-surface:     #131825;    /* Card/panel surface */
--bg-elevated:    #1A2035;    /* Hover state, active elements */
--bg-glass:       rgba(255,255,255, 0.04);  /* Glassmorphism panels */

/* Text hierarchy */
--text-primary:   #E8ECF4;    /* Primary text — warm white */
--text-secondary: #8B95A8;    /* Labels, metadata */
--text-tertiary:  #5A6478;    /* Disabled, ultra-low-priority */

/* Signal colors */
--signal-green:   #34D399;    /* Approved, on track */
--signal-amber:   #FBBF24;    /* Attention, in progress */
--signal-red:     #F87171;    /* Violations, blocked */
--signal-blue:    #60A5FA;    /* Active, information, links */
--signal-cyan:    #22D3EE;    /* THE accent — intelligence, insight */

/* Gradients */
--gradient-hero:  linear-gradient(135deg, #0B0F19 0%, #0F172A 50%, #131D35 100%);
--gradient-accent: linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%);

/* Typography */
--font-display: 'JetBrains Mono', 'Fira Code', monospace;
--font-body: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Fluid type scale */
--text-xs:    clamp(0.7rem, 0.65rem + 0.25vw, 0.75rem);
--text-sm:    clamp(0.8rem, 0.75rem + 0.25vw, 0.875rem);
--text-base:  clamp(0.875rem, 0.85rem + 0.15vw, 1rem);
--text-lg:    clamp(1.1rem, 1rem + 0.5vw, 1.25rem);
--text-xl:    clamp(1.4rem, 1.2rem + 1vw, 1.75rem);
--text-2xl:   clamp(1.8rem, 1.5rem + 1.5vw, 2.5rem);
--text-3xl:   clamp(2.2rem, 1.8rem + 2vw, 3.5rem);

/* Spacing */
--space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
--space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;
--space-16: 64px;

--content-max: 1400px;
--card-radius: 12px;
--card-border: 1px solid rgba(255,255,255, 0.06);
--card-shadow: 0 4px 24px rgba(0,0,0, 0.3);
```

### Task 1: Create `web/static/design-system.css`

Build the full Obsidian design system CSS file:
1. All custom properties above in `:root`
2. Google Fonts import for JetBrains Mono and IBM Plex Sans (weights 400, 500, 600, 700)
3. Base element resets using the design system tokens
4. Component classes:
   - `.glass-card` — dark surface + subtle border + card shadow
   - `.status-dot` with `.status-success`, `.status-warning`, `.status-danger` — 8px colored circles with matching glow
   - `.data-bar` — gradient progress bars with 1px bright top edge
   - `.stat-block` — large number + label for statistics display
   - `.obsidian-btn`, `.obsidian-btn-primary`, `.obsidian-btn-outline` — button styles
   - `.obsidian-input` — dark input fields with cyan focus ring
5. Responsive density:
   - Phone (≤768px): single column, 48px min tap targets, no animations
   - Desktop (≥1024px): multi-column, max info density
6. Print styles: white background, dark text, no backgrounds
7. Keep backward compatibility: scope new styles under `.obsidian` body class so existing pages aren't affected

### Task 2: Rewrite `web/templates/landing.html`

Complete rewrite of the landing page using the Obsidian design system. The page must communicate depth and intelligence within 10 seconds.

**Structure (desktop):**
1. **Header** — logo left, sign in / get started right
2. **Hero (split layout):**
   - Left: "San Francisco Building Permit Intelligence" headline in JetBrains Mono, subtext, search bar with cyan focus glow, suggested addresses ("Try 1455 Market St")
   - Right: "Live Data Pulse" panel — live counts from /api/stats (permits tracked, routing records, entities mapped, last refresh), subtle number animation on load
3. **Homeowner funnel** — keep existing "Planning a project?" and "Got a violation?" cards, restyle with Obsidian tokens
4. **Capability cards** (3-column grid):
   - Permit Search & Tracking (1.1M permits)
   - Timeline Estimation (station-sum model)
   - Entity Network (1M entities, 576K edges)
   - AI Plan Analysis (Claude Vision EPR)
   - Routing Intelligence (3.9M addenda records)
   - Morning Briefs (daily severity scoring)
   Each card: icon, title, one-line description, data point, free/premium badge
5. **Stats bar** — 4 key numbers with cyan accent
6. **Credibility footer** — "Built on 22 SF government data sources" / "3,329 automated tests" / "Updated nightly"
7. **CTA section** — "Get more from your permit data" with feature list
8. **Footer** — system status link

**Structure (phone ≤768px):**
- Single column throughout
- Hero: headline + search bar + one stat line (no split layout)
- Capability cards: horizontal scroll strip
- Stats: 2x2 grid

**Non-behaviors:**
- Do NOT add JavaScript animations (CSS transitions only)
- Do NOT require JS for core content to render
- Do NOT add a chatbot widget
- Do NOT add fake testimonials

### Task 3: Add `/api/stats` endpoint in `web/routes_api.py`

Create a lightweight JSON endpoint that returns cached data counts:
```json
{
  "permits": 1137816,
  "routing_records": 3920710,
  "entities": 1000000,
  "inspections": 671000,
  "last_refresh": "2026-02-26T04:00:00Z",
  "today_changes": 42
}
```

Implementation:
- Query the actual database for real counts (permits, addenda, entities, inspections tables)
- Cache results for 1 hour (simple in-memory dict with timestamp)
- If DB unavailable, return hardcoded fallback numbers
- No auth required (public endpoint)
- Add rate limiting (60 requests/min)

### Task 4: Update `web/static/style.css` and `web/static/mobile.css`

- Add `@import url('/static/design-system.css');` at the top of style.css
- Ensure existing utility classes (.disclosure-panel, .tier-*, .tab-*) still work
- Add any mobile overrides needed for new landing page components

---

## PHASE 3: TEST

After each task:
```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write new tests in `tests/test_sprint69_s1.py`:
- design-system.css loads (200 response)
- Landing page renders for anonymous users (200, contains key elements)
- /api/stats returns JSON with expected keys
- /api/stats caching works (second call faster)
- Landing page has Obsidian CSS classes (.obsidian, .glass-card)
- Landing page includes Google Fonts link
- Mobile meta viewport tag present
- Stats numbers are present in landing page HTML

Target: 15+ new tests.

---

## PHASE 4: SCENARIOS

Append to `scenarios-pending-review.md`:

Propose 3-5 behavioral scenarios for the landing page and design system. Examples:
- "Anonymous visitor sees live data counts on landing page"
- "Landing page search bar submits to /search endpoint"
- "Design system CSS loads without breaking existing authenticated pages"

Use the scenario format from `scenario-design-guide.md`.

---

## PHASE 5: QA (termRelay)

Write `qa-drop/sprint69-s1-design-landing-qa.md` with numbered steps.

**Required Playwright checks:**
1. Start Flask test server
2. Navigate to `/` — verify 200 response
3. Screenshot landing page at 375px (mobile), 768px (tablet), 1440px (desktop)
4. Verify search bar exists and is focusable
5. Verify stats section shows numbers (not "undefined" or empty)
6. Verify capability cards render (count >= 4)
7. Verify Google Fonts stylesheet link is present in HTML
8. Verify `/api/stats` returns JSON with `permits` key
9. Verify no horizontal scroll at 375px viewport
10. Navigate to an authenticated page (e.g., /account) — verify it still works (design system doesn't break existing pages)

Save screenshots to `qa-results/screenshots/sprint69-s1/`
Write results to `qa-results/sprint69-s1-results.md`

Run the QA script. Fix any FAILs. Loop until all PASS or BLOCKED.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All FAILs fixed or BLOCKED
- pytest still passing after fixes
- No regressions on authenticated pages

### 2. DOCUMENT
- Update CHANGELOG.md with Sprint 69-S1 entry
- Update STATUS.md

### 3. CAPTURE
- Scenarios appended to `scenarios-pending-review.md`
- QA results in `qa-results/`

### 4. SHIP
- Commit all changes with meaningful message
- Report: files created, tests added, test count, QA results

### 5. DeskRelay HANDOFF
List these visual checks for Stage 2 (DeskCC):
- [ ] Landing page hero: does it feel authoritative? Do the numbers create an impression of scale?
- [ ] Color palette: does the Obsidian dark theme feel premium, not just "dark mode"?
- [ ] Typography: JetBrains Mono for headings — does it work or feel forced?
- [ ] Mobile landing: does the single-column layout feel intentional, not just squished?
- [ ] Stats section: do the numbers feel real and current?
- [ ] Overall: would a product person seeing this for the first time think "this is serious"?

### 6. BLOCKED ITEMS REPORT (if any)

---

## File Ownership (Session 1 ONLY)
- `web/static/design-system.css` (NEW)
- `web/templates/landing.html` (REWRITE)
- `web/routes_api.py` (/api/stats endpoint — APPEND ONLY)
- `web/static/style.css` (add import line)
- `web/static/mobile.css` (landing-specific responsive additions)
- `tests/test_sprint69_s1.py` (NEW)
- `qa-drop/sprint69-s1-design-landing-qa.md` (NEW)
- `qa-results/sprint69-s1-results.md` (NEW)
- `qa-results/screenshots/sprint69-s1/` (NEW)

Do NOT touch: `web/templates/search_results_public.html`, `web/templates/methodology.html`, `web/routes_search.py`, `web/routes_misc.py`, `web/routes_public.py`, `web/routes_cron.py`, `docs/`, `src/`, `data/`
