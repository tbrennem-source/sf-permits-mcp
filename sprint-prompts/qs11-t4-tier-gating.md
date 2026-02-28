# QS11 T4: Tier Gating + Onboarding Polish

> **EXECUTE IMMEDIATELY.** You are a terminal orchestrator. Read this prompt, run Pre-Flight, then spawn Agents 4A + 4B in PARALLEL, and Agents 4C + 4D in PARALLEL. All 4 can run simultaneously (no file conflicts). Do NOT summarize or ask for confirmation — execute now. After all agents complete, run Post-Agent merge ceremony, then CHECKQUAD.

**Sprint:** QS11 — Intelligence-Forward Beta
**Terminal:** T4 — Tier Gating + Onboarding Polish
**Agents:** 4 (all parallel — no dependencies between agents)
**Theme:** Free sees showcases + blur. Beta sees everything + own properties.

---

## Terminal Overview

| Agent | Focus | Files Owned |
|---|---|---|
| 4A | Tier Gate Backend | web/tier_gate.py, web/app.py (add middleware hook only) |
| 4B | Tier Gate Frontend | components/tier_gate_overlay.html, tier-gate.css, tier-gate.js |
| 4C | Onboarding Polish | onboarding_step1/2/3.html, routes_auth.py |
| 4D | Gate Analytics + Email Templates | PostHog events in tier_gate.py, email template migration |

**All 4 agents run in parallel — zero file overlap.**

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
4. **CRITICAL: NEVER merge to main.** T4 orchestrator handles merges.
5. **File ownership**: Only touch files in YOUR assignment.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Write to `scenarios-t4-sprint93.md`.
8. **Changelog file**: Write to `CHANGELOG-t4-sprint93.md`.
9. **Design system**: Read `docs/DESIGN_TOKENS.md` FIRST for any template/CSS work.

---

## DuckDB / Postgres Gotchas

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use `conn.autocommit = True` for DDL

---

## Agent 4A Prompt — Tier Gate Backend

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Enhance tier gate system with teaser mode

The existing tier gate (web/tier_gate.py, 95 lines) has @requires_tier('beta') that either
redirects to login (anonymous) or returns a 403 with tier_gate_teaser.html (free users).

Enhance it with a TEASER mode that renders a blur overlay instead of redirecting or 403-ing.

### Current State

Read web/tier_gate.py first. It has:
- _TIER_LEVELS = {"free": 0, "beta": 1, "premium": 2}
- has_tier(user, required_tier) → bool
- requires_tier(required_tier) → decorator (redirects anonymous, 403s free users)

### What to Add

1. **Enhance requires_tier with teaser parameter:**

```python
def requires_tier(required_tier: str, teaser: bool = False):
    """Decorator: gate a route behind a subscription tier.

    Args:
        required_tier: 'beta' or 'premium'
        teaser: If True, render the page content with a blur overlay + signup CTA
                instead of a hard redirect or 403. The wrapped function IS called,
                but a flag is set so the template can add the overlay.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")

            if teaser:
                # Teaser mode: always call the wrapped function, but set a flag
                g.tier_locked = not has_tier(user, required_tier) if user else True
                g.tier_required = required_tier
                g.tier_current = (user.get("subscription_tier", "free") if user else "anonymous")
                return fn(*args, **kwargs)
            else:
                # Hard gate mode (existing behavior)
                if not user:
                    return redirect(url_for("auth.auth_login"))
                if not has_tier(user, required_tier):
                    return render_template(
                        "fragments/tier_gate_teaser.html",
                        required_tier=required_tier,
                        current_tier=user.get("subscription_tier", "free"),
                        user=user,
                    ), 403
                return fn(*args, **kwargs)
        return wrapper
    return decorator
```

2. **Add a context processor in web/app.py** so templates can check `tier_locked`:

Find the `inject_posthog()` or similar context processor section in app.py. Add:

```python
@app.context_processor
def inject_tier_gate():
    return {
        "tier_locked": getattr(g, "tier_locked", False),
        "tier_required": getattr(g, "tier_required", None),
        "tier_current": getattr(g, "tier_current", None),
    }
```

IMPORTANT: Only ADD this context processor. Do NOT modify any other part of app.py.
app.py is ~1,061 lines. Find the right section, add ~6 lines.

3. **The existing tool routes use `if not g.user: redirect` pattern.** Do NOT change these.
   Tool pages are accessible to everyone (they show demo data). The tier gate with teaser=True
   is for deep pages (portfolio, brief, dashboard) — those are already login-required.

