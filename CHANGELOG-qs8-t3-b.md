# CHANGELOG — QS8 T3-B: Search NLP Parser + Empty Result Guidance + Result Ranking

## [QS8-T3-B] 2026-02-27

### Added

**B-1: Natural language query parser (`web/helpers.py`)**

- New `parse_search_query(q: str) -> dict` function
- Extracts structured fields from free-text search queries using regex + keyword matching (no ML)
- Supported extractions:
  - `neighborhood`: matches 60+ SF neighborhood aliases (SoMa, Mission, Haight, etc.) with preposition phrase detection ("in the Mission", "near SoMa")
  - `street_number` + `street_name`: handles alpha streets ("Market St") and numbered streets ("6th Ave", "16th St")
  - `permit_type`: 30+ keyword phrases mapped to canonical types (new construction, alterations, adu, seismic, etc.)
  - `date_from`: year 2018-2030 extracted and mapped to ISO date string (e.g. "2024" → "2024-01-01")
  - `description_search`: residual unmatched text after all extractions
- Year extracted BEFORE address to prevent years like "2022" from being mistaken for street numbers
- Neighborhood aliases matched longest-first to avoid false partial matches

**B-2: Empty result guidance (`web/helpers.py`)**

- New `build_empty_result_guidance(q: str, parsed: dict) -> dict` function
- Returns context-aware suggestions when a search produces 0 results:
  - Query-specific suggestions based on what the NLP parser found (neighborhood, permit type)
  - `did_you_mean` hint when text looks like a street name missing a house number
  - Always includes `show_demo_link: True` pointing to `/demo`
- Template updated (`web/templates/search_results_public.html`) to render:
  - "Did you mean?" callout above the main guidance card
  - Contextual suggestions section inside guidance card
  - Link to `/demo` as "Not sure what to search?" CTA

**B-3: Result ranking (`web/helpers.py`)**

- New `rank_search_results(results, query, parsed) -> list` function
- Priority ranking:
  - Score 100: Exact address match (street_number + street_name match parsed query)
  - Score 90: Permit number found in query string
  - Score 50: Description keyword overlap with `description_search`
- Each result gets a `match_badge` key: `"Address Match"`, `"Permit"`, or `"Description"`
- Internal `_rank_score` removed from output before returning

**Route integration**

- `web/routes_public.py`: `public_search` now calls `parse_search_query` and passes `empty_guidance` + `parsed_query` to template; uses NLP-extracted address when intent router misses it
- `web/routes_search.py`: `/ask` handler calls `parse_search_query` to upgrade "general_question" or "analyze_project" intents to "search_address" when NLP finds an address embedded in the query; merges neighborhood into analyze entities

### Tests

- `tests/test_sprint_81_2.py`: 44 tests covering:
  - Neighborhood extraction (6 cases including aliases, preposition phrases)
  - Address extraction (5 cases including numbered streets, prepositional phrases)
  - Permit type extraction (6 cases)
  - Year extraction (6 cases including range boundary and conflict with address parser)
  - Combined multi-field queries (7 cases)
  - Empty result guidance (5 cases)
  - Result ranking (7 cases including badge assignment, ordering, internal key cleanup)

### Files Modified

| File | Change |
|------|--------|
| `web/helpers.py` | +`parse_search_query`, `rank_search_results`, `build_empty_result_guidance`; +`import re`; ~350 lines added |
| `web/routes_public.py` | Import new helpers, integrate NLP parser into `public_search`, pass `empty_guidance` to template |
| `web/routes_search.py` | Import new helpers, add NLP enhancement block in `/ask` handler |
| `web/templates/search_results_public.html` | Add `did_you_mean`, contextual suggestions, and demo link to no-results block |
| `tests/test_sprint_81_2.py` | New — 44 tests (all passing) |
