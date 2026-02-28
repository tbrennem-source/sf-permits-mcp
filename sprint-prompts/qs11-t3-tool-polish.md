# QS11 T3: Intelligence Tool Page Polish + New Pages + Share Mechanic

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn Agents 3A + 3B + 3C in PARALLEL using the Agent tool (subagent_type="general-purpose", model="sonnet", isolation="worktree"). After all 3 complete, spawn Agent 3D (sequential — depends on 3A/3B/3C). Do NOT summarize or ask for confirmation — execute now. After all agents complete, run Post-Agent merge ceremony, then CHECKQUAD.

**Sprint:** QS11 — Intelligence-Forward Beta
**Terminal:** T3 — Intelligence Tool Page Polish + Share Mechanic
**Agents:** 4 (3A + 3B + 3C parallel → 3D sequential)
**Theme:** Polish tool pages from bare to showcase-quality, add 2 new pages, add share mechanic

---

## Terminal Overview

| Agent | Focus | Files Owned |
|---|---|---|
| 3A | Polish Station Predictor + Stuck Permit | tools/station_predictor.html, tools/stuck_permit.html, gantt-interactive.js |
| 3B | Polish What-If + Cost of Delay | tools/what_if.html, tools/cost_of_delay.html |
| 3C | New Entity Network + Revision Risk pages | tools/entity_network.html, tools/revision_risk.html, entity-graph.js, routes_search.py (append) |
| 3D | Share Mechanic (all 6 tool pages) | components/share_button.html, share.js, share.css, routes_api.py (append) |

**Build order:** 3A + 3B + 3C (parallel) → 3D (adds share button to all tool pages after merge)

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules (ALL agents must follow)

1. **Worktree**: You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run `git checkout main`. Do NOT run `git merge`.
2. **No descoping**: Do not skip tasks. Flag blockers.
3. **Early commit**: Commit within 10 minutes.
4. **CRITICAL: NEVER merge to main.** T3 orchestrator handles merges.
5. **File ownership**: Only touch files in YOUR assignment.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Write to `scenarios-t3-sprint92.md`.
8. **Changelog file**: Write to `CHANGELOG-t3-sprint92.md`.
9. **Design system**: Read `docs/DESIGN_TOKENS.md` FIRST. Use ONLY token components.

---

## DuckDB / Postgres Gotchas

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use `conn.autocommit = True` for DDL

---

## Agent 3A Prompt — Polish Station Predictor + Stuck Permit

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Polish Station Predictor and Stuck Permit tool pages

Upgrade the bare QS10 tool pages into full interactive experiences.

### Context

These pages were created in QS10 as minimal templates. They currently render basic content.
T2 will have migrated them to Obsidian tokens before T3 merges, so build on top of the
token-compliant baseline.

### Station Predictor (/tools/station-predictor)

Current: bare template with basic layout.
After polish:
1. **Input area**: Permit number text input + "Analyze" button. If arrived via
   `?permit=202509155257` query param, auto-fill and auto-run.
2. **Interactive Gantt chart**: Horizontal bars per station, color-coded by status.
   Uses JS (not static HTML). User can hover stations for details.
   Create web/static/js/gantt-interactive.js for the chart rendering.
3. **Station detail panel**: Click a station bar → show reviewer name, date, round number.
4. **"How we know this" expandable**: Methodology section explaining data sources.
5. **Loading state**: Skeleton screen while HTMX fetches data.
6. **Empty state**: "Enter a permit number above" with suggested demo permits.

### Stuck Permit Analyzer (/tools/stuck-permit)

Current: bare template.
After polish:
1. **Input area**: Permit number input + "Diagnose" button. Auto-fill from `?permit=`.
2. **Severity dashboard**: RED/AMBER/GREEN severity badge. Block count.
3. **Block cards**: Each blocked station gets a card with reviewer, round, date, status.
4. **Intervention playbook**: Numbered action steps with specific phone numbers and names.
5. **Timeline impact**: "Each comment-response cycle adds 6-8 weeks"
6. **Loading state**: Skeleton screen.
7. **Empty state**: Suggested demo permits.

