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
