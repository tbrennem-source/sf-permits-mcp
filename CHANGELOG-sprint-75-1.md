# CHANGELOG — Sprint 75-1: Dashboard + Nav Redesign

## Sprint 75-1 (Agent 1) — Dashboard + Nav Obsidian Redesign

### New Features

**nav.html — Obsidian sticky navigation (Task 75-1-1, 75-1-2)**
- Replaced old badge-row header with sticky Obsidian nav using `backdrop-filter: blur(12px)`
- Desktop: `obs-nav` class with `obs-nav-logo` (left), `obs-nav-items` (center), `obs-nav-right` (right)
- Max 5 visible desktop badges: Search, Brief, Portfolio, Projects, + "More" dropdown
- "More" dropdown contains: My Analyses, Permit Prep, Consultants, Bottlenecks
- Admin gear dropdown preserved
- Account + Logout right-aligned
- Mobile: hamburger button replaces badge row (hidden via `@media (max-width: 768px)`)
- Mobile slide-down panel with all nav items stacked (48px min-height per item)
- Hamburger animates to X when open (CSS transform on spans)
- Close on tap-outside via document click listener
- All design tokens used: `--bg-elevated`, `--text-secondary`, `--signal-cyan`, etc.
- Loading animation: `nav-badge-loading` keyframe on badge click

**index.html — Obsidian dashboard layout (Tasks 75-1-3 through 75-1-7)**
- Replaced `<div class="container">` with `<div class="obs-container dash-main">`
- Search area: wrapped in `.glass-card.dash-search-card` with `var(--space-8)` padding
- Heading upgraded to `.dash-search-heading` with `clamp()` fluid size and `cyan` accent span
- Search input: now uses `.obsidian-input` class
- Go button: now uses `.obsidian-btn.obsidian-btn-primary`
- Quick Actions: new `.glass-card.dash-actions-card` section below search with 5 `.obsidian-btn-outline` buttons
  - "Analyze a project", "Look up a permit", "Upload plans", "Draft a reply"
  - Optional personalized "Check [address]" if user has primary address set
  - Mobile: 2-column grid at 768px, single column at 375px
- Recent Items: new `.glass-card.dash-recent-card` with `.dash-recent-grid` (3-col → 2-col → 1-col)
  - Chips rendered from localStorage as `.recent-chip` cards with address + "Recent search" label
  - Empty state: muted placeholder text
  - JS updated: `_renderRecentSearches()` now populates both old inline bar AND new grid
- Watched Properties: glassmorphism card with property report link (if set) or empty state CTA
- Quick Stats: `.glass-card.dash-stats-card` with 4 `.stat-block` components (2-col → 4-col grid)
  - Permits Watched, Changes This Week, 1.1M+ Permits Indexed, 30 Tools
- Footer: updated to use `obs-container` for centering
- All content wrapped in `obs-container` (Task 75-1-7)

**design-system.css — minor update**
- Added comment section for Sprint 75-1 nav token placeholder

**tests/test_sprint_75_1.py — New test file (Task 75-1-8)**
- 22 tests covering: nav structure, hamburger, badge count, media query, design tokens, obs-container, glass-card, quick actions, obsidian-input, heading class, landing page 200, auth dashboard 200, CSS obs-container max-width validation, mobile panel, hamburger spans

### Scope Notes
- landing.html: confirmed NOT modified (has its own inline header, not nav.html)
- All tool sections (section-analyze, section-analyze-plans, section-lookup) preserved inside obs-container
- Existing HTMX functionality fully preserved

### Test Results
- Sprint 75-1 tests: 22/22 PASS
- Full suite (excluding pre-existing failures): no new failures introduced
- Pre-existing failure: `test_permit_lookup_address_suggestions` — unrelated to this sprint