### HTMX Pattern for Tool Pages

These pages use HTMX for dynamic content:
```html
<form hx-post="/ask" hx-target="#results" hx-indicator="#loading">
  <input type="text" name="q" placeholder="Enter permit number..."
         value="{{ request.args.get('permit', '') }}">
  <button type="submit" class="ghost-cta">Analyze</button>
</form>
<div id="loading" class="htmx-indicator">Analyzing...</div>
<div id="results"></div>
```

If `?permit=` is in the URL, auto-trigger the analysis on page load:
```javascript
document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('permit')) {
    document.querySelector('form').requestSubmit();
  }
});
```

### FILES YOU OWN
- MODIFY: web/templates/tools/station_predictor.html
- MODIFY: web/templates/tools/stuck_permit.html
- CREATE: web/static/js/gantt-interactive.js
- CREATE: tests/test_tools_polish_a.py

### FILES YOU MUST NOT TOUCH
- web/routes_search.py (Agent 3C owns route changes)
- web/routes_api.py (Agent 3D owns share endpoint)
- tools/what_if.html, tools/cost_of_delay.html (Agent 3B)
- tools/entity_network.html, tools/revision_risk.html (Agent 3C)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_tools_polish_a.py)
- Test station_predictor template renders with empty state
- Test station_predictor template renders with sample data
- Test stuck_permit template renders with empty state
- Test stuck_permit template renders with severity badges
- Test ?permit= query param auto-fills input
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read current tools/station_predictor.html and tools/stuck_permit.html
3. Read src/tools/predict_next_stations.py and src/tools/stuck_permit.py (understand data format)
4. Polish station_predictor.html with interactive Gantt
5. Create gantt-interactive.js
6. Polish stuck_permit.html with severity dashboard + playbook
7. Create tests
8. Run tests + full suite
9. Run design lint: python scripts/design_lint.py --files web/templates/tools/station_predictor.html web/templates/tools/stuck_permit.html
10. Commit, write scenarios + changelog
```

---

## Agent 3B Prompt — Polish What-If + Cost of Delay

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Polish What-If Simulator and Cost of Delay tool pages

### What-If Simulator (/tools/what-if)

Current: bare template.
After polish:
1. **Input area**: Two-panel form. Left: "Project A" (scope, cost, neighborhood).
   Right: "Project B" (modified scope). If arrived via `?demo=kitchen-vs-full`,
   auto-fill both panels with the demo data and auto-run comparison.
2. **Comparison table**: Two columns with red/green indicators on dramatic differences.
   Rows: Cost, Review Path, Agencies, Timeline (p50/p75), Fees, Plans Signed By, ADA, Revision Risk.
3. **Strategy callout**: Highlighted recommendation (e.g., "Consider splitting into two permits")
4. **Loading state**: Skeleton screen.
5. **Empty state**: "Compare two project scopes" with suggested demo.

### Cost of Delay Calculator (/tools/cost-of-delay)

Current: bare template.
After polish:
1. **Input area**: Monthly carrying cost input (pre-filled $15K for demo).
   Neighborhood selector (affects timeline estimates).
   If arrived via `?demo=restaurant-15k`, auto-fill and auto-run.
2. **Percentile table**: p25/p50/p75/p90 days and costs.
3. **Expected cost highlight**: Probability-weighted total in a prominent card.
4. **Bottleneck alert**: Warning badge for slow stations (e.g., "SFFD-HQ +86% slower").
5. **Recommendation**: "Budget for p75, not p50"
6. **Loading state + empty state**.

### FILES YOU OWN
- MODIFY: web/templates/tools/what_if.html
- MODIFY: web/templates/tools/cost_of_delay.html
- CREATE: tests/test_tools_polish_b.py

### FILES YOU MUST NOT TOUCH
- web/routes_search.py, web/routes_api.py
- tools/station_predictor.html, tools/stuck_permit.html (Agent 3A)
- tools/entity_network.html, tools/revision_risk.html (Agent 3C)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_tools_polish_b.py)
- Test what_if template renders with empty state
- Test what_if template renders with comparison data
- Test cost_of_delay renders with percentile data
- Test ?demo= query param auto-fills
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read current templates
3. Read src/tools/what_if_simulator.py and src/tools/cost_of_delay.py
4. Polish both templates
5. Create tests, run tests + full suite
6. Run design lint
7. Commit, write scenarios + changelog
```

