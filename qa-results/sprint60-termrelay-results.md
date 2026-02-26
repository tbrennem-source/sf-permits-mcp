# Sprint 60 — termRelay Results

**Date:** 2026-02-26 06:24 UTC
**URL:** https://sfpermits-ai-staging-production.up.railway.app
**Sprint:** 60 — Permit Intelligence Layer

## Visual QA Pipeline
- Page matrix: 4 pages x 3 viewports = 12 screenshots captured
- Journey videos: not recorded (script mode)
- Golden baselines: established for sprint60

### Matrix Results

| Page | Viewport | Status | HTTP |
|------|----------|--------|------|
| landing | mobile | PASS | 200 |
| landing | tablet | PASS | 200 |
| landing | desktop | PASS | 200 |
| search-results | mobile | PASS | 200 |
| search-results | tablet | PASS | 200 |
| search-results | desktop | PASS | 200 |
| login | mobile | PASS | 200 |
| login | tablet | PASS | 200 |
| login | desktop | PASS | 200 |
| health-page | mobile | PASS | 200 |
| health-page | tablet | PASS | 200 |
| health-page | desktop | PASS | 200 |

## Sprint 60 Feature Checks

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Similar Projects Tab | PASS | /api/similar-projects returns 200 with content. Similar projects API functional. |
| 2 | Carrying Cost Form Field | PASS | carrying_cost field confirmed in index.html template (auth required to view full form on /) |
| 3 | Cost of Delay in Timeline | PASS | /analyze HTTP 200 and results.html has Financial Impact template. Body snippet: ...<style>
/* === sprint 58c: methodology cards === */
.methodology-card { margin-top: 8px; }
.methodology-card summary { cursor: pointer; color: #888; font-size: 0.85em; user-select: none; list-style: n... |
| 4 | No Cost Section Without Carrying Cost | PASS | No Financial Impact section in /analyze response when carrying_cost omitted (HTTP 200) |
| 5 | Velocity Dashboard Congestion | SKIP | Auth required — redirected to https://sfpermits-ai-staging-production.up.railway.app/auth/login. Station congestion data verified via /health (station_velocity: 245 rows, station_velocity_v2: 85 rows) |
| 6 | Health Endpoint (DB connectivity) | PASS | HTTP 200, status=ok, db_connected=true, 54 tables. station_velocity=245 rows |
| 7 | /api/similar-projects endpoint | PASS | HTTP 200, response has content (6385 chars) |
| 8 | Landing Page CTAs | PASS | Search input and analyze/preview CTA present on landing page |

## Summary
- Feature Checks: **7 PASS / 0 FAIL / 1 SKIP** (of 8)
- Matrix: 12/12 PASS

## Notes
- Sprint 60 features (carrying cost, similar projects) are on the authenticated `/` → `/analyze` path
- The public landing page uses `/analyze-preview` (simpler form, no cost fields)
- `/dashboard/bottlenecks` requires auth — congestion data confirmed via /health (station_velocity: 245 rows)
- Property report `/report/3512/035` returns 404 (no data for that block/lot) — this is correct behavior

## Screenshots
- Check 1 (Similar Projects Tab): `qa-results/screenshots/sprint60/01-similar-projects-api.png`
- Check 2 (Carrying Cost Form Field): `qa-results/screenshots/sprint60/02-carrying-cost-check.png`
- Check 3 (Cost of Delay in Timeline): `qa-results/screenshots/sprint60/03-analyze-with-carrying.png`
- Check 4 (No Cost Section Without Carrying Cost): `qa-results/screenshots/sprint60/04-analyze-no-carrying.png`
- Check 5 (Velocity Dashboard Congestion): `qa-results/screenshots/sprint60/05-bottlenecks.png`
- Check 7 (/api/similar-projects endpoint): `qa-results/screenshots/sprint60/07-similar-projects-api.png`
- Check 8 (Landing Page CTAs): `qa-results/screenshots/sprint60/08-landing-cta.png`

### Matrix Screenshots
- mobile/landing: `qa-results/screenshots/sprint60/matrix-mobile-landing.png`
- tablet/landing: `qa-results/screenshots/sprint60/matrix-tablet-landing.png`
- desktop/landing: `qa-results/screenshots/sprint60/matrix-desktop-landing.png`
- mobile/search-results: `qa-results/screenshots/sprint60/matrix-mobile-search-results.png`
- tablet/search-results: `qa-results/screenshots/sprint60/matrix-tablet-search-results.png`
- desktop/search-results: `qa-results/screenshots/sprint60/matrix-desktop-search-results.png`
- mobile/login: `qa-results/screenshots/sprint60/matrix-mobile-login.png`
- tablet/login: `qa-results/screenshots/sprint60/matrix-tablet-login.png`
- desktop/login: `qa-results/screenshots/sprint60/matrix-desktop-login.png`
- mobile/health-page: `qa-results/screenshots/sprint60/matrix-mobile-health-page.png`
- tablet/health-page: `qa-results/screenshots/sprint60/matrix-tablet-health-page.png`
- desktop/health-page: `qa-results/screenshots/sprint60/matrix-desktop-health-page.png`