### FILES YOU OWN
- MODIFY: web/tier_gate.py (enhance requires_tier)
- MODIFY: web/app.py (add context processor ONLY — ~6 lines)
- CREATE: tests/test_tier_gate_enhanced.py

### FILES YOU MUST NOT TOUCH
- web/routes_search.py, web/routes_public.py, web/routes_auth.py
- web/templates/* (Agent 4B owns the overlay template)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_tier_gate_enhanced.py)
- Test requires_tier with teaser=False still redirects anonymous
- Test requires_tier with teaser=False still 403s free users
- Test requires_tier with teaser=True sets g.tier_locked=True for free users
- Test requires_tier with teaser=True sets g.tier_locked=False for beta users
- Test requires_tier with teaser=True sets g.tier_locked=True for anonymous
- Test has_tier with all tier combinations
- Test context processor injects tier_locked
- At least 10 tests.

### Steps
1. Read web/tier_gate.py (95 lines)
2. Read web/app.py — find context processor section (search for @app.context_processor)
3. Enhance requires_tier with teaser parameter
4. Add context processor to app.py
5. Create tests
6. Run tests + full suite
7. Commit, write scenarios + changelog
```

---

## Agent 4B Prompt — Tier Gate Frontend

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Build tier gate overlay UI (blur + CTA)

Create the visual overlay that appears when a free user visits a gated page in teaser mode.
The page content renders normally but is covered with a blur overlay + signup CTA.

### Overlay Component (web/templates/components/tier_gate_overlay.html)

This partial is included at the bottom of gated page templates. It checks the `tier_locked`
template variable (injected by the context processor from Agent 4A).

```html
{% if tier_locked %}
<div class="tier-gate-overlay" data-track="tier-gate-impression"
     data-tier-required="{{ tier_required }}" data-tier-current="{{ tier_current }}">
  <div class="tier-gate-card glass-card">
    <h3>See this for your property</h3>
    <p>Get full access to permit intelligence for your address.</p>
    <a href="/beta/join" class="ghost-cta tier-gate-cta" data-track="tier-gate-click">
      Get access →
    </a>
    <p class="tier-gate-subtext">Free during beta. Takes 30 seconds.</p>
  </div>
</div>
{% endif %}
```

### CSS (web/static/css/tier-gate.css)

The blur overlay uses CSS filter to make page content visible but unreadable:

```css
/* When tier_locked, apply blur to the page content */
.tier-locked-content {
  filter: blur(8px);
  pointer-events: none;
  user-select: none;
  transition: filter 0.3s ease;
}

.tier-gate-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  background: rgba(0, 0, 0, 0.3);
}

.tier-gate-card {
  max-width: 420px;
  padding: var(--space-xl);
  text-align: center;
}

.tier-gate-card h3 {
  font-family: var(--sans);
  font-size: 1.5rem;
  color: var(--text-primary);
  margin-bottom: var(--space-md);
}

.tier-gate-card p {
  font-family: var(--sans);
  color: var(--text-secondary);
  margin-bottom: var(--space-lg);
}

.tier-gate-cta {
  font-size: 1.1rem;
  padding: var(--space-md) var(--space-xl);
}

.tier-gate-subtext {
  font-size: 0.85rem;
  color: var(--text-tertiary);
  margin-top: var(--space-md);
}

/* Mobile */
@media (max-width: 480px) {
  .tier-gate-card {
    margin: 0 var(--space-md);
    padding: var(--space-lg);
  }
}
```

### JavaScript (web/static/js/tier-gate.js)

```javascript
// Add blur class to main content when gate is active
document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.querySelector('.tier-gate-overlay');
  if (overlay) {
    // Find the main content container and blur it
    const main = document.querySelector('main, .obs-container, .obs-container-wide');
    if (main) {
      main.classList.add('tier-locked-content');
    }
  }
});
```

### Blur Calibration

**8px blur** — tantalizing but unreadable. The user can see shapes, colors, and layout structure
(enough to know the content is valuable) but cannot read text or data. This creates desire
without frustration. Do NOT use more than 8px (hostile) or less than 5px (readable).

### FILES YOU OWN
- CREATE: web/templates/components/tier_gate_overlay.html
- CREATE: web/static/css/tier-gate.css
- CREATE: web/static/js/tier-gate.js
- CREATE: tests/test_tier_gate_ui.py

### FILES YOU MUST NOT TOUCH
- web/tier_gate.py (Agent 4A owns this)
- web/app.py (Agent 4A owns this)
- web/routes_*.py
- web/templates/tools/* (T3 owns these)
- web/templates/landing.html (T1 owns this)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_tier_gate_ui.py)
- Test overlay template renders when tier_locked=True
- Test overlay template does NOT render when tier_locked=False
- Test overlay has correct CTA href (/beta/join)
- Test CSS file exists and contains blur(8px)
- Test JS file exists and contains tier-locked-content class
- Test overlay has data-track analytics attributes
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read existing fragments/tier_gate_teaser.html (understand current pattern)
3. Create tier_gate_overlay.html
4. Create tier-gate.css
5. Create tier-gate.js
6. Log new component in docs/DESIGN_COMPONENT_LOG.md
7. Create tests, run tests + full suite
8. Commit, write scenarios + changelog
```

