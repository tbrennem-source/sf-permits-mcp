<!-- LAUNCH: Paste into any CC terminal (fresh or reused from a previous sprint):
     "Read sprint-prompts/sprint-69-session2-search-intel.md and execute it" -->

# Sprint 69 — Session 2: Search Intelligence + Anonymous Demo Path

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
   Use EnterWorktree with name `sprint-69-s2`

If EnterWorktree fails because a worktree with that name already exists, remove it first:
```
git worktree remove .claude/worktrees/sprint-69-s2 --force 2>/dev/null; true
```
Then retry EnterWorktree.

---

## PHASE 1: READ

Before writing any code, read these files:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/templates/search_results_public.html` — current search results page you'll enhance
3. `web/templates/lookup_results.html` — current /lookup result fragment
4. `web/routes_search.py` — /lookup and /ask endpoints (you'll enhance /lookup)
5. `web/routes_public.py` — /search route that renders search_results_public.html
6. `web/helpers.py` — shared utilities (_resolve_block_lot, run_async, etc.)
7. `src/tools/permit_lookup.py` — the permit_lookup tool (already works for anonymous users)
8. `src/tools/estimate_timeline.py` — timeline estimation tool
9. `src/tools/search_complaints.py` — complaints search
10. `src/tools/search_violations.py` — violations search

**Key finding from audit:** `/lookup` already works without authentication. Anonymous users get full permit_lookup results. The intelligence layer (routing progress, timeline estimates, entity connections) exists in backend tools but is NOT surfaced in search results.

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

Include Google Fonts import for JetBrains Mono and IBM Plex Sans in any template you create or rewrite.

---

## PHASE 2: BUILD

### Task 1: Enhance `/lookup` to return intelligence data

Modify `web/routes_search.py` `/lookup` endpoint to include additional intelligence data for address-based lookups:

1. After the existing permit_lookup call, add parallel queries for:
   - **Routing progress**: For each active permit, query addenda for routing steps completed vs total
   - **Complaint/violation counts**: `search_complaints` and `search_violations` by block/lot
   - **Top entities**: Extract architect, contractor, owner names from permit contacts (already in permit_lookup results)
2. Bundle this into the template context as `intel_data`:
   ```python
   intel_data = {
       "routing": [...],  # List of {permit_number, stations_cleared, stations_total, current_station}
       "complaints_count": N,
       "violations_count": N,
       "top_entities": [...],  # List of {name, role, permit_count}
       "has_intelligence": True
   }
   ```
3. Use `run_async()` for any async tool calls
4. Wrap in try/except — if intelligence queries fail, set `has_intelligence: False` and return results without it. Never let intelligence failures break search.
5. If the lookup takes >2 seconds for intelligence, skip it and set `intel_data["timeout"] = True`

### Task 2: Create `web/templates/fragments/intel_preview.html`

HTMX fragment that renders the intelligence panel. Loaded via `hx-get` after initial search results render (progressive enhancement — results appear fast, intelligence loads after).

**Content (what anonymous users see for FREE):**
1. **Routing Progress** — For each active permit: colored progress bar (green/amber/red) showing review station progress. Station names visible. "3 of 7 stations cleared"
2. **Timeline Estimate** — "Estimated 4-7 months remaining" (range from estimate_timeline tool). Link text "How we calculated this" → /methodology (gated behind login for full breakdown)
3. **Entity Connections** — Top 3 entities on the property's permits: "Architect: Smith & Associates (47 SF permits)". "See full network" → login gate
4. **Complaint/Violation Summary** — "3 open complaints, 1 active violation" with status dots. Full descriptions → login gate
5. **CTA** — "Sign up free for full severity scoring, morning briefs, and watch alerts"

**What is NOT shown (gated behind auth):**
- Station velocity context (how fast each station is moving)
- Station-by-station timeline breakdown
- Full entity network graph
- Complaint/violation descriptions and resolution history
- Severity scores
- Morning brief content

**Desktop layout:** Two-column — permit list left, intelligence panel right (sticky)
**Phone layout:** Intelligence panel collapses to expandable section below permit list

### Task 3: Rewrite `web/templates/search_results_public.html`

Full Obsidian redesign of the search results page:

1. Apply Obsidian design tokens (inline `<style>` block — this is the current architecture)
2. Google Fonts import (JetBrains Mono + IBM Plex Sans)
3. **Desktop (≥1024px):** Two-column layout
   - Left column (60%): search bar + permit result cards
   - Right column (40%): sticky intelligence panel (loaded via HTMX from intel_preview.html)
4. **Phone (≤768px):** Single column
   - Search bar
   - Permit cards (compact — show permit number, status dot, description, filed date)
   - "View property intelligence" expandable section (HTMX loads intel_preview)
5. Permit cards redesigned:
   - Status dot (green/amber/red) + permit type badge
   - Address, description (truncated to 2 lines)
   - Filed date, current status, estimated cost
   - "Prep Checklist" button (links to /prep, future feature — render but disable)
6. "No results" state with helpful suggestions

### Task 4: Add HTMX endpoint for intelligence preview

In `web/routes_search.py`, add:
```python
@bp.route("/lookup/intel-preview", methods=["POST"])
def lookup_intel_preview():
    """HTMX fragment: intelligence preview panel for a property."""
