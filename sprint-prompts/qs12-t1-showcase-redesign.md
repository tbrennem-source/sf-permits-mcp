# QS12 T1: Landing Page Showcase Visual Redesign

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn Agent 1A first (sequential). After 1A completes, spawn 1B + 1C in parallel. After both complete, spawn 1D. Do NOT summarize or ask for confirmation — execute now.

**Sprint:** QS12 — Demo-Ready: Visual Intelligence
**Terminal:** T1 — Landing Showcase Redesign
**Agents:** 4 (1A → 1B + 1C parallel → 1D)
**Theme:** Make every card as good as the Gantt. The visual IS the intelligence.

---

## The Intelligence Layer Narrative (ALL AGENTS READ THIS)

Each showcase card represents a distinct analytical capability. The visitor should feel DEPTH.

| Showcase | Intelligence Layer | The visual IS... |
|---|---|---|
| Station Timeline Gantt | Routing intelligence | The Gantt IS the routing analysis |
| Stuck Permit | Diagnostic intelligence | The pipeline IS the diagnosis |
| What-If | Simulation intelligence | The comparison IS the simulation |
| Revision Risk | Predictive intelligence | The gauge IS the prediction |
| Entity Network | Network intelligence | The graph IS the intelligence |
| Cost of Delay | Financial intelligence | The number IS the intelligence |

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules

1. **Worktree**: You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run `git checkout main`. Do NOT run `git merge`.
2. **No descoping**: Attempt everything. Flag blockers.
3. **Early commit**: Within 10 minutes.
4. **CRITICAL: NEVER merge to main.** T1 orchestrator handles merges.
5. **File ownership**: Only YOUR files.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Write to `scenarios-t1-sprint94.md`.
8. **Changelog file**: Write to `CHANGELOG-t1-sprint94.md`.
9. **Design system**: Read `docs/DESIGN_TOKENS.md` FIRST.

---

## DuckDB / Postgres Gotchas

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`

---

## Agent 1A Prompt — Layout Restructure + Gantt Full-Width

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Restructure landing page — Gantt full-width, kill stats bar

Read web/templates/landing.html first (~1,300+ lines). Understand the current structure.

### Changes

1. **Gantt full-width.** Move the Station Timeline showcase to FULL WIDTH directly below
   the hero/search section. It should NOT share a row with any other card. This is the
   hero moment — the first intelligence showcase visitors see.

   Add a small label above: "Routing Intelligence" in --text-tertiary, --mono, small caps.

   CSS: the gantt card needs `max-width: none` or `width: 100%` within the page margins.
   Remove it from the showcase-grid and place it as a standalone section.

2. **Kill stats bar.** Find the stats section (shows "1,137,816 SF building permits",
   "22 City data sources", "Nightly", "Free During beta"). Remove the entire section.
   Replace with a single line at the page bottom (above footer):
   "Updated nightly from 22 city data sources · Free during beta"
   Style: --mono, --text-tertiary, text-align: center, margin: var(--space-lg) 0.

3. **Remaining 5 showcases in grid.** Below the full-width Gantt, place the other 5
   showcase cards (stuck, whatif, risk, entity, delay) in a responsive grid:
   - Desktop: 3 columns (grid-template-columns: repeat(3, 1fr))
   - Tablet (≤768px): 2 columns
   - Phone (≤480px): 1 column
   - Gap: var(--space-lg)

4. **Each card structure:** Intelligence layer label (small, --text-tertiary) at top,
   visual component (60%+ of card height), one-line insight, ghost CTA.

5. **MCP demo section stays below the showcase grid.** Don't move it.

### Gantt Mobile Treatment
- Phone (≤480px): horizontal scroll with overflow-x: auto and subtle shadow on right edge
- Station labels already short (BLDG, CP-ZOC) — keep
- Timeline axis: month labels only, hide day ticks if present
- Min-height: 300px
- Swipe to scroll (native behavior with overflow-x: auto)

### FILES YOU OWN
- MODIFY: web/templates/landing.html (showcase section restructure + stats removal)
- CREATE: tests/test_landing_showcase_layout.py

### FILES YOU MUST NOT TOUCH
- showcase_*.html components (Agents 1B/1C)
- mcp-demo.* (Agent 1D)
- web/routes_*.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests
- Test landing page returns 200
- Test stats section is removed (no "1,137,816" in response)
- Test credibility line is present ("Updated nightly")
- Test showcase-grid has the 5 non-Gantt cards
- Test Gantt section exists outside the grid
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read web/templates/landing.html in full
3. Restructure: move Gantt to full-width, kill stats, arrange grid
4. Write tests
5. Run tests + full suite + design lint
6. Commit, scenarios, changelog
```

---

## Agent 1B Prompt — Stuck Permit Card Redesign

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Redesign the Stuck Permit showcase card from text dump to visual diagnostic

The current showcase_stuck.html shows the intervention playbook as dense text. Too much
for a landing page teaser. Redesign it to be visual-first.

