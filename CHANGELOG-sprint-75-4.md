# CHANGELOG — Sprint 75-4 (Demo Enhancement + PWA Polish)

## Sprint 75-4 — Agent 4 Deliverables

### Features Added

#### Demo Severity Integration (Task 75-4-1, 75-4-2, 75-4-3)
- `web/routes_misc.py` `_get_demo_data()`: queries `parcel_summary` for demo parcel (block 3507, lot 004) to pull real neighborhood, permit counts, complaint counts, violation counts, and health_tier when available — with hardcoded fallbacks when DB is unavailable or table is empty
- Integrated `src.severity.score_permit` into `_get_demo_data()`: all active permits (status in `issued`, `filed`, `approved`) are scored; highest score drives overall `severity_tier` and `severity_score` context vars; each permit dict gets its own `severity_tier` and `severity_score`
- `web/templates/demo.html`: added severity badge CSS (`.severity-pill`, `.severity-CRITICAL`, `.severity-HIGH`, `.severity-MEDIUM`, `.severity-LOW`, `.severity-GREEN`) using design-spec.md tokens (`--signal-red`, `--signal-amber`, `--signal-green`, `--signal-blue`)
- Hero section displays overall severity banner when `severity_tier` is present
- Permit table has a new "Severity" column showing per-permit tier badges for active permits; inactive permits show `—`

#### Cache TTL Fix (Task 75-4-4)
- Changed `_get_demo_data()` cache TTL from 3600s (1 hour) to 900s (15 minutes) via `_DEMO_CACHE_TTL = 900` constant
- TTL check now references `_DEMO_CACHE_TTL` instead of inline magic number

#### PWA Manifest Polish (Task 75-4-5)
- `web/static/manifest.json`: added `"purpose": "any maskable"` to both icon entries (192x192 and 512x512)
- Added `"orientation": "portrait-primary"`, `"lang": "en"`, `"scope": "/"` for full PWA spec compliance
- All required PWA fields verified: `name`, `short_name`, `description`, `start_url`, `display`, `background_color`, `theme_color`, `icons`

#### Sitemap Update (Task 75-4-6)
- `web/routes_misc.py` `sitemap()`: added `/demo` to `static_pages` list

### Tests Added
- `tests/test_sprint_75_4.py` — 24 tests covering:
  - Sitemap includes `/demo`
  - `/demo` returns 200, contains demo address, severity CSS classes
  - `_get_demo_data()` returns all required keys, correct block/lot, timeline fallback
  - Cache TTL constant is 900 seconds
  - Cache hit logic within TTL
  - `score_permit` import and output validation
  - `manifest.json` valid JSON, all required PWA fields, `maskable` + `any` in purpose
  - Theme/background color values

### Scope Changes
- None. All 6 tasks delivered as specified.

### Known Pre-existing Issues
- `tests/test_permit_lookup.py::test_permit_lookup_address_suggestions` fails on main before this sprint. Not caused by Sprint 75-4 changes.
