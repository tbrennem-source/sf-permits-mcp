# QA: QS3-A Permit Prep Phase 1

Scenarios covered: [none — all new, pending review]

## CLI Tests (pytest)

1. [NEW] `pytest tests/test_qs3_a_permit_prep.py -v` — all 50 tests pass — PASS/FAIL
2. [NEW] `pytest tests/ --ignore=tests/test_tools.py -q` — no regressions — PASS/FAIL

## API Tests (Flask test client)

3. [NEW] POST /api/prep/create with valid permit — 201 response — PASS/FAIL
4. [NEW] GET /api/prep/<permit_number> returns JSON with items grouped by category — PASS/FAIL
5. [NEW] PATCH /api/prep/item/<id> toggles status, HTMX returns fragment — PASS/FAIL
6. [NEW] POST /api/prep/create returns 401 for anonymous — PASS/FAIL
7. [NEW] GET /api/prep/preview/<permit> returns preview JSON with is_preview=true — PASS/FAIL

## Route Tests

8. [NEW] GET /prep/<permit_number> renders checklist with categories and progress bar — PASS/FAIL
9. [NEW] GET /prep/<permit_number> requires authentication (302 redirect) — PASS/FAIL
10. [NEW] GET /account/prep lists active checklists with progress — PASS/FAIL
11. [NEW] Authenticated nav shows "Permit Prep" link — PASS/FAIL

## Integration Tests

12. [NEW] search_results_public.html contains "Prep Checklist" link — PASS/FAIL
13. [NEW] intel_preview.html contains "Permit Prep" section — PASS/FAIL
14. [NEW] Brief data includes prep_summary — PASS/FAIL
15. [NEW] Print stylesheet exists for prep page — PASS/FAIL
16. [NEW] DDL in scripts/release.py includes prep_checklists and prep_items — PASS/FAIL

## Visual (Playwright — deferred to termRelay if available)

17. [NEW] Screenshot /prep at 375px — no horizontal scroll, touch targets >= 48px — SKIP (no Playwright in build agent)
18. [NEW] Screenshot /prep at 768px — SKIP
19. [NEW] Screenshot /prep at 1440px — SKIP
20. [NEW] Print stylesheet removes nav and header — SKIP (manual visual check)