### Read First
- web/templates/components/showcase_stuck.html (current state)
- web/static/data/showcase_data.json (the stuck_permit data structure)
- docs/DESIGN_TOKENS.md

### New Design

Intelligence label: "Diagnostic Intelligence" (small, --text-tertiary, mono, top of card)

**Headline (mono, large):** "432 days · 4 agencies blocked"

**Severity indicator:** Pulsing red dot (CSS animation) + "CRITICAL" text badge.
CSS for pulse:
```css
@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.severity-pulse { animation: pulse-red 2s ease-in-out infinite; }
```

**Visual pipeline:** 4 station blocks in a HORIZONTAL ROW. Each block:
- Station abbreviation (BLDG, MECH, SFFD, CP-ZOC) in mono
- Red X overlay icon if blocked, green check if cleared
- Small text: "2nd round" or "223 days"
- Use flexbox, equal width per block
- This IS the card — the visual pipeline IS the diagnosis

**One-line intervention:** "Step 1: Call Planning (628-652-7600) about CP-ZOC"
Only the FIRST action. Not all 3.

**CTA:** "See full playbook →" ghost-cta linking to /tools/stuck-permit?permit=202412237330

**Card height:** Same as other showcase cards. Do NOT grow to fit the full playbook.

### FILES YOU OWN
- MODIFY: web/templates/components/showcase_stuck.html
- CREATE: web/static/css/showcase-stuck.css (if needed, or inline in component)
- CREATE: tests/test_showcase_stuck_redesign.py

### FILES YOU MUST NOT TOUCH
- landing.html (Agent 1A)
- Other showcase_*.html (Agent 1C)
- mcp-demo.* (Agent 1D)

### Tests
- Test component renders without error
- Test "432 days" or similar headline text present
- Test "CRITICAL" badge present
- Test 4 station names visible (BLDG, MECH, SFFD, CP-ZOC)
- Test pipeline visual elements present (station blocks)
- Test CTA links to /tools/stuck-permit with permit param
- Test NO raw JSON or dict output in rendered HTML
- At least 8 tests.

### Steps
1. Read current showcase_stuck.html
2. Read showcase_data.json stuck_permit section
3. Redesign the component
4. Write tests
5. Run tests + full suite
6. Commit, scenarios, changelog
```

---

## Agent 1C Prompt — 4 Remaining Showcase Card Redesigns

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Redesign 4 showcase cards to be visual-first

Each card must communicate in 2 seconds WITHOUT reading. Visual > text.

### Read First
- web/templates/components/showcase_whatif.html
- web/templates/components/showcase_risk.html
- web/templates/components/showcase_entity.html
- web/templates/components/showcase_delay.html
- web/static/data/showcase_data.json
- docs/DESIGN_TOKENS.md

### What-If Comparison (Simulation Intelligence)

- Label: "Simulation Intelligence" (--text-tertiary)
- Two columns, bold contrast:
  - Left: green tint. "Kitchen remodel" title. Big "2 weeks" (mono). "$1,200 · OTC" below.
  - Right: amber tint. "Kitchen + Bath + Wall" title. Big "5 months" (mono). "$6,487 · In-house" below.
- Horizontal bars below each showing relative timeline (left bar short/green, right bar long/amber)
- The comparison IS the simulation — the visual contrast tells the story instantly
- CTA: "Compare your project →" → /tools/what-if?demo=kitchen-vs-full

### Revision Risk (Predictive Intelligence)

- Label: "Predictive Intelligence"
- SVG circular arc gauge filled to 24.6%. Color: amber (use --dot-amber or --signal-amber).
  Large "24.6%" centered inside the arc (mono, ~2rem).
  ```html
  <svg viewBox="0 0 120 120" width="120" height="120">
    <circle cx="60" cy="60" r="50" fill="none" stroke="var(--glass-border)" stroke-width="8"/>
    <circle cx="60" cy="60" r="50" fill="none" stroke="var(--dot-amber)" stroke-width="8"
            stroke-dasharray="314" stroke-dashoffset="237" transform="rotate(-90 60 60)"/>
    <text x="60" y="65" text-anchor="middle" fill="var(--text-primary)"
          font-family="var(--mono)" font-size="20">24.6%</text>
  </svg>
  ```
- Below: "Restaurant alterations in the Mission"
- "5 common triggers" as ghost link
- CTA: "Check your risk →" → /tools/revision-risk?demo=restaurant-mission

### Entity Network (Network Intelligence)

- Label: "Network Intelligence"
- Mini SVG or D3 node graph. 5-7 nodes. Central node "1 Market St" larger.
  Connected nodes: top 3-4 contractors with size proportional to permit count.
  Edges in teal (--accent). Gentle float animation (CSS transform on nodes).
  The graph IS the intelligence.
- Below: "63 permits · 12,674 connected projects"
- CTA: "Explore network →" → /tools/entity-network?address=1+MARKET

### Cost of Delay (Financial Intelligence)

- Label: "Financial Intelligence"
- Big hero number: "$500" in large mono (~3rem). "/day" in --text-secondary beside it.
  The number IS the intelligence — bureaucratic time translated to money.
- Below: "Expected total: $41,375" (mono, smaller)
- Subtle: "Based on $15K/mo carrying cost" (--text-tertiary)
- CTA: "Calculate your cost →" → /tools/cost-of-delay?demo=restaurant-15k

### FILES YOU OWN
- MODIFY: web/templates/components/showcase_whatif.html
- MODIFY: web/templates/components/showcase_risk.html
- MODIFY: web/templates/components/showcase_entity.html
- MODIFY: web/templates/components/showcase_delay.html
- MODIFY: web/static/js/showcase-entity.js (if needed for D3/animation)
- CREATE: tests/test_showcase_cards_redesign.py

### FILES YOU MUST NOT TOUCH
- landing.html (Agent 1A)
- showcase_stuck.html, showcase_gantt.html (Agent 1B / unchanged)
- mcp-demo.* (Agent 1D)

### Tests
- Test each of 4 components renders without error
- Test What-If has two comparison columns with big numbers
- Test Risk has SVG gauge element
- Test Entity has node graph elements
- Test Delay has "$500" hero number
- Test each has intelligence layer label
- Test each has ghost CTA with correct link
- At least 12 tests.

### Steps
1. Read all 4 current component templates
2. Read showcase_data.json for data structure
3. Redesign all 4
4. Write tests
5. Run tests + full suite + design lint
6. Commit, scenarios, changelog
```

