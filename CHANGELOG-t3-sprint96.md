# QS12 T3 Sprint Changelog

## Agent 3A: Tool Page Public Access
- Removed auth redirect (`if not g.user: return redirect("/auth/login")`) from 4 routes in `web/routes_search.py`: `/tools/station-predictor`, `/tools/stuck-permit`, `/tools/what-if`, `/tools/cost-of-delay`
- Added anonymous soft CTA to 4 tool templates (`station_predictor.html`, `stuck_permit.html`, `what_if.html`, `cost_of_delay.html`) — gated with `{% if not g.user %}`, links to `/beta/join`, uses design token classes (`ghost-cta`, `--obsidian-mid`, `--glass-border`, `--text-tertiary`)
- Updated 9 existing tests across 4 test files that asserted 301/302 redirects for anonymous users — changed to assert 200 (`test_station_predictor_ui.py`, `test_stuck_permit_ui.py`, `test_what_if_ui.py`, `test_cost_of_delay_ui.py`, `test_tools_polish_a.py`, `test_tools_polish_b.py`)
- Created `tests/test_tool_public_access.py` with 24 tests covering: 6 routes × 200 for anonymous users, no redirect assertions, content rendering, soft CTA presence, anon gating, and authed user regression
- Design lint: 5/5 (zero violations across 4 changed templates)

# Changelog — T3 Agent 3B — Sprint QS12 / Sprint 96

## Feature: Triage Intelligence Signals on Search Result Cards

### Summary
Added per-permit triage intelligence panels to all three search result templates.
Each panel shows a colored station badge (days at current plan review station),
reviewer name (from most recent plan review assignment), and a "Stuck" indicator
when a permit has been waiting more than 2x the station median.

### Files Changed

**web/helpers.py**
- Added `_STATION_MEDIANS` dict with hardcoded p50 baselines per station:
  BLDG=30d, SFFD-HQ=45d, CP-ZOC=60d, MECH-E=25d, ELEC=25d, default=30d
- Added `_STATION_MEDIAN_DEFAULT = 30.0`
- Added `_get_station_median_db(conn, station, backend)` — queries
  `station_velocity_v2` for live medians; falls back to hardcoded defaults
- Added `classify_days_threshold(days, median)` — returns 'green', 'amber', or 'red'
  (green: days < median; amber: median <= days < 2*median; red: days >= 2*median)
- Added `compute_triage_signals(street_number, street_name, block, lot,
  permit_number, max_permits)` — queries permits + addenda to build
  per-permit triage signal dicts; returns [] on any error (graceful degradation)

**web/routes_public.py**
- Added `compute_triage_signals` to imports from `web.helpers`
- Added triage signals computation block in `public_search()` route:
  calls `compute_triage_signals()` with resolved address/block/lot;
  wrapped in try/except to ensure page never fails due to triage errors;
  passes `triage_signals` list to `render_template()`

