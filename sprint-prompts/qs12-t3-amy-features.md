# QS12 T3: Amy's "I Need This" Features + UX Fixes

> **EXECUTE IMMEDIATELY.** Spawn ALL 4 agents in PARALLEL (subagent_type="general-purpose", model="sonnet", isolation="worktree"). Do NOT summarize — execute now.

**Sprint:** QS12 — Demo-Ready: Visual Intelligence
**Terminal:** T3 — Amy's "I Need This" + UX Fixes
**Agents:** 4 (all parallel)
**Theme:** Surface intelligence without login. Fix the funnel breaks.

---

## Why This Terminal Matters

From the persona-amy audit: "Reviewer names are the killer feature. Amy can see ARRIOLA LAURA
approved SFPUC on Feb 11 — she knows exactly who to follow up with." But tool pages are
login-walled, search results hide triage signals behind auth, and permit clicks send users
to the external DBI portal. The intelligence EXISTS but visitors can't SEE it.

---

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git log --oneline -3
```

---

## Agent Rules

1. **Worktree**: ALREADY in worktree. No checkout main. No merge.
2. **Early commit**: Within 10 minutes.
3. **NEVER merge to main.** T3 orchestrator handles merges.
4. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
5. **Scenario file**: `scenarios-t3-sprint96.md`
6. **Changelog file**: `CHANGELOG-t3-sprint96.md`

---

## DuckDB / Postgres Gotchas

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`

---

## Agent 3A Prompt — Remove Tool Page Login Walls

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Make all 6 tool pages accessible without login

### The Problem
4 of 6 tool routes in web/routes_search.py redirect anonymous users to /auth/login.
The landing page showcases say "Try it yourself →" but clicking hits a login wall.
The funnel dies at the moment of highest intent.

### Current Code (routes_search.py)
Lines ~1609-1653 have 4 routes:
- /tools/station-predictor: `if not g.user: return redirect("/auth/login")`
- /tools/stuck-permit: same
- /tools/what-if: same
- /tools/cost-of-delay: same

The 2 newer routes (/tools/entity-network, /tools/revision-risk) do NOT have this guard.

### The Fix
1. Remove the `if not g.user: return redirect("/auth/login")` from all 4 routes
2. Tool pages render for EVERYONE with demo data pre-filled
3. The templates already support ?permit= and ?demo= query params (QS11 T3 added this)
4. For logged-in users: full functionality (input any permit)
5. For anonymous users: demo data + a soft CTA somewhere on the page:
   "Sign up to analyze your own permits → /beta/join" (small, non-blocking, below results)

### IMPORTANT: Check for tests that assert redirect behavior
Search tests/ for assertions like `assert resp.status_code in (301, 302)` on these routes.
If any tests expect a redirect for anonymous users, UPDATE the test to expect 200 instead.

### FILES YOU OWN
- MODIFY: web/routes_search.py (4 route modifications — remove auth redirects)
- MODIFY: web/templates/tools/station_predictor.html (add anonymous soft CTA)
- MODIFY: web/templates/tools/stuck_permit.html (same)
- MODIFY: web/templates/tools/what_if.html (same)
- MODIFY: web/templates/tools/cost_of_delay.html (same)
- CREATE: tests/test_tool_public_access.py

### FILES YOU MUST NOT TOUCH
- landing.html, showcase_*.html, routes_public.py
- intent_router.py (Agent 3C)
- search result templates (Agents 3B/3D)

### Tests
- Test all 6 tool routes return 200 for anonymous users (no redirect)
- Test tool pages contain demo data or empty state (not login form)
- Test logged-in users still see full functionality
- Test soft CTA is present for anonymous users
- At least 10 tests.
```

---

## Agent 3B Prompt — Surface Intelligence on Search Results

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Add triage intelligence signals to search result cards

### Amy's Problem
She triages 20 properties every morning. If days-at-station and stuck signals require
login, she checks the 2-3 she suspects and misses the others. Surface the triage signal
on the PUBLIC search results page.

### What to Add to Each Permit Row in Search Results

1. **Days-at-current-station** (if available in the data):
   Show "37 days at Plan Check" with color coding:
   - Green (--dot-green): < median days for that station
   - Amber (--dot-amber): 1.5x median
   - Red (--dot-red): > 2x median
   Format: small badge/pill below the permit status

2. **Reviewer name** on most recent plan review action:
   "Reviewer: ARRIOLA LAURA" in --text-secondary, small
   This is already in the SODA data — surface it in the template

3. **Stuck indicator**: Red dot or badge if days > 2x median
   "⚠ Stuck" in red next to the station name

### Implementation Notes
- The search results come from SODA API responses via routes_public.py or routes_search.py
- Plan review data includes reviewer names, station names, dates
- You may need to add a helper function that calculates days-at-station from the last
  routing record timestamp
- If median data isn't available, use hardcoded medians by station (from the existing
  station_velocity data or reasonable defaults)

### FILES YOU OWN
- MODIFY: web/templates/search_results_public.html (add intelligence signals)
- MODIFY: web/templates/results.html (same signals for authenticated view)
- MODIFY: web/routes_public.py (pass station timing data to template if needed)
- CREATE: tests/test_search_intelligence.py

### FILES YOU MUST NOT TOUCH
- landing.html, showcase_*.html, tool pages, routes_search.py

### Tests
- Test search results page renders with intelligence signals
- Test days-at-station badge is present when data available
- Test reviewer name is visible
- Test color coding logic (green/amber/red thresholds)
- At least 8 tests.
```

