# Sprint 69 Session 4 — QA Results

**Date:** 2026-02-26
**Session:** Sprint 69 Session 4 (Portfolio + PWA)
**Method:** File-based checks (Python) + curl HTTP checks against local Flask dev server (port 5199)
**Note:** Playwright browser checks blocked by block-playwright.sh hook in main agent; browser-equivalent checks run via curl with content inspection.

---

## File Checks

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | portfolio-brief.md exists and has >500 words | PASS | 1,054 words |
| 2 | portfolio-brief.md contains "Tim Brenneman" | PASS | Found in title line |
| 3 | portfolio-brief.md mentions "entity resolution" | PASS | Present in body |
| 4 | portfolio-brief.md mentions test count in 3000+ range | PASS | "3,327 automated tests" on line 15 |
| 5 | linkedin-update.md has Headline, About, Experience sections | PASS | All 3 sections present as H2 headers |
| 6 | model-release-probes.md has 10+ probe entries | PASS | 14 individual probes (### Probe N.N format) across 6 categories |
| 7 | dforge-public-readme.md mentions "behavioral scenario" | PASS | Present in body |
| 8 | dforge-public-readme.md mentions "Black Box" | PASS | Present in body |
| 9 | manifest.json is valid JSON | PASS | Parses cleanly with Python json.loads() |
| 10 | manifest.json has theme_color "#22D3EE" | PASS | Exact match confirmed |
| 11 | icon-192.png exists and is valid PNG | PASS | Valid PNG magic bytes, 547 bytes |
| 12 | icon-512.png exists and is valid PNG | PASS | Valid PNG magic bytes, 1,882 bytes |

---

## Browser / HTTP Checks

Dev server started at http://127.0.0.1:5199 with `app.config['TESTING'] = True`.

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 13 | GET /robots.txt — HTTP 200 | PASS | 200 OK, 232 bytes |
| 14 | robots.txt contains "Disallow: /admin/" | PASS | Present |
| 15 | robots.txt contains "Allow: /" | PASS | Present |
| 16 | robots.txt contains "Sitemap:" | PASS | Points to production sitemap URL |
| 17 | GET /static/manifest.json — HTTP 200 | PASS | 200 OK, valid JSON served |
| 18 | manifest.json served with correct theme_color | PASS | "#22D3EE" confirmed in HTTP response |
| 19 | GET / — landing page loads, HTTP 200 | PASS | 200 OK, page title "sfpermits.ai — San Francisco Building Permit Intelligence" |
| 20 | Landing page has CTA buttons (>0 visible) | PASS | 3 button elements found |
| 21 | No 500 error banner on landing page | PASS | No error content detected |
| 22 | Search form present and visible on landing page | PASS | `<form class="search-form" action="/search">` with text input found |
| 23 | Search input field accepts text (placeholder present) | PASS | placeholder="Enter an address, permit #, or block/lot..." |
| 24 | Search with valid address — no traceback, no 500 | PASS | HTTP 200, "couldn't complete your search" shown gracefully (DuckDB has no local data, expected) |
| 25 | Search with empty query — graceful handling | PASS | Redirects to / (HTTP 302), no server crash |
| 26 | Search with XSS payload — no unescaped reflection | PASS | `<script>alert(1)</script>` not reflected unescaped; HTTP 200 |
| 27 | GET /brief without auth — redirects to login | PASS | HTTP 302 → /auth/login |
| 28 | GET /health — HTTP 200, valid JSON | PASS | 200 OK, `{"status": "degraded", "db_connected": true}` |
| 29 | /health has db_connected field (truthy) | PASS | `"db_connected": true` |
| 30 | Report page (/report/3718/001) — no traceback in HTML | PASS | Returns HTTP 500 (DuckDB catalog error, no local data), but page renders with structure — no traceback visible in HTML; error logged server-side only |
| 31 | PWA manifest linked in landing page HTML | FAIL | `<link rel="manifest">` tag absent from landing page `<head>`. Manifest file exists and is served, but not referenced in HTML. |
| 32 | PWA meta theme-color in landing page HTML | FAIL | `<meta name="theme-color">` tag absent from landing page HTML |

---

## Detailed Findings

### PASS — robots.txt content
```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cron/
Disallow: /api/
Disallow: /auth/
Disallow: /demo
Disallow: /account
Disallow: /brief
Disallow: /projects

Sitemap: https://sfpermits-ai-production.up.railway.app/sitemap.xml
```

### PASS — manifest.json HTTP response
```json
{
  "name": "sfpermits.ai",
  "short_name": "SF Permits",
  "description": "San Francisco Building Permit Intelligence",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0B0F19",
  "theme_color": "#22D3EE",
  "icons": [
    { "src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### FAIL — PWA manifest not linked in HTML
The manifest.json file exists at `/web/static/manifest.json` and is served correctly at `/static/manifest.json` (HTTP 200). However, neither `web/templates/landing.html` nor `web/templates/index.html` contains a `<link rel="manifest">` tag. Without this tag, browsers will not recognize the app as installable.

Required addition to both templates:
```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#22D3EE">
```

### NOTE — Report page 500
`/report/3718/001` returns HTTP 500 because the local DuckDB instance has no permits table (no data ingested). The HTML renders correctly with page structure (Property Report, Risk Assessment, Permit History sections). No traceback appears in the HTML response. This is a local dev environment limitation, not a code defect.

### NOTE — Search results "couldn't complete"
`/search?q=123+Main+St` returns HTTP 200 with "We couldn't complete your search right now. Please try again." This is graceful error handling from the DuckDB catalog error (no local data). No 500, no traceback.

---

## Summary

| Category | Total | PASS | FAIL | SKIP |
|----------|-------|------|------|------|
| File Checks | 12 | 12 | 0 | 0 |
| Browser/HTTP Checks | 20 | 18 | 2 | 0 |
| **Total** | **32** | **30** | **2** | **0** |

**FAILs:**
- Check 31: `<link rel="manifest">` absent from landing page HTML
- Check 32: `<meta name="theme-color">` absent from landing page HTML

Both FAILs are in `web/templates/landing.html` (and `web/templates/index.html`). The manifest.json file itself is complete and correct. Only the HTML link tags are missing.

Screenshots: qa-results/screenshots/sprint69-s4/ (empty — Playwright blocked in main agent; curl-based checks used instead)
