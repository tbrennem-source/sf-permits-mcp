<!-- LAUNCH: Paste into any CC terminal (fresh or reused from a previous sprint):
     "Read sprint-prompts/sprint-69-session3-content-pages.md and execute it" -->

# Sprint 69 — Session 3: Methodology + About the Data + Demo Mode

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
   Use EnterWorktree with name `sprint-69-s3`

If EnterWorktree fails because a worktree with that name already exists, remove it first:
```
git worktree remove .claude/worktrees/sprint-69-s3 --force 2>/dev/null; true
```
Then retry EnterWorktree.

---

## PHASE 1: READ

Before writing any code, read these files:
1. `CLAUDE.md` — project structure, key numbers, architecture
2. `web/routes_misc.py` — where you'll add routes
3. `web/helpers.py` — decorators, NEIGHBORHOODS list
4. `src/tools/estimate_timeline.py` — timeline estimation methodology (document this)
5. `src/tools/estimate_fees.py` — fee calculation methodology (document this)
6. `src/tools/predict_permits.py` — permit prediction logic (document this)
7. `src/entities.py` — entity resolution cascade (document this)
8. `src/tools/revision_risk.py` — revision risk methodology (document this)
9. `src/tools/analyze_plans.py` — AI plan analysis (document this)
10. `src/vision/epr_checks.py` — EPR compliance checks (document this)
11. `data/knowledge/SOURCES.md` — data source inventory
12. `data/knowledge/GAPS.md` — known gaps
13. `docs/TIMELINE_ESTIMATION.md` — existing timeline documentation

**Key finding from audit:** No methodology.html, about_data.html, or demo.html exist. No /methodology, /about-data, or /demo routes exist. These are all new pages.

---

## Obsidian Design Tokens (use these EXACTLY)

```css
:root {
  --bg-deep: #0B0F19; --bg-surface: #131825; --bg-elevated: #1A2035;
  --bg-glass: rgba(255,255,255, 0.04);
  --text-primary: #E8ECF4; --text-secondary: #8B95A8; --text-tertiary: #5A6478;
  --signal-green: #34D399; --signal-amber: #FBBF24; --signal-red: #F87171;
  --signal-blue: #60A5FA; --signal-cyan: #22D3EE;
  --gradient-accent: linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%);
  --font-display: 'JetBrains Mono', 'Fira Code', monospace;
  --font-body: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --card-radius: 12px;
  --card-border: 1px solid rgba(255,255,255, 0.06);
  --card-shadow: 0 4px 24px rgba(0,0,0, 0.3);
}
```

Include Google Fonts import for JetBrains Mono and IBM Plex Sans.

---

## PHASE 2: BUILD

### Task 1: Create `/methodology` page

Create `web/templates/methodology.html` — a deep-dive page that shows how sfpermits.ai calculates everything. This is the single strongest credibility signal for technical visitors. "We show you how we calculate everything."

**Obsidian design:** Dark, dense, research-paper feel. Monospace section headings. Cyan accent on key data points.

**Sections:**

1. **Hero:** "How It Works" — one paragraph: "sfpermits.ai provides building permit intelligence backed by 22 government data sources, transparent methodology, and confidence intervals on every estimate."

2. **Data Provenance Table** — For each major data source:
   | Source | Agency | Records | Last Refresh | What We Use It For |
   Read `data/knowledge/SOURCES.md` and the actual codebase to populate this accurately. Key sources:
   - Building Permits (DBI) — 1.1M
   - Building Inspections (DBI) — 671K
   - Plan Review Routing (DBI) — 3.9M addenda records
   - Complaints (DBI)
   - Violations (DBI)
   - Electrical/Plumbing/Boiler Permits
   - Fire Permits
   - Planning Records
   - Tax Roll / Property Data
   - Business Registrations
   Show SODA API endpoint identifiers for each.

3. **Entity Resolution** — Explain the 5-step cascade:
   - Step 1: Exact match on name
   - Step 2: Normalized match (lowercase, strip LLC/Inc/etc.)
   - Step 3: Token-based fuzzy match
   - Step 4: Business name cross-reference
   - Step 5: Address co-occurrence
   Read `src/entities.py` for the actual implementation and describe it accurately.
   Include: "1.8M contacts resolved into 1M entities"
   On desktop: CSS-only flowchart (boxes + arrows). On phone: numbered list.

4. **Timeline Estimation** — Explain the station-sum model:
   - What stations are, how permits route through them
   - How p50/p75/p90 percentiles are calculated from historical data
   - When neighborhood-specific data is available vs global fallback
   - Worked example: "For an alterations permit in the Mission..."
   Read `src/tools/estimate_timeline.py` and `docs/TIMELINE_ESTIMATION.md` for accuracy.

5. **Fee Estimation** — Explain DBI fee table methodology:
   - Table 1A-A base fees
   - How construction valuation drives the calculation
   - Statistical comparison against historical permits
   Read `src/tools/estimate_fees.py`.

6. **AI Plan Analysis** — Explain what Claude Vision checks:
   - EPR requirements by category (file size, dimensions, encryption, fonts, etc.)
   - Vision-based checks (title blocks, stamps, addresses)
   - Read `src/vision/epr_checks.py` for the actual check list
   - "This is augmented intelligence, not automated approval"

7. **Revision Risk** — How revision probability is estimated from permit data patterns.

