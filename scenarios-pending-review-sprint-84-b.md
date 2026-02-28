## SUGGESTED SCENARIO: Browser caches CSS for 24 hours after first load
**Source:** web/app.py _add_static_cache_headers after_request hook
**User:** homeowner
**Starting state:** User visits sfpermits.ai for the first time; browser has no cached assets
**Goal:** Browser loads the page efficiently on repeat visits without re-downloading unchanged CSS/JS
**Expected outcome:** CSS and JS assets are served with Cache-Control: public, max-age=86400, stale-while-revalidate=604800 — browser caches them for up to 24 hours and serves stale copies for up to 7 days while revalidating in the background
**Edge cases seen in code:** Non-200 responses (e.g. 404 on missing file) receive no Cache-Control header; HTML responses from /static/ also receive no cache header
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: HTML pages are never served from browser cache via static hook
**Source:** web/app.py _add_static_cache_headers after_request hook
**User:** expediter
**Starting state:** User navigates to a search result or property report page
**Goal:** Each HTML page load reflects the latest server-rendered data — never a stale cached copy
**Expected outcome:** HTML responses from any path (including hypothetical HTML files under /static/) receive no Cache-Control header from the static asset hook; the browser fetches fresh HTML on every navigation
**Edge cases seen in code:** The hook checks both path prefix (/static/) AND content-type — a text/html response under /static/ is explicitly excluded; /api/ paths and all non-/static/ paths are entirely skipped
**CC confidence:** high
**Status:** PENDING REVIEW