---

## Agent 3C Prompt — New Entity Network + Revision Risk Pages

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Create Entity Network and Revision Risk tool pages + routes

Two entirely new tool pages with their routes in routes_search.py.

### Entity Network (/tools/entity-network)

1. **Input area**: Address or entity name text input. If arrived via
   `?address=1+Market+St`, auto-fill and auto-run.
2. **Force-directed graph**: D3.js node graph.
   - Central node: address/entity
   - Connected nodes: top contractors, architects, engineers
   - Node size proportional to permit count
   - Edge labels: relationship type (contractor, architect, engineer)
   - Click node to expand → shows that entity's permit history
3. **Entity detail panel**: Sidebar with license number, permit count, avg issuance time
4. **Loading state + empty state**
5. Create web/static/js/entity-graph.js for D3 visualization
6. Load D3 from CDN: `<script src="https://d3js.org/d3.v7.min.js"></script>`

### Revision Risk (/tools/revision-risk)

1. **Input area**: Form with permit type dropdown, neighborhood dropdown, project type text.
   If arrived via `?demo=restaurant-mission`, auto-fill and auto-run.
2. **Risk gauge**: Circular or bar gauge showing revision probability (0-100%).
   Color-coded: green (< 15%), amber (15-25%), red (> 25%).
3. **Correction triggers**: Numbered list of top 5 triggers with descriptions.
4. **Timeline impact**: "+N days average" with visual bar.
5. **Mitigation strategies**: Actionable recommendations to reduce risk.
6. **Loading state + empty state**

### Routes (APPEND to routes_search.py)

The existing routes_search.py has 4 tool routes ending at line 1653. Append at EOF:

```python
# ---------------------------------------------------------------------------
# Entity Network — /tools/entity-network (Sprint QS11-T3-3C)
# ---------------------------------------------------------------------------

@bp.route("/tools/entity-network")
def tools_entity_network():
    """Entity Network: visualize professional relationships around a property."""
    return render_template("tools/entity_network.html")


# ---------------------------------------------------------------------------
# Revision Risk — /tools/revision-risk (Sprint QS11-T3-3C)
# ---------------------------------------------------------------------------

@bp.route("/tools/revision-risk")
def tools_revision_risk():
    """Revision Risk: predict probability of plan corrections."""
    return render_template("tools/revision_risk.html")
```

**IMPORTANT about routes_search.py:** This file is shared with T4 (who may add decorators
later). APPEND at EOF ONLY. Do NOT reorganize or reformat existing routes. Do NOT modify
the existing 4 tool routes (station-predictor, stuck-permit, what-if, cost-of-delay).

Also add the import at the top of routes_search.py if needed:
```python
from web.tier_gate import has_tier
```

### FILES YOU OWN
- CREATE: web/templates/tools/entity_network.html
- CREATE: web/templates/tools/revision_risk.html
- CREATE: web/static/js/entity-graph.js (D3 force-directed graph)
- MODIFY: web/routes_search.py (APPEND 2 routes at EOF only)
- CREATE: tests/test_tools_new.py