**web/templates/search_results_public.html**
- Added `--dot-green`, `--dot-amber`, `--dot-red` CSS custom properties
  (were missing from this template's `:root` block)
- Added triage panel CSS: `.triage-panel`, `.triage-heading`, `.triage-cards`,
  `.triage-card`, `.station-badge` (with `--green/amber/red` modifiers),
  `.stuck-indicator`, `.triage-reviewer`
- Added triage panel HTML block rendered when `triage_signals` is non-empty;
  shows per-permit card with station badge, stuck indicator (if applicable),
  and reviewer name (if available)

**web/templates/search_results.html** (authenticated search)
- Added `{% set triage_signals = triage_signals if triage_signals is defined else [] %}` default
- Added `.triage-section` CSS for the authenticated search card layout
- Added triage signals section before `{{ result_html | safe }}`

**web/templates/results.html** (permit detail / HTMX result)
- Added `{% set triage_signals = triage_signals if triage_signals is defined else [] %}` default
- Added `.triage-signals-bar` CSS for compact inline bar format
- Added triage signals bar before the methodology toggle

### Tests Added

**tests/test_search_intelligence.py** (NEW — 22 tests)
- `test_classify_days_green_under_median` — days < median = green
- `test_classify_days_amber_at_1x_median` — days == median = amber
- `test_classify_days_amber_at_1_5x_median` — days == 1.5x median = amber
- `test_classify_days_red_at_2x_median` — days == 2x median = red
- `test_classify_days_red_above_2x_median` — days > 2x median = red
- `test_classify_days_green_just_under_median` — days == median - 1 = green
- `test_classify_days_amber_just_under_2x` — days == 2*median - 1 = amber
- `test_is_stuck_flag_at_2x_median` — is_stuck True at 2x
- `test_is_stuck_flag_false_below_2x_median` — is_stuck False below 2x
- `test_compute_triage_signals_returns_empty_without_inputs` — no args = []
- `test_compute_triage_signals_graceful_on_db_error` — DB error = []
- `test_compute_triage_signals_no_station_data` — no station = None fields
- `test_compute_triage_signals_with_station_data` — active station = timing data
- `test_compute_triage_signals_stuck_permit` — 75d at BLDG = red + is_stuck
- `test_compute_triage_signals_missing_reviewer_omitted` — no reviewer = None
- `test_search_results_public_template_has_triage_classes` — template audit
- `test_results_template_has_triage_classes` — results.html audit
- `test_search_results_auth_template_has_triage_classes` — search_results.html audit
- `test_public_search_renders_without_error` — route smoke test
- `test_public_search_triage_signals_empty_on_no_results` — no results path
- `test_station_median_default_fallback` — unknown station → 30d
- `test_station_median_known_stations` — BLDG/SFFD-HQ/CP-ZOC/MECH-E/ELEC medians

All 22 tests passing in 0.59s.

### Design Compliance
- Used `--dot-green`, `--dot-amber`, `--dot-red` for status dots (not `--signal-*`)
- Used `--mono` for data values (days, permit numbers, reviewer names)
- Used `--sans` for descriptive text labels
- Used `--text-secondary` for reviewer name display
- New components: `station-badge`, `triage-panel`, `triage-signals-bar`
  logged to `docs/DESIGN_COMPONENT_LOG.md`

## Agent 3C: Search Routing + Landing UX Fixes

### Search Routing — Intent Router (Job 1)
- Added `question` intent to `src/tools/intent_router.py` (priority 4.3, after validate_plans and address)
- Two detection paths:
  - `QUESTION_PHRASE_RE`: specific permit-question phrases ("need a permit", "permits required", "what permits do I need for…") — fires without context guard
  - `QUESTION_PREFIX_RE`: question-word prefixes ("do I", "can I", "how long", "should I", etc.) — requires at least one construction/permit context word (permit, remodel, kitchen, bathroom, etc.) to prevent over-classifying generic questions
- Guard: `has_draft_signal` prevents draft-style queries from being intercepted
- Priority ordering: validate_plans (3.5) > address (4) > question (4.3) > draft_fallback (4.5)
- Updated `web/routes_public.py` `/search` route: `question` intent now returns AI consultation guidance page without running a failed `permit_lookup()` call
- Updated `web/routes_search.py` `/ask` route: `question` intent maps to `general_question` for handler routing
- `nl_query` flag extended to include `question` intent (shows "How to use sfpermits.ai" guidance)

### Landing UX Fixes (Job 2)
- `web/templates/landing.html` — BETA badge text changed from `"beta"` to `"Beta Tester"` (id="beta-badge")
- `web/templates/landing.html` — `.scroll-cue` animation changed from `fadeIn` (ends at opacity 1.0) to `fadeInCue` (ends at opacity 0.6); added `@keyframes fadeInCue` definition
- `web/templates/landing.html` — Beta state watched property links: `/search?q=487+Noe+St` → `/?q=487+Noe+St` (prevents authenticated user loop through public search)
- `web/templates/landing.html` — Returning state watched property links: `/search?q=487+Noe+St` and `/search?q=225+Bush+St` → `/?q=487+Noe+St` and `/?q=225+Bush+St`
- Duplicate "do I need a permit?" link check: no duplicate instances found in actual HTML (task #3 condition not met)

### Tests
- Created `tests/test_search_routing_questions.py` — 19 tests covering question prefix patterns, question phrase patterns, and non-question query preservation
- Created `tests/test_landing_ux_fixes.py` — 10 tests covering beta badge text, scroll-cue opacity, and property click target paths
- Total: 29 new tests, all passing
- Full suite: 4462 passed, 0 failed