---

## Agent 4C Prompt — Onboarding Polish

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.

## YOUR TASK: Polish the 3-step onboarding wizard

The onboarding flow exists from QS10. It has 3 steps:
- Step 1: Role selector (homeowner/architect/expediter/contractor) — onboarding_step1.html
- Step 2: Add first watched property — onboarding_step2.html
- Step 3: Sample morning brief preview — onboarding_step3.html

These templates already extend head_obsidian.html (migrated). Polish them for a premium feel.

### Polish Requirements

**Step 1 — Welcome + Role**
- Progress indicator: 1/3 (visual dots or bar, not just text)
- Welcome message with user's name (from g.user)
- Role cards should feel clickable and selected state should be clear
- Ghost CTA: "Continue →"
- Skip option: "Skip setup →" (goes to dashboard with demo data)

**Step 2 — Add Property**
- Progress: 2/3
- Address input with placeholder "e.g., 487 Noe St"
- Demo parcel pre-filled as suggestion (not auto-selected)
- "This is where the magic happens" subtext
- Ghost CTA: "Find my property →"
- Skip: "Use demo property →" (uses 1455 Market St demo data)

**Step 3 — Intelligence Preview**
- Progress: 3/3
- Show a mini intelligence preview for their property (or demo property)
- Highlight: "This updates every night with new city data"
- Ghost CTA: "Go to dashboard →"
- Confetti or subtle celebration animation (CSS only, no library)

### Routes (web/routes_auth.py)

Read the existing onboarding routes (lines ~749-860 in routes_auth.py). Polish the logic:
- Ensure skip option works (redirects to dashboard)
- Ensure demo property fallback works
- Add flash message on completion: "Welcome to sfpermits.ai!"

### FILES YOU OWN
- MODIFY: web/templates/onboarding_step1.html
- MODIFY: web/templates/onboarding_step2.html
- MODIFY: web/templates/onboarding_step3.html
- MODIFY: web/routes_auth.py (onboarding routes only — do NOT touch login/signup routes)
- CREATE: tests/test_onboarding_polish.py