### FILES YOU MUST NOT TOUCH
- tools/station_predictor.html, tools/stuck_permit.html (Agent 3A)
- tools/what_if.html, tools/cost_of_delay.html (Agent 3B)
- web/routes_api.py (Agent 3D)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_tools_new.py)
- Test /tools/entity-network route returns 200
- Test /tools/revision-risk route returns 200
- Test entity_network template renders with empty state
- Test entity_network template renders with sample graph data
- Test revision_risk template renders with risk gauge data
- Test ?address= and ?demo= query params auto-fill
- At least 10 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read web/routes_search.py (understand route pattern, see lines 1605-1653)
3. Read src/tools/permit_lookup.py (entity data format)
4. Read src/tools/revision_risk.py (risk data format)
5. Create entity_network.html + entity-graph.js
6. Create revision_risk.html
7. Append 2 routes to routes_search.py
8. Create tests, run tests + full suite
9. Run design lint
10. Commit, write scenarios + changelog
```

---

## Agent 3D Prompt — Share Mechanic

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Build the share mechanic for intelligence tool pages

Create the engineered referral mechanism. When a user sees an intelligence result they want
to share, they click "Send this to your contractor" → share via Web Share API (mobile) or
copy-to-clipboard (desktop). This is the mechanism that turns the organic "tell your contractor"
moment into a one-tap action.

### IMPORTANT CONTEXT

This agent runs AFTER 3A, 3B, and 3C. The tool page templates will already be polished.
You add the share button to ALL 6 tool pages.

### Share Button Component

Create web/templates/components/share_button.html:
```html
<div class="share-container" data-track="share-view">
  <button class="share-btn ghost-cta" data-track="share-click"
          data-share-title="SF Permit Intelligence"
          data-share-text="Check out this permit analysis from sfpermits.ai">
    <span class="share-icon">↗</span>
    Send this to your contractor
  </button>
  <div class="share-copied" style="display:none">Link copied!</div>
</div>
```

### Share JavaScript (web/static/js/share.js)

```javascript
// Web Share API on mobile, copy-to-clipboard on desktop
document.querySelectorAll('.share-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const url = window.location.href;
    const title = btn.dataset.shareTitle;
    const text = btn.dataset.shareText;

    if (navigator.share) {
      // Mobile: native share sheet
      try {
        await navigator.share({ title, text, url });
      } catch (e) {
        if (e.name !== 'AbortError') console.error(e);
      }
    } else {
      // Desktop: copy to clipboard
      try {
        await navigator.clipboard.writeText(url);
        const copied = btn.closest('.share-container').querySelector('.share-copied');
        copied.style.display = 'block';
        setTimeout(() => copied.style.display = 'none', 2000);
      } catch (e) {
        // Fallback for older browsers
        const ta = document.createElement('textarea');
        ta.value = url;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
    }
  });
});
```

### Share CSS (web/static/css/share.css)

Style the share button to match design tokens:
- Use ghost-cta pattern from DESIGN_TOKENS.md
- Hover: subtle highlight
- "Link copied!" confirmation: green text, fades out
- Mobile: full-width share button
- Desktop: inline, right-aligned

### Add Share Button to All 6 Tool Pages

Add `{% include "components/share_button.html" %}` to each tool page's results section:
1. tools/station_predictor.html (after results div)
2. tools/stuck_permit.html (after results div)
3. tools/what_if.html (after comparison table)
4. tools/cost_of_delay.html (after percentile table)
5. tools/entity_network.html (after graph)
6. tools/revision_risk.html (after risk gauge)

Also add `<link rel="stylesheet" href="{{ url_for('static', filename='css/share.css') }}">` and
`<script src="{{ url_for('static', filename='js/share.js') }}"></script>` to each page.

### Share API Endpoint (OPTIONAL — if time permits)

Append to web/routes_api.py:

```python
@bp.route("/api/share", methods=["POST"])
def create_share():
    """Create a shareable link with pre-computed results."""
    # For now, just return the current URL — no backend persistence
    data = request.get_json(silent=True) or {}
    return jsonify({"url": data.get("url", request.url), "shared": True})
