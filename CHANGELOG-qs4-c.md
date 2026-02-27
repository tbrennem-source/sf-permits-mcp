# CHANGELOG — QS4-C Obsidian Design Migration

## 2026-02-26 — QS4-C: Obsidian Design Migration

### Added
- `web/templates/fragments/head_obsidian.html` — shared head fragment for all Obsidian-migrated pages
  - Google Fonts (IBM Plex Sans + JetBrains Mono) with preconnect hints
  - PWA meta tags (manifest, theme-color, apple-mobile-web-app)
  - design-system.css, style.css, mobile.css links
  - Legacy CSS variable aliases for nav.html backward compatibility
- `tests/test_qs4_c_design.py` — 27 tests covering fragment, index, and brief migration

### Changed
- `web/templates/index.html` — migrated to Obsidian design system
  - Replaced inline `:root` CSS variables with shared fragment include
  - Added `body.obsidian` class for design-system.css scoping
  - Applied `var(--font-display)` to headings, labels, tabs, section titles
  - Applied `var(--card-shadow)` and `var(--card-radius)` to cards
  - Removed duplicate header/badge/logo CSS (provided by nav.html fragment)
  - Removed duplicate mobile.css link (now in shared fragment)
- `web/templates/brief.html` — migrated to Obsidian design system
  - Same shared fragment include pattern as index.html
  - Applied `var(--font-display)` to h1, summary labels, section h2, health status badges
  - Applied Obsidian card patterns to summary cards, sections, property cards
  - Signal colors (green/amber/red) resolve via legacy aliases to Obsidian tokens
- `tests/test_qs3_d_analytics.py` — updated raw-file assertions to check shared fragment

### QA Results
- 12/12 Playwright checks PASS
- Visual review average: 4.0/5
- 3 scenarios proposed
