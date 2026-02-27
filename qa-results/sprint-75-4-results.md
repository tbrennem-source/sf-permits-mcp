# QA Results — Sprint 75-4: Demo Severity + PWA Polish

**Date:** 2026-02-26
**Agent:** 75-4
**Method:** pytest unit tests + manual CLI verification

---

## CLI Results (pytest)

| Check | Result | Notes |
|-------|--------|-------|
| 24 Sprint 75-4 unit tests pass | PASS | 0 failures |
| manifest.json maskable purpose | PASS | both icons have `"purpose": "any maskable"` |
| sitemap.xml includes /demo | PASS | `/demo` present in XML output |
| Cache TTL = 900s (15 min) | PASS | `_DEMO_CACHE_TTL == 900` |
| /demo route returns 200 | PASS | test_demo_returns_200 |
| severity-CRITICAL CSS in /demo | PASS | test_demo_contains_severity_css |
| severity-pill class in /demo | PASS | test_demo_contains_severity_pill_class |
| score_permit importable | PASS | from src.severity import score_permit |
| score_permit returns valid tier | PASS | tiers: CRITICAL/HIGH/MEDIUM/LOW/GREEN |
| manifest has all required PWA fields | PASS | name, short_name, start_url, display, icons |

## Browser Steps

| Check | Result | Notes |
|-------|--------|-------|
| /demo renders severity badge | DEFERRED | Requires staging with data — visual check at DeskRelay |
| Permit table Severity column | DEFERRED | Requires staging with data |
| PWA installable in Chrome | DEFERRED | Requires staging — DevTools manifest check |

## Summary

PASS: 10/10 CLI checks
DEFERRED: 3/3 browser visual checks (DeskRelay)

Pre-existing failure: `test_permit_lookup_address_suggestions` — fails on main branch before this sprint. Not caused by Sprint 75-4 changes (verified by git stash test).