```

This endpoint:
- Takes block, lot, street_number, street_name from form data
- Runs the intelligence queries (routing, complaints, violations, entities)
- Returns rendered `fragments/intel_preview.html`
- 2-second timeout — if intelligence queries don't finish, return a "Loading..." spinner that auto-retries once
- No auth required

---

## PHASE 3: TEST

Write `tests/test_sprint69_s2.py`:
- /search returns 200 for anonymous users
- /lookup returns results with intel_data when address provided
- /lookup/intel-preview returns HTML fragment
- Intel preview contains routing progress section
- Intel preview contains entity connections section
- Intel preview gracefully degrades when no data available
- Search results page has two-column layout class on desktop
- Search results page has Obsidian design tokens in CSS
- Permit cards show status dots
- HTMX attributes present on intel-preview container
- Google Fonts import present in search results template
- No horizontal scroll at 375px viewport

Target: 15+ new tests.

Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task.

---

## PHASE 4: SCENARIOS

Append 3-5 scenarios to `scenarios-pending-review.md`:
- "Anonymous visitor searches an address and sees routing progress for active permits"
- "Intelligence panel loads asynchronously without blocking permit results"
- "Anonymous visitor sees entity names but cannot access full network analysis"
- "Search results degrade gracefully when intelligence queries time out"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/sprint69-s2-search-intel-qa.md`.

**Required Playwright checks:**
1. Start Flask test server
2. Navigate to `/search?q=1455+Market+St` — verify 200
3. Screenshot at 375px, 768px, 1440px
4. Verify permit result cards appear with status dots
5. Verify intelligence panel section exists (or HTMX placeholder)
6. POST to `/lookup` with address — verify response includes permit data
7. POST to `/lookup/intel-preview` with block/lot — verify HTML fragment returned
8. Verify no horizontal scroll at 375px
9. Verify search bar is functional (submit form)
10. Verify "Sign up free" CTA appears in intelligence panel

Save screenshots to `qa-results/screenshots/sprint69-s2/`
Write results to `qa-results/sprint69-s2-results.md`

Run QA. Fix FAILs. Loop until PASS or BLOCKED.

---

## PHASE 6: CHECKCHAT

### DeskRelay HANDOFF
- [ ] Search results: does the two-column layout feel like a premium product?
- [ ] Intelligence panel: do routing progress bars communicate depth at a glance?
- [ ] Entity connections: does "Smith & Associates (47 SF permits)" feel impressive?
- [ ] Mobile: does the expandable intelligence section feel natural?
- [ ] Overall: does a stranger searching an address think "how is this free?"

---

## File Ownership (Session 2 ONLY)
- `web/routes_search.py` (enhance /lookup + add /lookup/intel-preview)
- `web/templates/search_results_public.html` (REWRITE)
- `web/templates/fragments/intel_preview.html` (NEW)
- `web/templates/lookup_results.html` (restyle with Obsidian tokens if needed)
- `tests/test_sprint69_s2.py` (NEW)
- `qa-drop/sprint69-s2-search-intel-qa.md` (NEW)
- `qa-results/sprint69-s2-results.md` (NEW)

Do NOT touch: `web/templates/landing.html`, `web/static/design-system.css`, `web/static/style.css`, `web/routes_api.py`, `web/routes_misc.py`, `web/routes_public.py`, `docs/`, `src/tools/` (read only)
