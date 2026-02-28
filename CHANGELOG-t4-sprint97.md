# CHANGELOG — Sprint 97 Agent 4A (mobile UX fixes)

## [Sprint 97] — 2026-02-28

### Fixed

#### Mobile Touch Target: Ghost CTAs (obsidian.css)
- `.ghost-cta` padding changed from `padding-bottom: 1px` to `padding: 8px 0`
- Touch target height rises from ~19px to ~35px, meeting Apple HIG 32px minimum
- Applies site-wide to all ghost CTAs (load-more, property report links, search CTAs)
- Desktop layout unaffected — inline-block padding collapses vertically in flow context

#### Mobile Touch Target: MCP Demo Carousel Dots (mcp-demo.css)
- `.mcp-demo-dot` dimensions: 8px × 8px → 12px × 12px
- Added `padding: 10px` + `box-sizing: content-box`
- Combined touch target: 12px + 2×10px = 32px (meets Apple HIG minimum)
- Visual dot size is 12px × 12px (unchanged from user perspective — padding is invisible)

#### Mobile Navigation: Landing Page (landing.html)
- Added `.mobile-nav` fixed bar at top of viewport, scoped to `@media (max-width: 480px)`
- Height: 52px — all links span full bar height for ≥44px touch targets (Apple HIG ideal)
- Links: /search, /demo, /methodology, /auth/login
- Hidden on desktop (≥481px) via separate media query
- Background: `color-mix(in srgb, var(--obsidian) 92%, transparent)` with `backdrop-filter: blur`
- Body padding-top and hero min-height adjusted to avoid nav overlap

### Added
- `tests/test_mobile_fixes.py` — 16 tests across 3 test classes
  - `TestGhostCtaPadding` (4 tests): verifies block exists, has padding, padding ≥8px, is inline-block
  - `TestMcpDemoDots` (6 tests): width ≥12px, height ≥12px, has padding, padding ≥10px, content-box
  - `TestLandingMobileNav` (6 tests): element present, /search link, /demo link, /auth/login link, 480px media query, ≥44px height
- `DESIGN_COMPONENT_LOG.md`: logged `.mobile-nav` as new component with full HTML/CSS spec
