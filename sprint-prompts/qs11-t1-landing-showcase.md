# QS11 T1: Landing Page Intelligence Showcase + MCP Demo

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn agents using the Agent tool (subagent_type="general-purpose", isolation="worktree"). Agent 1A runs first (sequential). Then spawn Agents 1B + 1C in parallel. After both complete, spawn Agent 1D. Do NOT summarize or ask for confirmation — execute now. After all agents complete, run the Post-Agent merge ceremony, then CHECKQUAD.

**Sprint:** QS11 — Intelligence-Forward Beta
**Terminal:** T1 — Landing Page Intelligence Showcase + MCP Demo
**Agents:** 4 (1A sequential → 1B + 1C parallel → 1D sequential)
**Theme:** Transform landing page from "nice dark theme" to "holy shit, look what this can do"

---

## Terminal Overview

| Agent | Focus | Model | Files Owned |
|---|---|---|---|
| 1A | Data Prep Script | Sonnet | scripts/generate_showcase_data.py, web/static/data/showcase_data.json, tests/test_showcase_data.py |
| 1B | 6 Showcase Components | Sonnet | web/templates/components/showcase_*.html (6), web/static/js/showcase-*.js (2), tests/test_showcase_components.py |
| 1C | MCP Demo Animation | **Opus** | web/templates/components/mcp_demo.html, web/static/js/mcp-demo.js, web/static/css/mcp-demo.css, tests/test_mcp_demo.py |
| 1D | Landing Integration | Sonnet | web/templates/landing.html, web/routes_public.py, tests/test_landing_showcases.py |

**Build order:** 1A → 1B + 1C (parallel) → 1D

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules (ALL agents must follow)

1. **Worktree**: You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run `git checkout main`. Do NOT run `git merge`. Your CWD is your isolated copy.
2. **No descoping**: If something is hard, attempt it. Do not skip tasks. Flag actual blockers as BLOCKED with reason.
3. **Early commit**: Commit after each major milestone — first commit within 10 minutes. Use `git add <specific-files>` not `git add -A`.
4. **CRITICAL: NEVER merge to main.** Commit to your worktree branch. T1 orchestrator handles all merges.
5. **File ownership**: Only touch files in your ownership matrix. If you need a file owned by another agent, stop and note it.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Write to `scenarios-t1-sprint90.md` (create if missing). Do NOT touch `scenarios-pending-review.md`.
8. **Changelog file**: Write to `CHANGELOG-t1-sprint90.md` (create if missing).
9. **Design system**: Read `docs/DESIGN_TOKENS.md` before touching any template or CSS. Use ONLY token components and CSS custom properties. Log new components to `docs/DESIGN_COMPONENT_LOG.md`.

---

## DuckDB / Postgres Gotchas

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use `conn.autocommit = True` for DDL
- `duckdb.connect()` in tests must use a temp path, not the real DB file

---

## Agent 1A Prompt — Data Prep Script

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Create showcase data generation script

Generate pre-computed JSON fixture data for 6 intelligence showcases on the landing page.
The output file (web/static/data/showcase_data.json) is loaded at build time — zero API calls on page load.

### Context

sfpermits.ai has 30+ MCP tools that analyze SF building permits. The landing page will show
6 pre-rendered intelligence showcases using curated real permits. Each showcase demonstrates
a different tool's capabilities.

### The 6 Showcases

1. **station_timeline** — Permit 202509155257. $13M parking-to-loading-zone conversion.
   8 review stations, 3 BLDG comment rounds, 166 days elapsed. Show station-by-station journey
   with status (approved/comments/stuck), reviewer names, dates.

2. **stuck_permit** — Permit 202412237330. Laundromat-to-childcare conversion, $200K.
   4 simultaneous blocks (BLDG, MECH, SFFD, CP-ZOC). 223 days at Planning.
   Show severity badges, block details, intervention playbook with reviewer names + phone numbers.

