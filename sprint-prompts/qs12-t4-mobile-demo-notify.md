# QS12 T4: Mobile Fixes + Demo Script + Notifications

> **EXECUTE IMMEDIATELY.** Spawn ALL 4 agents in PARALLEL (subagent_type="general-purpose", model="sonnet", isolation="worktree"). Do NOT summarize — execute now.

**Sprint:** QS12 — Demo-Ready: Visual Intelligence
**Terminal:** T4 — Mobile + Demo Script + Notifications
**Agents:** 4 (all parallel)
**Theme:** Fix the phone experience, create a sendable demo, build workflow notifications.

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
3. **NEVER merge to main.** T4 orchestrator handles merges.
4. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
5. **Scenario file**: `scenarios-t4-sprint97.md`
6. **Changelog file**: `CHANGELOG-t4-sprint97.md`

---

## Agent 4A Prompt — Mobile Critical Fixes

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before modifying CSS.

## YOUR TASK: Fix 3 critical mobile issues from the qa-mobile audit

### Issue 1: Ghost CTAs are 19px tall (UNTAPPABLE)

Every "Try it yourself →" link on the landing page is only 19px tall. Mobile touch
targets must be ≥ 32px (Apple HIG) or ≥ 44px (ideal).

Fix in web/static/obsidian.css:
```css
.ghost-cta {
  padding: 8px 0;  /* raises from 19px to ~35px */
}
```

This affects ALL ghost CTAs site-wide — verify it doesn't break desktop layout.

### Issue 2: MCP Demo Dots are 8px (INVISIBLE)

The carousel navigation dots for the MCP demo section are 8px — completely untappable.

Fix in web/static/mcp-demo.css:
```css
.mcp-demo-dot {
  width: 12px;
  height: 12px;
  padding: 10px;  /* increases touch target to 32px */
  box-sizing: content-box;
}
```

### Issue 3: Landing Page Has NO Mobile Navigation

The landing page (web/templates/landing.html) has no hamburger menu, no mobile nav panel.
The only navigation is an 11px "Sign in →" link that's 59x13px — untappable.

Fix: Add a minimal mobile nav bar at the top of the landing page for phone viewports:
```html
{% if request.user_agent.platform in ('iphone', 'android') or true %}
<nav class="mobile-nav-landing" style="display:none">
  <a href="/search">Search</a>
  <a href="/demo">Demo</a>
  <a href="/methodology">About</a>
  <a href="/auth/login">Sign in</a>
</nav>
{% endif %}
```

Use a `@media (max-width: 480px)` rule to show it. Style to match obsidian tokens.
Make touch targets ≥ 44px.

**IMPORTANT about landing.html:** T1 restructures the showcase section. T3 changes
the badge/arrow/links. You ONLY touch the mobile nav and nothing else in landing.html.
Add the nav element at the very top of the body, before the hero. Do NOT modify the
showcase section, stats section, or any other content.

### FILES YOU OWN
- MODIFY: web/static/obsidian.css (ghost-cta padding)
- MODIFY: web/static/mcp-demo.css (dot sizing)
- MODIFY: web/templates/landing.html (add mobile nav ONLY — at top of body, nothing else)
- CREATE: tests/test_mobile_fixes.py

### FILES YOU MUST NOT TOUCH
- showcase_*.html, mcp_demo.html, routes_*.py

### Tests
- Test ghost-cta CSS has padding ≥ 8px
- Test mcp-demo-dot CSS has adequate size
- Test landing page has mobile nav element
- Test mobile nav links are present (/search, /demo, /auth/login)
- At least 6 tests.
```

---

## Agent 4B Prompt — Minor Fixes

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Fix minor UX issues

### Fix 1: /demo Overflow at 375px
web/templates/demo.html has .callout elements that are display: inline-block with no
max-width, causing 300px overflow on phone.

Add to the mobile media query in demo.html:
```css
@media (max-width: 480px) {
  .callout { display: block; max-width: 100%; box-sizing: border-box; }
}
```

### Fix 2: Stats Counter "0"
If the landing page stats counter shows "0 SF building permits", the counting animation
may be broken. Check landing.html for the counting animation JS. If the target number
is hardcoded, ensure it's 1,137,816. If it's fetched dynamically and failing, hardcode it.

NOTE: Do NOT touch the showcase section or page structure of landing.html. ONLY modify
the stats/counter section. But check first — T1 Agent 1A may be killing the stats bar
entirely. If the stats section no longer exists in the template, skip this fix.

### Fix 3: Property Navigation State Machine
The landing page JS has 6 persona states (new, beta, beta_nowatch, returning,
returning_nowatch, power). Property clicks in beta/returning states may loop back to
the landing page instead of going to /report or /portfolio.

Check the JS state machine in landing.html. Each watched property click should navigate
to a useful destination, not reload the landing page.

### FILES YOU OWN
- MODIFY: web/templates/demo.html (overflow fix)
- MODIFY: web/templates/landing.html (ONLY stats counter + property navigation JS)
- CREATE: tests/test_minor_fixes.py

### FILES YOU MUST NOT TOUCH
- showcase_*.html, routes_*.py, obsidian.css (Agent 4A), tool pages

### Tests
- Test /demo page renders without errors
- Test demo.html has mobile callout fix
- At least 4 tests.
```

---

## Agent 4C Prompt — Guided Demo Page

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
Read docs/DESIGN_TOKENS.md before creating templates.

## YOUR TASK: Create /demo/guided — a self-guided walkthrough page

Tim needs a URL he can send to Charis, Amy, or any stakeholder for a self-guided demo.
Instead of a live walkthrough, the visitor clicks through at their own pace.