---

## Agent 1D Prompt — MCP Demo Fix + Integration QA

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before touching any template.

## YOUR TASK: Fix MCP demo section + verify all showcase integration

Two jobs: (1) fix the MCP demo if broken, (2) integration QA on all showcases.

### Job 1: MCP Demo Fix

Read web/templates/components/mcp_demo.html, web/static/mcp-demo.js, web/static/mcp-demo.css.

The MCP demo section ("What your AI sees") may show a tool badge then empty content.
Diagnose:
1. Does mcp-demo.js load transcript data? From where?
2. Does the IntersectionObserver scroll trigger fire?
3. Does the typing animation render text?
4. Any JS errors in the template?

Fix approach (IN ORDER — do not skip to step 3 without trying 1 and 2):
1. If data loading issue → fix path or inline the data
2. If JS animation bug → fix the rendering
3. If fundamentally broken after 20 min → REPLACE with static mockup:
   - 2-3 pre-rendered chat bubbles (user + Claude) with tool call badges
   - Use the What-If demo transcript from docs/mcp-demo-transcripts.md
   - No animation needed — the content is compelling
   - "Connect your AI →" CTA below
   - A WORKING SIMPLE VERSION BEATS A BROKEN FANCY ONE

### Job 2: Integration QA

After 1A, 1B, and 1C have run (you run last):
- Start the dev server: `source .venv/bin/activate && python -m web.app &`
- Verify Gantt renders at full width (1A's change)
- Verify all 6 showcase cards render with data from showcase_data.json
- Verify all 6 "Try it yourself →" CTAs link to correct /tools/ page with query param
- Test at 375px: Gantt scroll, cards stack, no overflow
- Kill dev server when done

### FILES YOU OWN
- MODIFY: web/templates/components/mcp_demo.html
- MODIFY: web/static/mcp-demo.js
- MODIFY: web/static/mcp-demo.css
- CREATE: tests/test_mcp_demo_fix.py

### FILES YOU MUST NOT TOUCH
- landing.html (Agent 1A owns structure)
- showcase_*.html (Agents 1B/1C)
- web/routes_*.py

### Tests
- Test mcp_demo.html renders without error
- Test demo content present (check for transcript text from at least one demo)
- Test CTA present with href
- Test no empty content containers
- At least 6 tests.

### Steps
1. Read mcp_demo.html, mcp-demo.js, mcp-demo.css
2. Read docs/mcp-demo-transcripts.md
3. Diagnose and fix MCP demo
4. Start dev server, run integration checks
5. Write tests
6. Run tests + full suite
7. Commit, scenarios, changelog
```

---

## Post-Agent Merge Ceremony

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge in order: 1A → 1B → 1C → 1D
git merge <1A-branch> --no-ff -m "feat(landing): Gantt full-width, kill stats bar, showcase grid"
git merge <1B-branch> --no-ff -m "feat(showcase): stuck permit card visual redesign"
git merge <1C-branch> --no-ff -m "feat(showcase): 4 card visual redesigns (whatif/risk/entity/delay)"
git merge <1D-branch> --no-ff -m "feat(mcp-demo): fix demo section + integration QA"

source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x
python scripts/design_lint.py --changed --quiet
git push origin main
```

---

## CHECKQUAD

### Step 0: ESCAPE CWD
`cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

### Steps 1-5: Standard CHECKQUAD
Write `qa-drop/qs12-t1-session.md`. Concatenate per-agent files. Signal done.

Do NOT clean worktrees — T0 handles that.
