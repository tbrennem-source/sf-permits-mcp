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