### Route
Add to web/routes_public.py (or routes_misc.py — check which is appropriate):
```python
@bp.route("/demo/guided")
def demo_guided():
    return render_template("demo_guided.html")
```

### Page Structure (demo_guided.html)

Use head_obsidian.html base. Full Obsidian tokens.

**Section 1: Hero**
"See what sfpermits.ai does"
Subtitle: "A 2-minute walkthrough of permit intelligence tools"

**Section 2: The Gantt (embed or screenshot)**
"We track every permit through every review station"
Show the Gantt showcase component or a static screenshot
"Every colored bar is a real review station. Every name is a real reviewer."

**Section 3: Try a Search**
Pre-filled search link: "Search 487 Noe St →" that links to /search?q=487+Noe+St
"See real permits, real reviewers, real timeline data"

**Section 4: Intelligence Tools**
4 cards linking to each tool with demo data pre-filled:
- "Diagnose a stuck permit →" → /tools/stuck-permit?permit=202412237330
- "Compare project scopes →" → /tools/what-if?demo=kitchen-vs-full
- "Check revision risk →" → /tools/revision-risk?demo=restaurant-mission
- "Calculate delay cost →" → /tools/cost-of-delay?demo=restaurant-15k

**Section 5: For Professionals**
"How Amy uses sfpermits.ai"
- Morning triage: scan 20 properties, see which are stuck
- Reviewer lookup: know who to call without calling DBI
- Intervention playbooks: specific actions, phone numbers, deadlines

**Section 6: Connect Your AI**
"Add sfpermits.ai to Claude, ChatGPT, or any AI assistant"
"Your AI gains access to 34 intelligence tools and 18M government records"
CTA: "Learn more →" (placeholder)

**Footer:** Link back to landing page.

### FILES YOU OWN
- CREATE: web/templates/demo_guided.html
- MODIFY: web/routes_public.py OR web/routes_misc.py (add /demo/guided route)
- CREATE: tests/test_demo_guided.py

### FILES YOU MUST NOT TOUCH
- landing.html, tool pages, search templates, routes_search.py

### Tests
- Test /demo/guided returns 200
- Test page contains all 6 sections
- Test tool links have correct query params
- Test page uses head_obsidian.html
- At least 8 tests.
```

---

## Agent 4D Prompt — Notification Hooks

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Build differentiated notification sounds for CC workflow events

Tim currently gets the same ping for every qa-results/ file write. He wants different
sounds for different events so he can hear sprint progress without watching terminals.

### Create scripts/notify.sh

```bash
#!/bin/bash
# Differentiated notification sounds for CC workflow events
# Usage: scripts/notify.sh <event_type> [message]

EVENT="$1"
MESSAGE="${2:-$EVENT}"

case "$EVENT" in
  agent-done)
    afplay /System/Library/Sounds/Tink.aiff &
    ;;
  terminal-done)
    afplay /System/Library/Sounds/Glass.aiff &
    ;;
  sprint-done)
    afplay /System/Library/Sounds/Hero.aiff &
    ;;
  qa-fail)
    afplay /System/Library/Sounds/Basso.aiff &
    ;;
  prod-promoted)
    afplay /System/Library/Sounds/Funk.aiff &
    ;;
  *)
    afplay /System/Library/Sounds/Pop.aiff &
    ;;
esac

# macOS notification center
osascript -e "display notification \"$MESSAGE\" with title \"sfpermits.ai\" subtitle \"$EVENT\"" 2>/dev/null
```

Make it executable: `chmod +x scripts/notify.sh`

### Hook Integration

Read .claude/settings.json and .claude/hooks/ to understand the current hook system.

The existing hooks fire on specific PostToolUse events. Add notification triggers:

1. **On qa-results/ write (existing):** Change from default sound to `notify.sh qa-fail`
   if the written content contains "FAIL"

2. **On CHECKQUAD COMPLETE pattern:** When a Write tool writes content containing
   "CHECKQUAD.*COMPLETE", trigger `notify.sh terminal-done`

3. **On prod push:** When Bash runs `git push origin prod`, trigger `notify.sh prod-promoted`

If modifying existing hooks is complex, create a NEW hook script
`.claude/hooks/notify-events.sh` that handles these patterns.

### Document in CLAUDE.md

Add a section to the project CLAUDE.md explaining the notification system:
- What sounds mean what
- How to test: `scripts/notify.sh agent-done "Test notification"`
- How to add new event types
- How to disable: remove the hook or `NOTIFY_ENABLED=0`

NOTE: Add to the END of CLAUDE.md. Do NOT modify existing sections.

### FILES YOU OWN
- CREATE: scripts/notify.sh
- CREATE OR MODIFY: .claude/hooks/notify-events.sh
- MODIFY: CLAUDE.md (APPEND notification section at end ONLY)
- CREATE: tests/test_notify.py

### FILES YOU MUST NOT TOUCH
- landing.html, routes_*.py, templates/*, obsidian.css
- Existing hooks (stop-checkchat.sh, block-playwright.sh, etc.) — do NOT modify

### Tests
- Test scripts/notify.sh exists and is executable
- Test each event type is handled (check case statement coverage)
- Test unknown event type falls back to default sound
- At least 6 tests.
```

---

## Post-Agent Merge + CHECKQUAD

Standard: escape CWD → merge all 4 (parallel, different files) → test → push → session artifact → signal done.

**NOTE on landing.html:** Agent 4A adds mobile nav. Agent 4B may touch stats/navigation JS.
T1 and T3 also touch landing.html. Merge order: T1 → T2 → T3 → T4. By the time T4 merges,
landing.html has T1's showcase restructure and T3's badge/arrow fixes. T4's changes are
ADDITIVE (mobile nav at top of body, stats counter fix). Resolve conflicts by keeping the
merged T1+T3 structure and adding T4's elements.