### FILES YOU MUST NOT TOUCH
- web/tier_gate.py, web/app.py (Agent 4A)
- web/templates/components/* (Agent 4B)
- web/routes_search.py, web/routes_public.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_onboarding_polish.py)
- Test step 1 renders with progress indicator
- Test step 1 has skip option
- Test step 2 has demo property suggestion
- Test step 3 has "Go to dashboard" CTA
- Test skip redirects to dashboard
- At least 8 tests.

### Steps
1. Read docs/DESIGN_TOKENS.md
2. Read onboarding_step1/2/3.html (current state)
3. Read web/routes_auth.py lines 749-860 (onboarding routes)
4. Polish all 3 step templates
5. Update routes_auth.py if needed
6. Create tests, run tests + full suite
7. Run design lint on all 3 templates
8. Commit, write scenarios + changelog
```

---

## Agent 4D Prompt — Gate Analytics + Email Templates

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to your worktree branch only.

## YOUR TASK: Add analytics tracking for tier gate + migrate email templates

Two tasks:

### Task 1: PostHog Analytics for Tier Gate Events

The tier gate system (Agent 4A) and overlay (Agent 4B) add data-track attributes to the
overlay HTML. But we also need server-side event tracking for:

1. **Gate impression** — when requires_tier(teaser=True) fires and user is below required tier
2. **Gate click-through** — when user clicks "Get access" (tracked by PostHog autocapture via data-track)
3. **Onboarding completion** — when user finishes step 3
4. **Onboarding skip** — when user clicks "Skip setup"

Add PostHog server-side tracking. The PostHog helper is in web/helpers.py:
```python
from web.helpers import posthog_track
# posthog_track(event_name, properties_dict, user_id)
```

Create a thin analytics helper file:

web/gate_analytics.py:
```python
"""Analytics events for tier gating and onboarding."""
from web.helpers import posthog_track

def track_gate_impression(user, required_tier, current_tier, page):
    posthog_track("tier_gate_impression", {
        "required_tier": required_tier,
        "current_tier": current_tier,
        "page": page,
    }, user_id=user.get("user_id") if user else None)

def track_onboarding_complete(user, role, property_address):
    posthog_track("onboarding_complete", {
        "role": role,
        "property_address": property_address,
    }, user_id=user.get("user_id"))

def track_onboarding_skip(user, step):
    posthog_track("onboarding_skip", {
        "step": step,
    }, user_id=user.get("user_id"))
```

### Task 2: Email Template Token Migration

Migrate these email templates to use consistent branding (not full Obsidian — emails have
different CSS constraints):

1. **web/templates/brief_email.html** — Morning brief email
2. **web/templates/report_email.html** — Property report email
3. **web/templates/notification_email.html** — Notification email
4. **web/templates/invite_email.html** — Invite email

For email templates:
- Replace any hardcoded hex colors with inline styles using the brand palette
  (emails can't use CSS custom properties — use the actual hex values from DESIGN_TOKENS.md)
- Ensure consistent header/footer branding
- Add "sfpermits.ai" wordmark in header
- Keep email-safe HTML (tables, inline styles, no CSS grid/flexbox)

### FILES YOU OWN
- CREATE: web/gate_analytics.py
- MODIFY: web/templates/brief_email.html
- MODIFY: web/templates/report_email.html
- MODIFY: web/templates/notification_email.html
- MODIFY: web/templates/invite_email.html
- CREATE: tests/test_gate_analytics.py

### FILES YOU MUST NOT TOUCH
- web/tier_gate.py (Agent 4A)
- web/app.py (Agent 4A)
- web/routes_auth.py (Agent 4C)
- web/templates/components/* (Agent 4B)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_gate_analytics.py)
- Test track_gate_impression calls posthog_track with correct event name
- Test track_onboarding_complete includes role and address
- Test track_onboarding_skip includes step number
- Test each email template renders without error
- Test email templates contain brand header
- At least 8 tests.

### Steps
1. Create web/gate_analytics.py
2. Read web/helpers.py — understand posthog_track signature
3. Create tests/test_gate_analytics.py
4. Read each email template
5. Migrate email templates (consistent branding)
6. Run tests + full suite
7. Commit, write scenarios + changelog
```

---

## Post-Agent Merge Ceremony

After ALL 4 agents complete:

```bash
# Step 0: ESCAPE CWD
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

# Step 1: Pull latest main (T1, T2, T3 should have merged)
git checkout main && git pull origin main

# Step 2: Merge all agents (no dependency between them)
git merge <4A-branch> --no-ff -m "feat(tier-gate): teaser mode with blur overlay backend"
git merge <4B-branch> --no-ff -m "feat(tier-gate): blur overlay UI — 8px blur + CTA"
git merge <4C-branch> --no-ff -m "feat(onboarding): polish 3-step wizard"
git merge <4D-branch> --no-ff -m "feat(analytics): gate events + email template migration"

# Step 3: Quick test
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short -x

# Step 4: Verify tier gate works end-to-end
python -c "
from web.tier_gate import requires_tier, has_tier
# Test teaser mode
import types
fn = lambda: None
fn.__name__ = 'test'
fn.__module__ = '__main__'
decorated = requires_tier('beta', teaser=True)(fn)
print('Tier gate teaser mode: OK')
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
Write `qa-drop/qs11-t4-session.md` with:
- Agent results table (4 agents)
- Tier gate teaser mode status
- Onboarding polish status
- Analytics events status
- Email migration status

### Step 3: CAPTURE
- Concatenate scenario files → `scenarios-t4-sprint93.md`
- Concatenate changelog files → `CHANGELOG-t4-sprint93.md`

### Step 4: HYGIENE CHECK
```bash
python scripts/test_hygiene.py --changed --quiet 2>/dev/null || echo "No test_hygiene.py"
```

### Step 5: SIGNAL DONE
```
═══════════════════════════════════════════════════
  CHECKQUAD T4 COMPLETE — Tier Gating + Onboarding
  Sprint 93 · 4 agents · X/4 PASS
  Tier gate teaser: DONE · Onboarding: POLISHED
  Pushed: <commit hash>
  Session: qa-drop/qs11-t4-session.md
═══════════════════════════════════════════════════
```

Do NOT run `git worktree remove` or `git worktree prune`. T0 handles cleanup.