3. **what_if** — Kitchen remodel $45K (OTC, 1 agency, ~2 weeks) vs Kitchen+Bath+Wall $185K
   (in-house, 7 agencies, 70 days p50). Show dramatic comparison table with green/red indicators.

4. **revision_risk** — Restaurant alteration in the Mission. 24.6% revision rate from 21,596
   similar permits. Top 5 correction triggers. +51 days timeline impact. Budget recommendation.

5. **entity_network** — 1 Market Street. 63 permits. Top contractors: Arb Inc (12,674 permits),
   Pribuss Engineering (7,309 permits). Show node-edge relationships.

6. **cost_of_delay** — Restaurant with $15K/month carry cost ($500/day).
   p25=$17,500, p50=$35,000, p75=$56,500, p90=$87,000.
   Probability-weighted expected cost: $41,375. SFFD-HQ bottleneck alert (+86% slower).

### Implementation

Create `scripts/generate_showcase_data.py`:
1. Read existing tool source code to understand data structures:
   - src/tools/predict_next_stations.py (station timeline data)
   - src/tools/stuck_permit.py (stuck analysis format)
   - src/tools/what_if_simulator.py (comparison format)
   - src/tools/revision_risk.py (risk assessment format)
   - src/tools/cost_of_delay.py (delay calculation format)
   - src/tools/permit_lookup.py (entity data format)

2. Generate HARDCODED fixture data (not live API calls) that matches each tool's output format.
   Use the real permit numbers and data points listed above. The data is curated for demo impact.

3. Output: JSON file with this structure:
   ```json
   {
     "station_timeline": { "permit": "202509155257", "stations": [...], "elapsed_days": 166, ... },
     "stuck_permit": { "permit": "202412237330", "blocks": [...], "playbook": [...], ... },
     "what_if": { "scenario_a": {...}, "scenario_b": {...}, "comparison": [...] },
     "revision_risk": { "rate": 0.246, "triggers": [...], "timeline_impact": 51, ... },
     "entity_network": { "address": "1 Market St", "permits": 63, "entities": [...], ... },
     "cost_of_delay": { "monthly_cost": 15000, "percentiles": {...}, "expected": 41375, ... }
   }
   ```

4. Write to `web/static/data/showcase_data.json`

5. Script should be runnable: `python scripts/generate_showcase_data.py`
   Also importable: `from scripts.generate_showcase_data import generate_all`

### FILES YOU OWN
- CREATE: scripts/generate_showcase_data.py
- CREATE: web/static/data/showcase_data.json
- CREATE: tests/test_showcase_data.py

