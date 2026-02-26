# Public QA Results — Sprint 69 Session 3 — 2026-02-26

**Scope:** Three new content pages: /methodology, /about-data, /demo
**Server:** Local Flask dev on port 5099 (sprint-69-s3 worktree)
**Tool:** Playwright headless Chromium

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | /methodology — 200 response | PASS | HTTP 200 |
| 2 | /methodology desktop screenshot (1440x900) | PASS | methodology-desktop.png saved |
| 2 | /methodology mobile screenshot (375x812) | PASS | methodology-mobile.png saved |
| 3 | /methodology — 'Entity Resolution' visible | PASS | |
| 3 | /methodology — 'Timeline Estimation' visible | PASS | |
| 3 | /methodology — 'Data Provenance' visible | PASS | |
| 3 | /methodology — 'Building Permits' in table | PASS | |
| 3 | /methodology — word count > 2000 | PASS | word count: 3007 |
| 4 | /about-data — 200 response | PASS | HTTP 200 |
| 5 | /about-data desktop screenshot (1440x900) | PASS | about-data-desktop.png saved |
| 5 | /about-data mobile screenshot (375x812) | PASS | about-data-mobile.png saved |
| 6 | /about-data — 'Data Inventory' visible | PASS | |
| 6 | /about-data — 'Pipeline' visible | PASS | |
| 6 | /about-data — 'Knowledge Base' visible | PASS | |
| 7 | /demo — 200 response | PASS | HTTP 200 |
| 8 | /demo desktop screenshot (1440x900) | PASS | demo-desktop.png saved |
| 9 | /demo — noindex meta tag present | PASS | found 1 meta[robots=noindex] |
| 9 | /demo — 'Property Intelligence' visible | PASS | |
| 9 | /demo — 'Permit History' visible | PASS | |
| 9 | /demo — at least one .callout element | PASS | found 5 .callout elements |
| 10 | /methodology — --bg-deep in source | PASS | |
| 10 | /methodology — --signal-cyan in source | PASS | |
| 10 | /methodology — fonts.googleapis.com in source | PASS | |
| 10 | /about-data — --bg-deep in source | PASS | |
| 10 | /about-data — --signal-cyan in source | PASS | |
| 10 | /about-data — fonts.googleapis.com in source | PASS | |
| 10 | /demo — --bg-deep in source | PASS | |
| 10 | /demo — --signal-cyan in source | PASS | |
| 10 | /demo — fonts.googleapis.com in source | PASS | |

**Total: 29 PASS / 0 FAIL**

## Notes

- Routes are registered in `web/routes_misc.py` (not routes_public.py) under the misc Blueprint (no url_prefix).
- Server startup required `app.config['TESTING'] = True` to bypass daily request limit enforcement (131 activity_log entries today in local DuckDB exceeded the 50-request anonymous limit).
- /demo has 5 `.callout` elements, `/methodology` has 3007 words, both well above thresholds.
- noindex meta tag confirmed on /demo only (expected — /methodology and /about-data are indexable).

Screenshots: qa-results/screenshots/sprint69-s3/
- methodology-desktop.png (1440x900, full-page, 1.9 MB)
- methodology-mobile.png (375x812, full-page, 1.8 MB)
- about-data-desktop.png (1440x900, full-page, 687 KB)
- about-data-mobile.png (375x812, full-page, 628 KB)
- demo-desktop.png (1440x900, full-page, 102 KB)
