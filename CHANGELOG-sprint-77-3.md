# CHANGELOG — Sprint 77-3 (Search + Entity Scenarios)

## [Sprint 77-3] — 2026-02-26

### Added
- `tests/e2e/test_search_scenarios.py` — 15 new Playwright E2E tests covering:
  - **Address search** (TestAddressSearchReturnsResults): authenticated address search returns permit results; search result page has substantial content
  - **Permit number search** (TestPermitNumberSearch): permit number lookup returns meaningful response without server errors; authenticated index has a search form
  - **Empty search handling** (TestEmptySearchHandledGracefully): empty, whitespace-only, and anonymous empty searches handled gracefully without crashes
  - **Plan analysis upload form** (TestPlanAnalysisUploadForm): file upload input present, accepts only PDFs, plan analysis section visible on authenticated index
  - **Methodology page content** (TestMethodologyPageFullContent): substantive content with 3+ headings, mentions data sources, entity resolution, plan analysis; accessible without login

### Test Coverage
- 15 tests collected, 15 passing
- Covers scenarios: 77-3-1 through 77-3-5 as specified in Sprint 77-3 prompt
- All tests use `auth_page` fixture with `expediter`, `homeowner`, and `architect` personas
- Screenshots captured to `qa-results/screenshots/e2e/`

### Files Changed
- `tests/e2e/test_search_scenarios.py` — NEW (test only, no production files modified)