---

## Agent 3C Prompt — Search Routing + Landing UX Fixes

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Fix search routing for questions + landing page UX bugs

### Job 1: Search Routing

"Do I need a permit for a kitchen remodel?" returns "no permits found" instead of an
intelligent response.

Read src/tools/intent_router.py. The intent router classifies queries. Natural language
questions should route to AI consultation (/ask), not literal permit search.

Add question-pattern detection:
- Starts with: "do I", "how long", "what do I need", "can I", "should I", "is it", "will"
- Contains: "need a permit", "how much", "how many", "what's required"
- These should classify as intent "question" or "ai_consultation"

The /search route in routes_public.py or routes_search.py should check the intent and
redirect question-type queries to the AI consultation flow.

### Job 2: Landing UX Fixes

IMPORTANT: landing.html is owned by T1 for the showcase restructure. You may ONLY touch
these specific elements. Do NOT change the showcase section or page structure.

1. **BETA badge → "Beta Tester"** — Find the beta-badge element (id="beta-badge") and
   change the text from "beta" to "Beta Tester"
2. **Down arrow opacity** — Find .scroll-cue and increase opacity from current to 0.6
   or use --text-secondary color
3. **Redundant "Do I need a permit" links** — If there are two instances, consolidate to one
4. **Property click loops (#11/#12)** — Beta/returning state property clicks should go to
   /report or /portfolio, not loop back to landing. Check the JS state machine.

### FILES YOU OWN
- MODIFY: src/tools/intent_router.py (add question detection)
- MODIFY: web/templates/landing.html (ONLY badge, arrow, links, property navigation — NOT showcase section)
- CREATE: tests/test_search_routing_questions.py
- CREATE: tests/test_landing_ux_fixes.py

### FILES YOU MUST NOT TOUCH
- showcase_*.html, mcp-demo.*, routes_search.py (Agent 3A), search result templates (Agent 3B)

### Tests
- Test question-format queries classify as question/consultation intent
- Test non-question queries still classify as search
- Test BETA badge text is "Beta Tester"
- Test scroll-cue has appropriate opacity
- At least 8 tests.
```

---

## Agent 3D Prompt — Permit Row Click Target

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Fix permit number click targets in search results

### The Problem
When Amy clicks a permit number in search results, she expects AI analysis. Instead,
she lands on the external DBI portal (dbiweb02.sfgov.org). The value proposition breaks
at the most natural click target on the page.

### The Fix
1. Change the primary click target for permit numbers from DBI portal URL to:
   `/tools/station-predictor?permit=<permit_number>`
   This shows the internal analysis page with Gantt chart and station details.

2. Keep the DBI link as a SECONDARY option:
   Small "View on DBI →" link (--text-tertiary, small font) next to or below the
   permit number. This is the escape hatch for users who specifically want DBI.

3. The format should be:
   ```html
   <a href="/tools/station-predictor?permit={{ permit.number }}"
      class="permit-link">{{ permit.number }}</a>
   <a href="https://dbiweb02.sfgov.org/dbipts/..." class="dbi-link"
      target="_blank" rel="noopener">View on DBI →</a>
   ```

### Files to Check
Search result templates render permit rows. Find where the `<a href>` links to DBI
and change it. Check:
- web/templates/search_results_public.html
- web/templates/results.html
- web/templates/search_results.html
- Any fragments that render permit table rows

### FILES YOU OWN
- MODIFY: web/templates/search_results_public.html (permit link targets)
- MODIFY: web/templates/results.html (same)
- MODIFY: web/templates/search_results.html (same)
- CREATE: tests/test_permit_click_target.py

### FILES YOU MUST NOT TOUCH
- landing.html, routes_*.py, tool pages, intent_router.py

### Tests
- Test permit numbers link to /tools/station-predictor?permit=
- Test DBI link is present as secondary (target="_blank")
- Test DBI link has "View on DBI" text
- At least 6 tests.
```

---

## Post-Agent Merge + CHECKQUAD

Standard: escape CWD → merge all 4 (parallel, different files) → test → push → session artifact → signal done.

**NOTE on landing.html:** Agent 3C touches landing.html (badge/arrow/links). T1 also touches landing.html (showcase restructure). T1 merges FIRST. When T3 merges, resolve any conflicts by keeping T1's structure and re-applying 3C's targeted edits (badge text, arrow opacity, link consolidation).