### FILES YOU MUST NOT TOUCH
- web/templates/*, web/routes_*.py, web/app.py
- src/tools/* (read only — don't modify tool code)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_showcase_data.py)
- Test that generate_all() returns a dict with all 6 keys
- Test each showcase has required fields (permit number, data arrays, etc.)
- Test the JSON output is valid and parseable
- Test the script creates the output file at the correct path (use tmp_path)
- At least 10 tests. All must pass.

### Steps
1. Read src/tools/predict_next_stations.py, stuck_permit.py, what_if_simulator.py, revision_risk.py, cost_of_delay.py, permit_lookup.py — understand output formats
2. Create scripts/generate_showcase_data.py with hardcoded fixture data
3. Run script: source .venv/bin/activate && python scripts/generate_showcase_data.py
4. Create tests/test_showcase_data.py
5. Run tests: pytest tests/test_showcase_data.py -v
6. Run full suite: pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
7. Commit: git add scripts/generate_showcase_data.py web/static/data/showcase_data.json tests/test_showcase_data.py
8. Write 2-3 scenarios to scenarios-t1-sprint90.md
9. Write changelog entry to CHANGELOG-t1-sprint90.md
```

---

## Agent 1B Prompt — 6 Showcase Components

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Build 6 intelligence showcase components for the landing page

Create 6 self-contained Jinja2 partial templates, each displaying a pre-rendered intelligence
showcase. These are included in landing.html by Agent 1D. Data comes from showcase_data.json
(created by Agent 1A) passed as template context.

### IMPORTANT: Read docs/DESIGN_TOKENS.md FIRST

All components must use Obsidian design tokens:
- Colors: CSS custom properties only (--obsidian, --accent, --text-primary, etc.)
- Fonts: --mono for data/numbers, --sans for prose/labels
- Components: glass-card, obs-table, ghost-cta, status-dot
- NO ad-hoc hex colors, NO custom font-families

### Component 1: Station Timeline Gantt (showcase_gantt.html)

Horizontal bar chart showing a permit's journey through 8 review stations.
- Each station is a horizontal bar. Width proportional to time spent.
- Color-coded: green (--dot-green) = approved, amber (--dot-amber) = comments, red (--dot-red) = stuck
- Timeline axis at bottom (months)
- "You are here" indicator on the current station (CPB — final processing)
- Station labels on left: PERMIT-CTR, CP-ZOC, BLDG, PAD-STR, MECH, MECH-E, SFFD-HQ, DPW-BSM, SFPUC, CPB
- Reviewer names in small text on each bar
- Uses CSS grid/flexbox, NOT canvas/SVG (keep it simple, renderable server-side)
- Receives data as: {{ showcase.station_timeline | tojson }}
- Associated JS in web/static/js/showcase-gantt.js — entrance animation (bars grow from left on scroll)

### Component 2: Stuck Permit Diagnosis (showcase_stuck.html)

Card showing a permit stuck at multiple stations simultaneously.
- Red severity badge: "CRITICAL — 4 SIMULTANEOUS BLOCKS"
- 4 block cards, each with:
  - Station name + status icon (red circle for comments, gray for waiting)
  - Reviewer name (e.g., "Jeff Ibarra")
  - Round number ("2nd round of comments")
  - Date issued
- Intervention playbook section:
  1. "Address BLDG + MECH + SFFD comments NOW — respond to all agencies in one resubmission"
  2. "Call Planning (628-652-7600) about CP-ZOC. Ask for Wesley Wong."
  3. "Upload corrected sheets with revision clouds (EPR-025)"
- Timeline impact: "Each comment-response cycle adds 6-8 weeks"
- Use glass-card for the outer container, status-dot for severity

### Component 3: What-If Comparison (showcase_whatif.html)

Two-column comparison table with dramatic visual contrast.
- Left column: "KITCHEN ONLY" — $45K, OTC, 1 agency, ~2 weeks, $1,200 fees
- Right column: "KITCHEN + BATH + WALL" — $185K, In-House, 7 agencies, 70 days, $6,487 fees
- Rows: Cost, Review Path, Agencies, Timeline (p50), Timeline (p75), DBI Fees, Plans Signed By, ADA Required, Revision Risk
- Green indicator on favorable values, red on unfavorable
- Use obs-table token class for the table
- Strategy callout at bottom: "Consider splitting into two permits..."

### Component 4: Revision Risk Meter (showcase_risk.html)

Risk gauge showing probability of plan corrections.
- Bar gauge at 24.6% with HIGH badge (red)
- "Based on 21,596 similar permits"
- Top 5 correction triggers as numbered list:
  1. Incomplete grease interceptor sizing
  2. Missing Type I hood fire suppression details
  3. DPH health permit requirements not addressed
  4. Inadequate ventilation calculations
  5. ADA path-of-travel missing or insufficient
- Timeline impact: "+51 days average"
- Budget recommendation: "Plan for $321,250 (not $250K)"

### Component 5: Entity Network Mini-Graph (showcase_entity.html)

Simplified node graph showing professionals connected to a property.
- Central node: "1 Market St" (63 permits)
- 3-4 connected nodes: top contractors/architects with permit counts
- Node size proportional to permit count
- Edge labels: "contractor", "architect"
- Pure SVG or CSS — keep it simple, no D3 dependency on landing page
- "Click to explore full network →" ghost CTA
- Associated JS in web/static/js/showcase-entity.js — entrance animation (nodes fade in + connect)

### Component 6: Cost of Delay Calculator (showcase_delay.html)

Pre-filled calculator showing financial impact of permit delays.
- Input label: "Monthly carrying cost" — pre-filled "$15,000"
- Output table:
  - Best case (p25): 35 days = $17,500
  - Typical (p50): 70 days = $35,000
  - Conservative (p75): 113 days = $56,500
  - Worst case (p90): 174 days = $87,000
- Probability-weighted expected cost: $41,375 (highlighted)
- Warning badge: "SFFD-HQ is running 86% slower than baseline"
- "Budget for p75, not p50"

### Each Component MUST:
- Be a self-contained Jinja partial ({% macro %} or plain include)
- Accept data from template context (not JS fetch)
- Work at both desktop (card in 2×3 grid) and mobile (full-width stacked)
- Have a "Try it yourself →" ghost CTA linking to the /tools/ page with demo permit pre-filled
  - Gantt → /tools/station-predictor?permit=202509155257
  - Stuck → /tools/stuck-permit?permit=202412237330
  - What-If → /tools/what-if?demo=kitchen-vs-full
  - Risk → /tools/revision-risk?demo=restaurant-mission
  - Entity → /tools/entity-network?address=1+Market+St
  - Delay → /tools/cost-of-delay?demo=restaurant-15k
- Use WCAG AA contrast ratios
- Have data-track="showcase-view" attribute for analytics (IntersectionObserver)

### FILES YOU OWN
- CREATE: web/templates/components/showcase_gantt.html
- CREATE: web/templates/components/showcase_stuck.html
- CREATE: web/templates/components/showcase_whatif.html
- CREATE: web/templates/components/showcase_risk.html
- CREATE: web/templates/components/showcase_entity.html
- CREATE: web/templates/components/showcase_delay.html
- CREATE: web/static/js/showcase-gantt.js
- CREATE: web/static/js/showcase-entity.js
- CREATE: tests/test_showcase_components.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html (Agent 1D owns this)
- web/routes_*.py
- web/static/js/mcp-demo.js (Agent 1C owns this)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_showcase_components.py)
Tests do NOT need Playwright. Use Jinja2 environment to render each component with sample data:
- Test each of the 6 components renders without error
- Test each component contains expected text (permit numbers, station names, etc.)
- Test ghost CTAs have correct href with demo permit pre-filled
- Test data-track attributes are present
- At least 12 tests total.

### Steps
1. Read docs/DESIGN_TOKENS.md — understand available tokens and components
2. Read web/static/data/showcase_data.json (created by Agent 1A) — understand data structure
3. Create all 6 component templates
4. Create showcase-gantt.js and showcase-entity.js (entrance animations)
5. Create tests/test_showcase_components.py
6. Run: source .venv/bin/activate && pytest tests/test_showcase_components.py -v
7. Run full suite: pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
8. Commit all files
9. Write 3-4 scenarios to scenarios-t1-sprint90.md
10. Write changelog entry to CHANGELOG-t1-sprint90.md
```

---

## Agent 1C Prompt — MCP Demo Animation (OPUS)

> **MODEL OVERRIDE: Launch this agent with model="opus"**
> Interaction complexity (typing animation, tool badges, table rendering, auto-advance, scroll trigger, mobile collapse) warrants the stronger model.

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Build the animated MCP demo section for the landing page

Create an animated chat transcript showing Claude using sfpermits.ai tools. This auto-plays
when scrolled into view and cycles through 3 conversations. This is the highest-value,
highest-visibility section on the landing page — disproportionate QA attention required.

### Demo Rotation (LOCKED ORDER — do not change)

1. **Demo 2: What-If Scope Comparison** — leads because the comparison table communicates instantly
2. **Demo 1: Stuck Permit Diagnosis** — follows with depth (intervention playbook)
3. **Demo 6: Cost of Delay** — closes with emotional hook ($500/day)

### Transcript Source

Read docs/mcp-demo-transcripts.md for the full conversation text. Use the EXACT text
from Demo 2, Demo 1, and Demo 6 (in that order). These are built from real tool outputs.

### Visual Treatment

- Dark terminal-style chat background (use --obsidian-900 or similar dark token)
- User messages: right-aligned, blue bubbles (--accent)
- Claude messages: left-aligned, light bubbles (--glass-bg) with sfpermits.ai wordmark
- Tool call badges: small pills with lightning icon pulsing
  - e.g., "⚡ diagnose_stuck_permit" in a rounded badge
  - Badges pulse once then settle (CSS animation)
- Section title: "What your AI sees" in --text-secondary

### Animation Behavior

- **Scroll trigger**: IntersectionObserver fires when section enters viewport (threshold 0.3)
- **User message**: Types in over 0.5s (not character by character — fade-in + slide-up)
- **Tool call badges**: Appear sequentially with 0.3s stagger, pulse animation
- **Claude response**: Types line by line at 40ms per character for text
  - Tables render as pre-built HTML blocks (instant, not typed)
  - Risk meters / gauges render as pre-built HTML (instant)
- **Pause**: 4s at end of each demo
- **Transition**: Fade out current (0.5s), fade in next demo
- **Manual control**: Click left/right arrows or dots to switch demos
- **Auto-advance**: Cycles 2→1→6→2→1→6... indefinitely

### MOBILE TREATMENT (CRITICAL — 375px breakpoint)

Tables inside chat bubbles on 375px viewports BREAK. You MUST handle this:

1. **Tables collapse to stacked key-value pairs on mobile.** The What-If comparison table
   (Demo 2, the LEAD demo) must NOT render as a 2-column table on mobile. Instead, render
   as stacked cards: "Kitchen Only" card with its values, then "Kitchen + Bath + Wall" card.

2. **Cap Claude response visible height with expand.** Long Claude responses (Demo 1 has
   the intervention playbook) get `max-height: 300px; overflow: hidden` on mobile with a
   "See full analysis ↓" expand button that removes the cap.

3. **Tool call badges wrap to 2 lines max.** If 3+ badges, wrap — don't overflow.

4. **Test at 375px before committing.** You don't have Playwright, but verify CSS handles
   the breakpoint correctly. Use `@media (max-width: 480px)` for mobile treatment.

### CTA Below Demo

- "Connect your AI" button → placeholder href="#connect" (future: Anthropic directory)
- "How it works" 3-step explainer:
  1. Connect — "Add sfpermits.ai to your AI assistant"
  2. Ask — "Ask about any SF property or permit"
  3. Get Intelligence — "Receive data-backed analysis with specific actions"

### FILES YOU OWN
- CREATE: web/templates/components/mcp_demo.html
- CREATE: web/static/js/mcp-demo.js
- CREATE: web/static/css/mcp-demo.css
- READ ONLY: docs/mcp-demo-transcripts.md (use this text, do NOT modify the file)
- CREATE: tests/test_mcp_demo.py

### FILES YOU MUST NOT TOUCH
- web/templates/landing.html (Agent 1D owns this)
- web/templates/components/showcase_*.html (Agent 1B owns these)
- web/routes_*.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_mcp_demo.py)
Tests do NOT need Playwright:
- Test mcp_demo.html renders without error in Jinja2
- Test all 3 demos are present in the template (check for unique text from each)
- Test mobile CSS includes max-width media query
- Test CTA section renders with correct href
- Test demo rotation order matches spec (What-If first, then Stuck, then Delay)
- At least 8 tests total.

### Steps
1. Read docs/DESIGN_TOKENS.md — available tokens
2. Read docs/mcp-demo-transcripts.md — demo transcript content (use EXACT text)
3. Create web/static/css/mcp-demo.css (styling + animations + mobile breakpoints)
4. Create web/templates/components/mcp_demo.html (template structure, all 3 demos inline)
5. Create web/static/js/mcp-demo.js (scroll trigger, typing animation, auto-advance, manual controls)
6. Create tests/test_mcp_demo.py
7. Run tests: source .venv/bin/activate && pytest tests/test_mcp_demo.py -v
8. Run full suite: pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
9. Commit all files
10. Write 3-4 scenarios to scenarios-t1-sprint90.md
11. Write changelog entry to CHANGELOG-t1-sprint90.md
```

---

## Agent 1D Prompt — Landing Page Integration

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Wire showcase components + MCP demo into landing.html

Integrate the 6 showcase components (from Agent 1B) and MCP demo (from Agent 1C) into
the existing landing page. Also add server-side showcase data loading.

### IMPORTANT: Read the current landing.html first

The current landing page (web/templates/landing.html, ~1,266 lines) has:
- Hero: "Permit intelligence, distilled" + unified search bar
- Below-search: sub row (anchor links), watched row, context row (examples)
- Stats section: 4 counting animations
- Capabilities section: 4 items (#cap-permits, #cap-timeline, #cap-stuck, #cap-hire)
- Demo section: static widget showing 1455 Market St
- Footer: methodology, about-data, login links
- JavaScript: dropdown logic, user state management, scroll reveal, counting animation

### New Page Structure

Restructure landing.html to this layout:
1. **Hero** (KEEP) — "Permit intelligence, distilled" + search + below-search
2. **NEW: Intelligence Showcase** — 6 cards in 2×3 grid (desktop) or stacked (mobile)
3. **NEW: MCP Demo** — "What your AI sees" animated chat section
4. **Stats** (KEEP) — 4 counting stats, wire to real numbers if possible
5. **Footer** (KEEP) — methodology, about-data, login

REMOVE the old "Capabilities" section (#cap-permits etc.) — the showcases replace it.
REMOVE the old static "Demo" section — the MCP demo replaces it.

### Showcase Section Layout

```html
<section class="showcase-section" id="intelligence">
  <h2>See what permit intelligence looks like</h2>
  <div class="showcase-grid">
    {% include "components/showcase_gantt.html" %}
    {% include "components/showcase_stuck.html" %}
    {% include "components/showcase_whatif.html" %}
    {% include "components/showcase_risk.html" %}
    {% include "components/showcase_entity.html" %}
    {% include "components/showcase_delay.html" %}
  </div>
</section>
```

CSS for .showcase-grid:
- Desktop: 2×3 grid (grid-template-columns: repeat(2, 1fr))
- Tablet (≤768px): single column
- Mobile (≤480px): single column, full-width cards
- Gap: var(--space-lg) or similar token

### MCP Demo Section

```html
<section class="mcp-section" id="mcp-demo">
  {% include "components/mcp_demo.html" %}
</section>
```

### Server-Side: Load Showcase Data

Modify `web/routes_public.py` — the `index()` function currently passes NO data to landing.html.
Add showcase data loading:

```python
@bp.route("/")
def index():
    if not g.user:
        # Load showcase data for landing page
        import json, os
        showcase_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "static", "data", "showcase_data.json"
        )
        showcase = {}
        try:
            with open(showcase_path) as f:
                showcase = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # graceful fallback — showcases won't render
        return render_template("landing.html", showcase=showcase)
    # ... rest of authenticated index unchanged
```

### ANALYTICS TRACKING (from review — MANDATORY)

Add data-track attributes for PostHog event capture:
1. `data-track="showcase-view"` on each showcase card container (IntersectionObserver tracks which cards scrolled into view)
2. `data-track="showcase-click"` with `data-showcase="gantt|stuck|whatif|risk|entity|delay"` on each CTA
3. `data-track="mcp-demo-view"` with `data-demo-id="1|2|6"` on the MCP section
4. `data-track="mcp-demo-cta"` on the "Connect your AI" button

PostHog is already initialized on the landing page (lines ~1258-1261). The `data-track` attributes
will be picked up by PostHog's autocapture. No additional PostHog config needed.

### Preserve Existing Features

- Keep ALL existing JavaScript for search dropdown, user state management
- Keep the admin tools (admin-feedback.js, admin-tour.js script tags)
- Keep ?admin=1 cookie detection and beta badge
- Keep the search form action="/search" method="GET"
- Keep the "Sign in" link

### FILES YOU OWN
- MODIFY: web/templates/landing.html
- MODIFY: web/routes_public.py (add showcase data loading to index())
- CREATE: tests/test_landing_showcases.py

### FILES YOU MUST NOT TOUCH
- web/templates/components/* (Agents 1B and 1C own these)
- web/static/js/mcp-demo.js, showcase-*.js (Agents 1B and 1C own these)
- web/static/css/mcp-demo.css (Agent 1C owns this)
- web/routes_search.py, web/routes_auth.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_landing_showcases.py)
- Test landing route returns 200 for unauthenticated user
- Test landing response contains "showcase" section
- Test showcase data is loaded from JSON file
- Test landing page still renders when showcase_data.json is missing (graceful fallback)
- Test old capabilities section is removed
- Test analytics data-track attributes are present
- At least 8 tests total.

### Steps
1. Read web/templates/landing.html — understand current structure (1,266 lines)
2. Read web/routes_public.py — understand index() route
3. Read docs/DESIGN_TOKENS.md — available tokens
4. Modify web/routes_public.py to load showcase_data.json and pass to template
5. Modify web/templates/landing.html:
   a. Add showcase section (includes 6 components)
   b. Add MCP demo section
   c. Remove old Capabilities and Demo sections
   d. Add CSS for showcase grid layout
   e. Add data-track analytics attributes
6. Create tests/test_landing_showcases.py
7. Run tests: source .venv/bin/activate && pytest tests/test_landing_showcases.py -v
8. Run full suite: pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
9. Run design lint: python scripts/design_lint.py --files web/templates/landing.html
10. Commit all files
11. Write 2-3 scenarios to scenarios-t1-sprint90.md
12. Write changelog entry to CHANGELOG-t1-sprint90.md
```

---

## Post-Agent Merge Ceremony

After ALL 4 agents complete:

```bash
# Step 0: ESCAPE CWD
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

# Step 1: Pull latest main
git checkout main && git pull origin main

# Step 2: Merge agents in dependency order
# 1A first (data prep — no conflicts)
git merge <1A-branch> --no-ff -m "feat(showcase): data prep script — 6 pre-computed intelligence fixtures"

# 1B and 1C next (parallel agents, no file overlap)
git merge <1B-branch> --no-ff -m "feat(showcase): 6 intelligence showcase components"
git merge <1C-branch> --no-ff -m "feat(mcp-demo): animated chat demo — 3 demo rotation"

# 1D last (integration — depends on 1B and 1C)
git merge <1D-branch> --no-ff -m "feat(landing): wire showcases + MCP demo into landing page"

# Step 3: Quick test
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x

# Step 4: Design lint
python scripts/design_lint.py --changed --quiet

# Step 5: Push
git push origin main
```

---

## CHECKQUAD

### Step 0: ESCAPE CWD
`cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

### Step 1: MERGE
See Post-Agent Merge Ceremony above.

### Step 2: ARTIFACT
Write `qa-drop/qs11-t1-session.md` with:
- Agent results table (4 agents, PASS/FAIL each)
- Files created/modified
- Test counts
- Merge conflicts (if any)
- Visual QA checklist: landing page with showcases, MCP demo animation, 375px mobile

### Step 3: CAPTURE
- Concatenate per-agent scenario files → `scenarios-t1-sprint90.md`
- Concatenate per-agent changelog files → `CHANGELOG-t1-sprint90.md`

### Step 4: HYGIENE CHECK
```bash
python scripts/test_hygiene.py --changed --quiet 2>/dev/null || echo "No test_hygiene.py"
```

### Step 5: SIGNAL DONE
```
═══════════════════════════════════════════════════
  CHECKQUAD T1 COMPLETE — Landing Showcase + MCP Demo
  Sprint 90 · 4 agents · X/4 PASS
  Pushed: <commit hash>
  Session: qa-drop/qs11-t1-session.md
═══════════════════════════════════════════════════
```

Do NOT run `git worktree remove` or `git worktree prune`. T0 handles cleanup.