```

This endpoint is a placeholder for future shareable-link persistence (short URLs, etc.).

### FILES YOU OWN
- CREATE: web/templates/components/share_button.html
- CREATE: web/static/js/share.js
- CREATE: web/static/css/share.css
- MODIFY: web/templates/tools/station_predictor.html (add include)
- MODIFY: web/templates/tools/stuck_permit.html (add include)
- MODIFY: web/templates/tools/what_if.html (add include)
- MODIFY: web/templates/tools/cost_of_delay.html (add include)
- MODIFY: web/templates/tools/entity_network.html (add include)
- MODIFY: web/templates/tools/revision_risk.html (add include)
- MODIFY: web/routes_api.py (append share endpoint — if time permits)
- CREATE: tests/test_share_mechanic.py

### FILES YOU MUST NOT TOUCH
- web/routes_search.py (Agent 3C owns this)
- web/routes_public.py, web/templates/landing.html
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_share_mechanic.py)
- Test share_button.html renders correctly
- Test share.js exists and contains Web Share API check
- Test share.css exists and uses token variables
- Test each of the 6 tool pages includes the share button partial
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Create share_button.html, share.js, share.css
3. Read each tool page template (all 6)
4. Add share button include to each tool page
5. Optionally create the /api/share endpoint
6. Create tests, run tests + full suite
7. Commit, write scenarios + changelog
```

---

## Post-Agent Merge Ceremony

After ALL 4 agents complete:

```bash
# Step 0: ESCAPE CWD
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

# Step 1: Pull latest main (T2 should have merged already)
git checkout main && git pull origin main

# Step 2: Merge agents in dependency order
# 3A, 3B, 3C first (parallel, no overlap)
git merge <3A-branch> --no-ff -m "feat(tools): polish station predictor + stuck permit"
git merge <3B-branch> --no-ff -m "feat(tools): polish what-if + cost of delay"
git merge <3C-branch> --no-ff -m "feat(tools): new entity network + revision risk pages"

# 3D last (touches all tool pages)
git merge <3D-branch> --no-ff -m "feat(share): share mechanic for all tool pages"
# NOTE: 3D merge may need manual resolution if tool page templates changed significantly.
# 3D only adds an {% include %} and script/css links — these should merge cleanly.

# Step 3: Quick test
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x

# Step 4: Verify new routes
python -c "
from web.app import create_app
app = create_app()
rules = [r.rule for r in app.url_map.iter_rules()]
assert '/tools/entity-network' in rules, 'entity-network route missing'
assert '/tools/revision-risk' in rules, 'revision-risk route missing'
print('New routes verified')
"

# Step 5: Design lint
python scripts/design_lint.py --changed --quiet

# Step 6: Push
git push origin main
```

---

## CHECKQUAD

### Step 0: ESCAPE CWD
`cd /Users/timbrenneman/AIprojects/sf-permits-mcp`

### Step 1: MERGE
See Post-Agent Merge Ceremony above.

### Step 2: ARTIFACT
Write `qa-drop/qs11-t3-session.md` with:
- Agent results table (4 agents)
- New routes added
- Share mechanic status
- Design lint scores

### Step 3: CAPTURE
- Concatenate scenario files → `scenarios-t3-sprint92.md`
- Concatenate changelog files → `CHANGELOG-t3-sprint92.md`

### Step 4: HYGIENE CHECK
```bash
python scripts/test_hygiene.py --changed --quiet 2>/dev/null || echo "No test_hygiene.py"
```

### Step 5: SIGNAL DONE
```
═══════════════════════════════════════════════════
  CHECKQUAD T3 COMPLETE — Tool Polish + Share Mechanic
  Sprint 92 · 4 agents · X/4 PASS
  New pages: 2 · Share mechanic: 6 pages
  Pushed: <commit hash>
  Session: qa-drop/qs11-t3-session.md
═══════════════════════════════════════════════════
```

Do NOT run `git worktree remove` or `git worktree prune`. T0 handles cleanup.
