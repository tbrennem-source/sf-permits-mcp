# CHANGELOG — Sprint 97 T4 (mobile UX fixes + guided demo + notifications)

## [Sprint 97] — 2026-02-28

### Agent 4A: Mobile Critical Fixes

#### Fixed

##### Mobile Touch Target: Ghost CTAs (obsidian.css)
- `.ghost-cta` padding changed from `padding-bottom: 1px` to `padding: 8px 0`
- Touch target height rises from ~19px to ~35px, meeting Apple HIG 32px minimum
- Applies site-wide to all ghost CTAs (load-more, property report links, search CTAs)
- Desktop layout unaffected — inline-block padding collapses vertically in flow context

##### Mobile Touch Target: MCP Demo Carousel Dots (mcp-demo.css)
- `.mcp-demo-dot` dimensions: 8px × 8px → 12px × 12px
- Added `padding: 10px` + `box-sizing: content-box`
- Combined touch target: 12px + 2×10px = 32px (meets Apple HIG minimum)
- Visual dot size is 12px × 12px (unchanged from user perspective — padding is invisible)

##### Mobile Navigation: Landing Page (landing.html)
- Added `.mobile-nav` fixed bar at top of viewport, scoped to `@media (max-width: 480px)`
- Height: 52px — all links span full bar height for ≥44px touch targets (Apple HIG ideal)
- Links: /search, /demo, /methodology, /auth/login
- Hidden on desktop (≥481px) via separate media query
- Background: `color-mix(in srgb, var(--obsidian) 92%, transparent)` with `backdrop-filter: blur`
- Body padding-top and hero min-height adjusted to avoid nav overlap

#### Added
- `tests/test_mobile_fixes.py` — 16 tests across 3 test classes
- `DESIGN_COMPONENT_LOG.md`: logged `.mobile-nav` as new component with full HTML/CSS spec

---

### Agent 4C: /demo/guided Self-Guided Demo Page

#### Added
- `GET /demo/guided` — new public route registered on `misc` Blueprint (`web/routes_misc.py`)
- `web/templates/demo_guided.html` — 6-section self-guided stakeholder walkthrough page using full Obsidian design token system
  - Section 1: Hero ("See what sfpermits.ai does")
  - Section 2: Gantt / station tracker explanation with link to `/tools/station-predictor`
  - Section 3: Pre-filled search block (`/search?q=487+Noe+St`)
  - Section 4: 4 intelligence tool cards (stuck-permit, what-if, revision-risk, cost-of-delay) with demo query params
  - Section 5: Amy professional workflow bullets (morning triage, reviewer lookup, intervention playbooks)
  - Section 6: MCP/AI connect block with Learn more link to `/methodology`
- `tests/test_demo_guided.py` — 20 passing tests covering all 6 sections, tool link params, auth behavior, template base
- Design Token Compliance: 5/5 — clean (zero violations per `design_lint.py`)

---

# CHANGELOG — T4 Sprint 97 (Agent 4D)

## Differentiated Notification Sounds for CC Workflow Events

**Branch:** worktree-agent-aebcb9f4
**Commit:** 61e2d94

### What was built

#### scripts/notify.sh (new, executable)
Bash script for differentiated audio notifications. Maps workflow events to distinct macOS system sounds:
- `agent-done` → Tink (light, brief — individual agent signal)
- `terminal-done` → Glass (clear, ringing — T1-T4 completion)
- `sprint-done` → Hero (triumphant — full sprint done)
- `qa-fail` → Basso (deep, attention-getting)
- `prod-promoted` → Funk (celebratory)
- fallback → Pop (neutral)

Fires `afplay` in background, then `osascript` for macOS notification center. Respects `NOTIFY_ENABLED=0` env var for silent/CI environments. Early-exit guard placed before case statement.

#### .claude/hooks/notify-events.sh (new, executable)
PostToolUse hook (Write + Bash) with three detection rules:
1. Write to `qa-results/` containing "FAIL" → `qa-fail` sound
2. Write containing "CHECKQUAD" AND "COMPLETE" → `terminal-done` sound
3. Bash command containing `git push origin prod` → `prod-promoted` sound

Hook is non-blocking (always exits 0). Audio fires in background subshell. Resolves REPO_ROOT from hook file path so it works from any CWD.

#### .claude/settings.json (modified)
Added `notify-events.sh` to PostToolUse hooks for both `Write` and `Bash` matchers. Existing Write hooks (detect-descope.sh, test-hygiene-hook.sh) preserved and ordered first.

#### CLAUDE.md (appended — section 14)
Documents the notification system: sound map table, CLI usage examples, hook detection logic, how to add new event types, list of available macOS system sounds, and NOTIFY_ENABLED disable pattern.

#### tests/test_notify.py (new)
13 tests covering:
- File existence and executability
- All 5 named event types (agent-done, terminal-done, sprint-done, qa-fail, prod-promoted)
- Default fallback case presence
- NOTIFY_ENABLED check presence and correct comparison value
- Disabled early-exit behavior via subprocess
- afplay and osascript presence
- Sound distinctness (≥5 unique sound files)

All 13 tests pass.

### Files touched
| File | Action |
|------|--------|
| `scripts/notify.sh` | CREATE |
| `.claude/hooks/notify-events.sh` | CREATE |
| `.claude/settings.json` | MODIFY |
| `CLAUDE.md` | APPEND (section 14) |
| `tests/test_notify.py` | CREATE |

### Files NOT touched (per ownership matrix)
- `web/templates/*`, `web/static/*`, `web/routes_*.py` — not in scope
- Existing hooks: stop-checkchat.sh, block-playwright.sh, plan-accountability.sh, detect-descope.sh, test-hygiene-hook.sh

---

# CHANGELOG — T4 Sprint 97 (Agent 4B)

## Agent 4B: Minor UX Fixes

### Fixed

- **`web/templates/demo.html`** — Mobile overflow fix: `.callout` elements (annotation chips) now use `display: block; max-width: 100%; box-sizing: border-box` inside `@media (max-width: 480px)`. Previously the `inline-block` default caused ~300px horizontal overflow on 375px phones.

### Verified (no changes needed)

- **`web/templates/landing.html`** — Stats counter: `data-target="1137816"` was already correct (1,137,816 SF building permits).
- **`web/templates/landing.html`** — State machine navigation: All watched-property `href` values in `beta` and `returning` states already navigate to `/search?q=...` or `/portfolio` — none use `href="/"`.

### Tests Added

- **`tests/test_minor_fixes.py`** — 5 tests:
  1. `/demo` route returns HTTP 200
  2. demo.html renders `.callout` elements
  3. demo.html `@media (max-width: 480px)` block contains `.callout` with `display:block`, `max-width:100%`, `box-sizing:border-box`
  4. landing.html stats counter `data-target` equals 1137816
  5. landing.html state machine watched-property links do not route to `"/"`