# QA Script — Sprint 77-3: Search + Entity Scenarios

**Session:** Sprint 77-3 (Agent 77-3)
**Date:** 2026-02-26
**Feature:** E2E Playwright tests for search, permit lookup, plan analysis upload, methodology page

## Setup

No extra setup needed. Tests run against a local Flask dev server (auto-started by conftest.py).

```bash
source .venv/bin/activate
TESTING=1 TEST_LOGIN_SECRET=e2e-test-secret-local pytest tests/e2e/test_search_scenarios.py -v
```

## Test Checklist

### 1. Address Search Returns Results (77-3-1)

**Run:** `pytest tests/e2e/test_search_scenarios.py::TestAddressSearchReturnsResults -v`

- [ ] `test_address_search_returns_results` — Login as expediter, search "valencia", assert page has permit/search/result content
  - PASS: Body contains at least one of: "permit", "result", "valencia", "search", "lookup"
  - FAIL: Body is blank or contains none of the expected keywords

- [ ] `test_address_search_result_count_visible` — Search "market st", assert page has >200 chars of content
  - PASS: Body length > 200 characters
  - FAIL: Response is effectively empty

### 2. Permit Number Search (77-3-2)

**Run:** `pytest tests/e2e/test_search_scenarios.py::TestPermitNumberSearch -v`

- [ ] `test_permit_number_search_shows_detail` — Search "202101234567", assert no server error, assert meaningful response
  - PASS: No "internal server error" or "traceback" in body; at least one of "permit", "no result", "not found", "search", "lookup", "202101234567" present
  - FAIL: Server error shown OR no recognizable content

- [ ] `test_permit_lookup_form_present_on_index` — Authenticated index has a search input
  - PASS: `input[name="q"]` or similar search input found
  - FAIL: No search input on authenticated dashboard

### 3. Empty Search Handled Gracefully (77-3-3)

**Run:** `pytest tests/e2e/test_search_scenarios.py::TestEmptySearchHandledGracefully -v`

- [ ] `test_empty_search_redirects_or_shows_guidance` — Empty search returns 200 or redirect, shows content
  - PASS: HTTP 200/302, no "internal server error", body >50 chars
  - FAIL: Server error or blank page

- [ ] `test_anonymous_empty_search_redirects` — Anonymous empty search returns 200 or redirect
  - PASS: HTTP 200 or 302
  - FAIL: Server error

- [ ] `test_whitespace_only_search_handled` — Whitespace-only query does not crash
  - PASS: No "internal server error" or "traceback"
  - FAIL: Server error

### 4. Plan Analysis Upload Form (77-3-4)

**Run:** `pytest tests/e2e/test_search_scenarios.py::TestPlanAnalysisUploadForm -v`

- [ ] `test_plan_analysis_upload_input_exists` — Authenticated index has `input[type="file"]`
  - PASS: File input found
  - FAIL: No file input on page

- [ ] `test_plan_analysis_file_input_accepts_pdf` — File input has `accept=".pdf"`
  - PASS: `input[type="file"][accept*=".pdf"]` found
  - FAIL: File input does not restrict to PDF

- [ ] `test_plan_analysis_section_visible` — Page mentions "plan", "analyze", "analysis", or "upload"
  - PASS: At least one keyword present
  - FAIL: No plan analysis content found

### 5. Methodology Page Full Content (77-3-5)

**Run:** `pytest tests/e2e/test_search_scenarios.py::TestMethodologyPageFullContent -v`

- [ ] `test_methodology_page_is_substantive` — Page has 3+ headings, mentions methodology content
  - PASS: `h2, h3` count >= 3; body mentions "methodology" or "how"
  - FAIL: Fewer than 3 headings (stub page)

- [ ] `test_methodology_page_has_data_sources_section` — Mentions data/source/permit/soda/api/dataset
  - PASS: At least one keyword present
  - FAIL: No data source content

- [ ] `test_methodology_page_has_entity_or_search_section` — Mentions entity/search/network/resolution
  - PASS: At least one keyword present
  - FAIL: No entity or search methodology content

- [ ] `test_methodology_page_accessible_without_login` — Returns HTTP 200 for anonymous users
  - PASS: HTTP 200
  - FAIL: Redirect to login (401/302) or error

- [ ] `test_methodology_page_has_plan_analysis_section` — Mentions plan/vision/analysis/ai/check
  - PASS: At least one keyword present
  - FAIL: No plan analysis content

## Expected Result

All 15 tests: PASS
Screenshots in: `qa-results/screenshots/e2e/`