8. **Limitations & Known Gaps** — Honest section:
   - Planning department data lags 2-4 weeks
   - Trade permit integration is newer (less historical depth)
   - Estimates are statistical, not guarantees
   - Entity resolution has ~85-90% accuracy (some false merges/splits)
   Read `data/knowledge/GAPS.md` for specifics.

**This page must be >2,500 words of real technical content.** Not filler — actual methodology descriptions derived from reading the source code.

### Task 2: Create `/about-data` page

Create `web/templates/about_data.html` — the full data inventory.

**Sections:**
1. **Overview** — "18.4M rows across 22 SODA datasets, refreshed nightly"
2. **Data Inventory Table** — every dataset with record count, agency, refresh frequency
3. **Nightly Pipeline** — what runs and when (read `web/routes_cron.py` for accuracy):
   - SODA permit change detection
   - Inspection updates
   - Addenda/routing refresh
   - Velocity computation
   - RAG chunk refresh
   - Morning brief generation
4. **Knowledge Base** — 4-tier system:
   - Tier 1: 47 structured JSON files (loaded at startup)
   - Tier 2: Raw text info sheets
   - Tier 3: Administrative bulletins
   - Tier 4: Full code corpus (Planning Code + BICC)
5. **Quality Assurance** — 3,329 automated tests, DQ checks, pipeline health monitoring
6. **What We Don't Cover** — honest gaps

### Task 3: Create `/demo` page

Create `web/templates/demo.html` — Tim's Zoom demo page. Pre-loaded with a known-rich address that shows all intelligence layers.

- **Route:** `/demo` (no auth required, but not indexed by robots)
- **Content:** Full property intelligence for 1455 Market St (or another address with rich data — check which address has routing progress, violations, multiple permits)
- Pre-query the data at render time (not HTMX — everything visible immediately)
- Show: permit history, routing progress bars, timeline estimate, entity connections, complaint/violation summary
- Desktop only — add `<meta name="robots" content="noindex">`
- Annotation callouts: small cyan labels explaining each section ("This shows real routing data from DBI's addenda system")
- `?density=max` parameter forces maximum info density at any viewport

### Task 4: Add routes in `web/routes_misc.py`

```python
@bp.route("/methodology")
def methodology():
    ...

@bp.route("/about-data")
def about_data():
    ...

@bp.route("/demo")
def demo():
    ...
```

For /methodology and /about-data: no auth required (public pages).
For /demo: no auth required, but add noindex meta tag.
For /demo: pre-query permit data for the demo address using existing tool functions.

---

## PHASE 3: TEST

Write `tests/test_sprint69_s3.py`:
- /methodology returns 200
- /methodology contains "Entity Resolution" section
- /methodology contains "Timeline Estimation" section
- /methodology contains data provenance table
- /methodology contains >2,000 words of content (measure text length)
- /about-data returns 200
- /about-data contains data inventory table
- /about-data mentions nightly pipeline
- /demo returns 200
- /demo has noindex meta tag
- /demo contains permit data (not empty)
- All three pages use Obsidian design tokens
- All three pages include Google Fonts import
- No horizontal scroll at 375px for methodology and about-data

Target: 15+ new tests.

---

## PHASE 4: SCENARIOS

Append 3-5 scenarios to `scenarios-pending-review.md`:
- "Technical visitor reads methodology page and understands how timeline estimates are calculated"
- "Visitor navigates from landing page to about-data and sees complete data inventory"
- "Tim shares /demo URL in Zoom and all intelligence layers are visible without clicking"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/sprint69-s3-content-pages-qa.md`.

**Required Playwright checks:**
1. Navigate to `/methodology` — 200 response
2. Screenshot at 375px and 1440px
3. Verify "Entity Resolution" heading exists
4. Verify "Timeline Estimation" heading exists
5. Verify data provenance table has >5 rows
6. Navigate to `/about-data` — 200 response
7. Screenshot at 375px and 1440px
8. Verify data inventory section exists
9. Navigate to `/demo` — 200 response
10. Screenshot at 1440px (desktop only)
11. Verify permit data renders (not "No results")
12. Verify annotation callouts visible
13. Verify noindex meta tag present on /demo

Save screenshots to `qa-results/screenshots/sprint69-s3/`
Write results to `qa-results/sprint69-s3-results.md`

---

## PHASE 6: CHECKCHAT

### DeskRelay HANDOFF
- [ ] Methodology: does a technical person reading this feel the depth? Is it real content, not filler?
- [ ] Entity resolution flowchart: does the CSS diagram work on desktop?
- [ ] About-data: does the data inventory feel comprehensive?
- [ ] Demo page: if Tim screen-shared this in a Zoom, would it impress?
- [ ] Typography: does JetBrains Mono for section headings work in a long-form content page?
- [ ] Mobile methodology: is it readable at 375px?

---

## File Ownership (Session 3 ONLY)
- `web/templates/methodology.html` (NEW)
- `web/templates/about_data.html` (NEW)
- `web/templates/demo.html` (NEW)
- `web/routes_misc.py` (add 3 routes — APPEND ONLY)
- `tests/test_sprint69_s3.py` (NEW)
- `qa-drop/sprint69-s3-content-pages-qa.md` (NEW)
- `qa-results/sprint69-s3-results.md` (NEW)

Do NOT touch: `web/templates/landing.html`, `web/templates/search_results_public.html`, `web/static/design-system.css`, `web/routes_api.py`, `web/routes_search.py`, `web/routes_public.py`, `docs/portfolio-*.md`, `src/`
