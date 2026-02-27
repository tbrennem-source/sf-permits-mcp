## SUGGESTED SCENARIO: Severity badge visible on permit lookup

**Source:** web/routes_search.py (_ask_permit_lookup + _get_severity_for_permit), web/templates/fragments/severity_badge.html
**User:** expediter
**Starting state:** User is logged in and searches for a specific permit number that is in the permits DB
**Goal:** Quickly assess the risk level of a permit without reading the full details
**Expected outcome:** A colored tier badge (CRITICAL / HIGH / MEDIUM / LOW / GREEN) appears alongside the permit result, reflecting the permit's computed severity score
**Edge cases seen in code:** Severity computation fails gracefully — if DB is unavailable or scoring raises, the badge is simply omitted rather than breaking the search result
**CC confidence:** high
**Status:** PENDING REVIEW


## SUGGESTED SCENARIO: Severity cache populated by nightly cron

**Source:** web/routes_cron.py (cron_refresh_severity_cache), scripts/release.py (severity_cache DDL)
**User:** admin
**Starting state:** severity_cache table exists but is empty (fresh deploy or manual flush)
**Goal:** Populate the cache with scores for all active permits so search results load quickly
**Expected outcome:** POST /cron/refresh-severity-cache with correct CRON_SECRET bearer token processes up to 500 permits, upserts score/tier/drivers for each, and returns a JSON response with permits_scored count and elapsed time
**Edge cases seen in code:** Batch limited to 500 per run to prevent Railway timeouts; individual permit errors are counted separately and do not abort the batch
**CC confidence:** high
**Status:** PENDING REVIEW
