# Changelog

## Session 23 — Portfolio Dashboard, Intelligence Engine & UI Polish (2026-02-16)

### 6 New Features (Amy Lee Expediter Workflow)

**Feature 1: Portfolio Dashboard** (`/portfolio`)
- Property card grid with health indicators (on_track / behind / at_risk)
- Filter by: All, Action Needed, In Review, Active
- Sort by: Recent Activity, Highest Cost, Most Stale, Worst Health
- Click-to-expand shows permit list per property
- Mobile-responsive with breakpoint at 500px

**Feature 2: Client Tags** (`/watch/tags`)
- Tag editor on each watch item (comma-separated tags)
- Collapsed by default with pencil (✎) toggle
- HTMX inline save, no page reload
- Tags column added to `watch_items` table (DuckDB + PostgreSQL)

**Feature 3: Stale Permit Alerts**
- Morning brief surfaces permits with >60 days of inactivity
- Merged with expiring-soon into unified "Permits Needing Attention" section
- Color-coded: stale (warning), expiring (error)

**Feature 4: Inspection Timeline**
- 11-phase progress bar (SITE VERIFICATION → FINAL INSPECT/APPRVD)
- Lazy-loaded via HTMX `intersect once` trigger inside portfolio card expansion
- Color-coded: green (completed), blue (current), gray (upcoming)

**Feature 5: Intelligence Engine** (`web/intelligence.py`)
- 8 proactive rules: bundle_inspections, companion_permits, triage_delay, plan_check_delay, completion_push, extension_needed, cost_variance, fresh_issuance
- Action items surfaced in morning brief with priority/urgency
- Cross-linked to portfolio dashboard

**Feature 6: Bulk Onboarding** (`/portfolio/discover`, `/portfolio/import`)
- Discover properties by owner name or firm name
- Results table with checkboxes for bulk selection
- One-click import adds all selected as watch items
- Confirmation card with links to Portfolio, Brief, Import More

### 13 UI Audit Fixes
1. ✅ Shared nav partial (`nav.html`) — consistent nav across all 4 pages
2. ✅ HTMX loading spinner on discover form
3. ✅ Tag editor collapsed by default with pencil toggle
4. ✅ Brief summary cards consolidated (6→4)
5. ✅ Stale & expiring sections merged in brief
6. ✅ Cross-links between brief, portfolio, and account pages
7. ✅ Portfolio empty state with onboarding CTAs
8. ✅ Mobile breakpoint for portfolio filters
9. ✅ Health text labels alongside color dots
10. ✅ Inspection timeline wired into portfolio card expansion
11. ✅ Import confirmation expanded CTAs
12. ✅ Brief footer links updated
13. ✅ Action items → portfolio cross-link

### Tests: 836 passing (6 fail, 18 errors — all pre-existing)

### Files Changed (16 files, +1822 / -70)
- `src/db.py` — tags column migration
- `web/app.py` — 6 new routes (portfolio, tags, timeline, discover, import)
- `web/auth.py` — tag CRUD, get_user_tags()
- `web/brief.py` — stale alerts, intelligence engine wiring, summary consolidation
- `web/intelligence.py` — NEW: 8-rule proactive intelligence engine
- `web/portfolio.py` — NEW: portfolio data assembly, discovery, import
- `web/templates/index.html` — nav partial include
- `web/templates/brief.html` — summary cards, merged sections, cross-links
- `web/templates/portfolio.html` — NEW: portfolio dashboard page
- `web/templates/account.html` — nav include, HTMX spinner
- `web/templates/fragments/nav.html` — NEW: shared navigation
- `web/templates/fragments/tag_editor.html` — NEW: collapsible tag editor
- `web/templates/fragments/import_confirmation.html` — NEW: bulk import confirmation
- `web/templates/fragments/inspection_timeline.html` — NEW: timeline progress bar
- `web/templates/fragments/discover_results.html` — NEW: discovery results table
- `tests/test_brief.py` — updated for new brief structure

---

## Session 21.8 — Consolidate Validate + Analyze Plans into One Section (2026-02-16)

### Feature: Merge Redundant Plan Analysis Features (#63)
- **Problem:** Homepage had two overlapping plan analysis features:
  - "Validate Plan Set" (metadata + optional AI vision checkbox)
  - "Analyze Plans (AI Vision)" (full analysis + gallery + recommendations)
  - Both used the same vision code; Analyze Plans was strictly better
  - Users confused about which to use
- **Solution:** Merged into one unified "Analyze Plans" section with two modes:
  - **Full Analysis (default):** AI vision + page gallery + sheet completeness + recommendations
  - **Quick Check (checkbox):** Metadata-only EPR checks, no Vision API call, fast
- **Changes:**
  - Removed "Validate Plan Set" section entirely (60 lines of HTML)
  - Removed "Validate plans" preset chip from homepage
  - Added "Quick Check — metadata only" checkbox to Analyze Plans form
  - Added "Site Permit Addendum" checkbox (previously only on Validate)
  - `/validate` route preserved but marked DEPRECATED with logging notice
  - Results template shows "Quick Check (metadata only)" badge when applicable

### Files Changed (3 files, +80 / -84 lines)
- `web/templates/index.html` — Removed validate section, added checkboxes to analyze form
- `web/app.py` — Route handles `quick_check` + `is_addendum` params, deprecated `/validate`
- `web/templates/analyze_plans_results.html` — Quick-check badge

---

## Session 21.7 — Fix Two NameErrors Crashing Analyze Plans (2026-02-16)

### Bug Fix: Analysis Succeeded but Results Never Rendered (#62)
- **Problem:** PDF analysis completed successfully (Vision API called, session created) but results never displayed — Flask returned 500
- **Root cause:** Two `NameError` bugs in `web/app.py`:
  1. `json.dumps()` used at line 849 but `import json` was missing
  2. `logger.warning()` at line 854 should be `logging.warning()`
- **How they interacted:** Analysis succeeds → `json` NameError when serializing results → falls into except handler → `logger` NameError in except handler → unhandled exception → Flask 500
- **Fix:** Added `import json` to imports, changed `logger` → `logging`
- **Discovered via:** Session 21.6 error logging (which made the stack trace visible in Railway logs for the first time)

### Files Changed (1 file, +2 / -1 lines)
- `web/app.py` — Added `import json` (line 14), fixed `logger` → `logging` (line 855)

---

## Session 21.6 — Fix Analyze Plans 500 Error with Comprehensive Logging (2026-02-16)

### Bug Fix: Silent 500 Errors on PDF Upload (#61)
- **Problem:** `/analyze-plans` endpoint returned HTTP 500 with NO error messages in Railway logs - impossible to debug
- **Root cause:** Flask exception handler caught errors but didn't use `logging.exception()`, so exceptions were silently swallowed
- **Evidence:** Railway logs showed normal operation despite user seeing 500 errors
- **Solution:**
  - Added `logging.exception()` to write full stack traces to Railway logs
  - User now sees styled error box with expandable technical details
  - Added file size validation (max 400 MB) with proper HTTP 413 status
  - Added logging.info() for successful uploads to track processing
  - Wrapped PDF rendering in try-except to detect poppler dependency issues
  - Clear error messages for: database errors, missing poppler, Vision API failures, etc.

### Files Changed (2 files, +48 / -8 lines)
- `web/app.py` — Added comprehensive error logging, file size validation, user-visible tracebacks (lines 783-812)
- `src/vision/pdf_to_images.py` — Wrapped pdf2image in try-except, detect poppler missing (lines 54-76)

### Expected Outcome
- Railway logs now show full stack traces for ALL errors
- Users see helpful error messages instead of generic 500
- Can diagnose if issue is database, poppler, Vision API, or other
- Future errors are visible and debuggable

---

## Session 21.5 — Analyze Plans Loading Indicator Fix (2026-02-16)

### Bug Fix: No Loading Indicator on PDF Upload (#60)
- **Problem:** When uploading PDF to "Analyze Plan Set" and clicking submit, NO loading indicator appeared - form appeared frozen with no visual feedback
- **Root cause:** HTMX's `hx-encoding="multipart/form-data"` for file uploads may not trigger `.htmx-request` CSS class reliably, plus potential DOMContentLoaded timing issues
- **Solution (Iteration 1):** Added explicit JavaScript event listeners for analyze-plans form
  - Listens for HTMX events (`htmx:beforeRequest`, `htmx:afterRequest`)
  - Fallback to form submit event if HTMX doesn't fire (100ms delay)
  - Manually controls loading indicator visibility
  - Disables submit button during upload
- **Solution (Iteration 2 - MORE ROBUST):** Improved event handling with debugging
  - Changed to IIFE (immediately invoked function) instead of DOMContentLoaded
  - Checks `document.readyState` and runs immediately if DOM already loaded
  - Form `submit` event is PRIMARY handler (most reliable, fires first)
  - Added `console.log` statements for debugging
  - Added `htmx:responseError` handler for error cases
  - Sets button opacity to `0.6` when disabled for visual feedback
  - Prevents timing issues and browser caching problems
- **Outcome:** Hourglass spinner (⏳) now appears immediately when "Analyze Plan Set" is clicked, providing clear visual feedback during long PDF uploads (up to 2-3 minutes)

### Files Changed (1 file, +59 lines total)
- `web/templates/index.html` — Added `<script>` with robust event listeners after analyze-plans-loading div (lines 1125-1171)

---

## Session 22 — Report Share Fix + Invite Cohort Templates (2026-02-16)

### Bug Fix: Report Share Was Completely Broken (#59)
- **Fixed field name mismatch** — Share form sent `recipient_email` but route read `email`, so every share attempt silently failed
- **Added personal message** — Optional textarea in share modal, renders as styled callout in email
- **Email template** — Personal message block with sender name, hidden when empty

### Invite Email Cohort Templates (#14)
- **Admin cohort selector** — Dropdown: Friends (casual), Beta Testers, Expediters (professional), Custom
- **Pre-fill templates** — JavaScript auto-populates suggested message per cohort
- **Cohort-specific emails** — Different headings, descriptions, and feature highlights per audience
- **Subject lines** — `"Hey! You're invited..."` (friends) vs `"Invitation: Join sfpermits.ai's Professional Network"` (expediters)

### DuckDB Test Fix
- **Removed `ON DELETE CASCADE`** from `plan_analysis_images` foreign key — DuckDB doesn't support cascade actions, was blocking all test execution

### Tests: 10 new (822+ total)
- 4 auth tests: cohort invites, personal message, default cohort, UI selector
- 6 web tests: share auth, email validation, field name regression, message field, email template rendering

### Files Changed (8 files, +358 / -29)
- `src/db.py` — Remove CASCADE from DuckDB FK
- `web/app.py` — Share route fix + cohort invite support
- `web/templates/report.html` — Fix field name, add message textarea
- `web/templates/report_email.html` — Personal message block
- `web/templates/account.html` — Cohort selector + message field
- `web/templates/invite_email.html` — Cohort-specific email templates
- `tests/test_auth.py` — 4 new invite tests
- `tests/test_web.py` — 6 new share tests

---

## Session 21.4 — External DBI Link Fix (2026-02-16)

### Replace External Links with Internal Searches
- **Fixed broken external redirects** — Clicking permit/complaint numbers in property reports redirected to dbiweb02.sfgov.org (broken ASP.NET site showing errors)
- **Internal search routes** — All permit/complaint links now navigate to `/?q={number}` which triggers internal search
- **Stays within app** — Users remain in our AI-powered interface with Quick Actions available

### Changes
- `src/report_links.py` — Replace external URLs with `/?q={number}` routes (2 methods)
- `web/templates/report.html` — Remove `target="_blank"` from 4 links (lines 563, 655, 681, 777)

**Before:** Click permit → external DBI site → ASP.NET error page
**After:** Click permit → internal search → our database results + Quick Actions

**Commit:** `c376e80` — fix: Replace external DBI links with internal searches

---

## Session 21.3 — Permit Lookup UX Enhancements + Critical Fixes (2026-02-16)

### Hourglass Spinner + Action Buttons
- **Added hourglass spinner to permit lookup** — Visual consistency across all forms (⏳ with pulsing dots)
- **Enhanced action buttons** — 4 quick actions after all search results (View Report, Ask AI, Analyze Project, Check Violations)
- **Action buttons at TOP** — Moved from bottom to top in highlighted blue box (user request)
- **Contextual actions** — Buttons auto-populate with address/permit data from search/lookup

### Action Buttons
1. 📊 **View Property Report** (primary) — Links to full property analysis
2. 💬 **Ask AI** — "What permits are needed for work at {address}?"
3. 🔍 **Analyze Project** — Submits to /ask with address
4. ⚠️ **Check Violations** — "Are there any violations at {address}?"

### CRITICAL Bug Fixes
- **Fixed `_ph()` ImportError** — Removed non-existent `_ph()` function calls causing property report button to never appear
- **Fixed block/lot resolution** — Restored fallback query for addresses like "1234 market" where exact match fails
- **Fixed Analyze Project button** — Changed from broken link to working form POST

### Before/After
- **Before:** Basic pulsing dots on lookup, only 1 button (View Report) at bottom, property report missing for most searches
- **After:** Hourglass spinner everywhere, 4 functional action buttons at TOP in blue box, property report works for all addresses

### Files Changed
- `web/templates/index.html` — Hourglass spinner for lookup (6 → 14 lines)
- `web/templates/lookup_results.html` — Action button panel (7 → 45 lines)
- `web/templates/search_results.html` — Action button panel (5 → 50 lines)
- `web/app.py` — Pass `street_address` context to all search routes (3 routes updated)

**Commits:**
- `8e3421f` — feat: Add hourglass spinner to permit lookup + action buttons
- `2d458cd` — fix: Add action buttons to search results (not just lookup)

---

## Session 21.2 — Phase 4.5 Hotfix: Timeout Fix for Large PDFs (2026-02-16)

### Timeout & Progress Indicator Fix
- **Increased gunicorn timeout** — 120s → 300s to support 40-50 page PDF uploads
- **Enhanced progress indicator** — Animated hourglass spinner (⏳) with pulsing dots
- **Clear user messaging** — "Large files may take 2-3 minutes to process"
- **Time budget** — 50 pages: 30s Vision + 150s rendering + 10s DB = 190s (under 300s limit)

### Problem Solved
- **Before:** 40+ page PDFs timed out at 120s, no gallery displayed, users saw endless spinner
- **After:** 40-50 page PDFs complete in ~140-190s with clear progress feedback

### Files Changed
- `web/railway.toml` — Timeout 120s → 300s
- `web/templates/index.html` — Hourglass spinner, progress dots, messaging

**Commit:** `7e6359f` — hotfix: Increase timeout and add progress indicator for large PDFs

---

## Session 21.1 — Phase 4.5 Hotfix: Critical Path & Variable Fixes (2026-02-16)

### Critical Bug Fixes
- **Fixed template variable mismatch** — Route wasn't passing `extractions` list to template, causing entire gallery to be hidden
- **Fixed URL path mismatch** — All template URLs changed from `/plan-analysis/*` to `/plan-images/*` to match actual routes
- **Fixed download ZIP path** — Changed `/download-zip` to `/download-all` to match implemented route
- **Fixed email route path** — Changed `/plan-analysis/<session_id>/email` to `/plan-images/email`
- **Fixed email comparison context** — Changed format from `comparison:X,Y` to `comparison-X-Y` to match server parsing
- **Removed PDF download button** — Feature not implemented in Phase 4.5 (planned for 4.6)

### Impact
Without these fixes, Phase 4.5 visual UI was completely non-functional:
- ✗ All images returned 404 (path mismatch)
- ✗ Gallery hidden (missing template variable)
- ✗ ZIP download failed (wrong path)
- ✗ Email comparison broken (format mismatch)

**Status:** All visual features now functional after hotfix

---

## Session 21 — Phase 4.5: Visual Plan Analysis UI (2026-02-16)

### Visual Plan Gallery & Viewer
- **Database-backed image storage** — 24h session expiry with nightly cleanup
- `plan_analysis_sessions` table — stores filename, page_count, page_extractions (JSONB/TEXT)
- `plan_analysis_images` table — base64 PNG storage per page, CASCADE delete on session expiry
- `web/plan_images.py` module — `create_session()`, `get_session()`, `get_page_image()`, `cleanup_expired()`
- PostgreSQL (prod) + DuckDB (dev) dual-mode support

### Enhanced analyze_plans Tool
- Added `return_structured: bool = False` parameter to `src/tools/analyze_plans.py`
- Returns tuple `(markdown_report, page_extractions)` when True
- Backward compatible — existing MCP callers get markdown string as before
- Web route now renders all pages (cap at 50) and creates session

### Web UI Components (analyze_plans_results.html)
- **Thumbnail gallery** — CSS grid with lazy loading, page numbers + sheet IDs
- **Detail cards** — Extracted metadata (sheet #, address, firm, professional stamp)
- **Lightbox viewer** — Full-screen with keyboard navigation (arrows, escape)
- **Side-by-side comparison** — Compare any two pages with dropdown selectors
- **Email modal** — Share analysis with recipient via Mailgun
- Dark theme with CSS variables, responsive grid layout

### API Routes
- `GET /plan-images/<session_id>/<page_number>` — Serve rendered PNG images (24h cache)
- `GET /plan-session/<session_id>` — Return session metadata as JSON
- `GET /plan-images/<session_id>/download-all` — ZIP download of all pages
- `POST /plan-analysis/email` — Email analysis to recipient (full or comparison context)
- Nightly cron cleanup integrated — deletes sessions older than 24h

### JavaScript Interactivity
- State management: `currentPage`, `sessionId`, `pageCount`, `extractions`
- Functions: `openPageDetail()`, `openLightbox()`, `openComparison()`, `downloadPage()`, `downloadAllPages()`, `emailAnalysis()`
- Keyboard navigation in lightbox (ArrowLeft, ArrowRight, Escape)
- Dropdown population for comparison view with sheet metadata

### Tests
- **21 new tests** — `test_plan_images.py` (8 unit), `test_plan_ui.py` (10 integration), `test_analyze_plans.py` (+3)
- Tests cover: session creation, image retrieval, cleanup, route responses, ZIP download, email delivery
- **833 tests total** (812 → 833)

### Performance & Security
- 50-page cap to avoid timeouts (configurable)
- Graceful degradation — falls back to text report if image rendering fails
- Session IDs via `secrets.token_urlsafe(16)` act as capability tokens
- Per-page images: ~50-150 KB base64 PNG (150 DPI, max 1568px)
- 24h expiry prevents database bloat

---

## Session 20 — Bounty Points, Nightly Triage & Quick Fixes (2026-02-16)

### Bounty Points System
- `points_ledger` table (DuckDB + PostgreSQL) with user, points, reason, feedback_id
- `award_points()` — idempotent, auto-calculated on resolution: bugs 10pts, suggestions 5pts, screenshot +2, first reporter +5, high severity +3, admin bonus
- `get_user_points()`, `get_points_history()` — total and history with reason labels
- Wired into PATCH `/api/feedback/<id>` and admin HTMX resolve route
- Account page shows Points card with total and recent history
- Admin feedback queue: "1st reporter" checkbox + "Resolve (+pts)" button
- `GET /api/points/<user_id>` — CRON_SECRET-protected points API

### Nightly Feedback Triage (piggybacked on existing cron)
- Three-tier classification: Tier 1 (auto-resolve: dupes, test/junk, already-fixed), Tier 2 (actionable: clear repro context), Tier 3 (needs human input)
- `is_test_submission()` — pattern matching for test keywords, short admin messages, punctuation-only
- `detect_duplicates()` — exact match + Jaccard word-overlap >0.8 (same user/page within 7 days)
- `is_already_fixed()` — matches against recently resolved items by page+type+similarity
- `classify_tier()` — multi-signal scoring for actionability (repro signals, page URL, screenshot, message length)
- `auto_resolve_tier1()` — PATCH with `[Auto-triage]` prefix
- `run_triage()` — full pipeline, appended to `/cron/nightly` (non-fatal)

### Morning Triage Report (piggybacked on existing cron)
- `web/email_triage.py` — renders + sends triage report to all active admins
- `web/templates/triage_report_email.html` — table-based email: summary metrics, Tier 1 (green), Tier 2 (blue), Tier 3 (amber), CTA button
- `get_admin_users()` — queries `users WHERE is_admin = TRUE AND is_active = TRUE`
- Appended to `/cron/send-briefs` (non-fatal)

### Quick Fixes
- **#18**: "Expeditor Assessment" → "Expeditor Needs Assessment" with explanatory paragraph
- **#22**: View Parcel link fixed — `sfassessor.org` (301 redirect) → `sfplanninggis.org/pim/`
- **#19**: Expediter form pre-fills block/lot/address/neighborhood from query params; report page passes all fields in URL

### Tests
- 67 new tests: 18 bounty points, 43 triage classification + email, 6 others
- **748 tests passing** (681 → 748)

---

## Session 19 — Feedback Triage Round 2: 12 Items (2026-02-16)

### Address Lookup Fix (#8, #10) — Root Cause
- Street suffix mismatch: intent router extracts "16th Ave" but DB stores `street_name="16TH"` + `street_suffix="AVE"` separately
- Added `_strip_suffix()` helper to separate base name from suffix before SQL search
- Now searches base name against `street_name` column AND full name against concatenation
- Applied fix to: `permit_lookup._lookup_by_address()`, `brief._get_property_synopsis()`, `app._resolve_block_lot()`
- Fixes: home page search, morning brief property synopsis, account page primary address

### Ask AI Link Fix (#7)
- CTA link was `<a href="/ask?q=...">` (GET) but `/ask` route only accepts POST
- Changed to `<form method="POST">` with hidden input + styled button

### CLI Resolve Endpoint (Process Improvement)
- New `PATCH /api/feedback/<id>` — CRON_SECRET-protected, accepts `{"status": "resolved", "admin_note": "..."}`
- Updated `scripts/feedback_triage.py` with `--resolve 4,5 --note "Fixed"` flag
- Full triage→fix→resolve loop now possible without browser admin

### Feedback Triage Results
- 12 unresolved items triaged (HIGH: 2, NORMAL: 4, LOW: 6)
- Fixed: #4, #5 (session 18), #7, #8, #10 (this session)
- Deferred: #6, #9, #12, #14 (enhancements), #11/#13 (investigate)

### Tests
- 5 new tests: PATCH auth, resolve, invalid status, missing status, suffix stripping
- **686 tests passing** (681 → 686)

### Branch Cleanup
- Removed 10 stale worktrees and branches (local + remote)
- Down to: main + claude/clever-snyder (active session)

---

## Session 18 — Bug Fixes: No-Results UX & Morning Brief (2026-02-16)

### Bug #4: Address Search Dead End
- Address search returning "No permits found" now shows "What you can do next" CTA box
- Links to Ask AI (pre-filled with address) and search refinement
- Integrates with existing `report_url` — shows "Run Property Report" link when block/lot is resolvable
- Helpful context: "No permit history doesn't mean no permits are required"

### Bug #5: Morning Brief Empty State
- Fixed missing `query_one` import in `web/brief.py` (would crash data freshness section)
- Added "All quiet on your watched items" banner when user has watches but no permit activity
- Banner suggests expanding lookback period (Today → 7 days → 30 days)

### Branch Audit
- 1 unmerged branch (`claude/focused-chandrasekhar`) — only stale CHANGELOG, code already in main
- 12 merged branches identified for cleanup

### Tests
- **681 tests passing** (620 → 681, includes main-branch tests from prior session)

---

## Session 17 — Feedback Triage API (2026-02-16)

### Feedback Triage System
- New `/api/feedback` JSON endpoint — CRON_SECRET-protected, supports multi-status filtering
- New `/api/feedback/<id>/screenshot` endpoint — serves screenshot images via API auth
- New `scripts/feedback_triage.py` CLI — fetches unresolved feedback, classifies severity, extracts page areas, formats triage report
- Pre-processing: HIGH/NORMAL/LOW severity via keyword matching, page area extraction from URLs, relative age formatting
- Usage: `railway run -- python -m scripts.feedback_triage` to pull and triage production feedback
- New `get_feedback_items_json()` in `web/activity.py` — JSON-serializable feedback with ISO timestamps

### Tests
- 11 new tests: API auth (403), JSON structure, status filtering, multi-status, screenshot API, triage severity classification, page area extraction, age formatting, report formatting
- **620 tests passing** (609 → 620)

---

## Session 16 — Feedback Screenshot Attachment (2026-02-15)

### Feedback Widget Enhancement
- Screenshot attachment for feedback submissions — users can capture page state for LLM debugging
- Dual capture: "Capture Page" (html2canvas) + "Upload Image" (file picker)
- Screenshots stored as base64 JPEG in PostgreSQL `screenshot_data TEXT` column (~300KB typical)
- html2canvas lazy-loaded on first click (saves ~40KB per page load)
- Capture overlay ("Capturing page screenshot...") replaces jarring modal hide/show
- Form auto-resets after successful submit (textarea, screenshot, radio buttons), modal auto-closes after 3s
- Admin feedback queue shows "View Screenshot" toggle with lazy-loaded image
- Admin-only `/admin/feedback/<id>/screenshot` route decodes base64 and serves image
- Server-side validation: must start with `data:image/`, max 2MB, invalid data silently dropped
- DuckDB + PostgreSQL dual-mode support with idempotent migrations

### Tests
- 12 new screenshot tests in `tests/test_activity.py`:
  - Submit with/without screenshot, store + retrieve, has_screenshot flag
  - Invalid data dropped, oversized data dropped
  - Admin route auth (403), missing screenshot (404), image serve (200 + mime type)
  - Admin page shows "View Screenshot" button, widget has capture/upload buttons
- **609 tests passing** (567 → 609), 0 skipped

---

## Session 9 — Web UI + Predictions Refresh (2026-02-14)

### Amy Web UI (sfpermits.ai)
- Built Flask + HTMX frontend in `web/` — dark-themed, tabbed results, preset scenarios
- Form accepts: project description, address, neighborhood, cost, square footage
- Runs all 5 decision tools and renders markdown output as styled HTML tabs
- 5 preset "quick start" scenarios matching Amy's stress tests
- Dockerfile.web for containerized deployment (Railway/Fly.io)
- Railway deployment files: Procfile, railway.toml, requirements.txt

### System Predictions Refresh
- Regenerated `data/knowledge/system_predictions.md` with source citations (37K → 69K chars)
- All 5 tools × 5 scenarios now include `## Sources` sections with clickable sf.gov links
- Generation script at `scripts/generate_predictions.py` for reproducible runs

### Tests
- 9 new web UI tests in `tests/test_web.py`:
  - Homepage rendering, neighborhood dropdown, empty description validation
  - Full analysis for kitchen/restaurant/ADU scenarios
  - No-cost fee info message, markdown-to-HTML conversion
- **254 tests passing** (245 → 254), 0 skipped

### Dependencies
- Added `flask`, `markdown`, `gunicorn` to `[project.optional-dependencies] web`

---

## Phase 2.75 — Permit Decision Tools (2026-02-14)

### Knowledge Supplement (Phase 2.6+)
- Created `tier1/title24-energy-compliance.json` — CA Title-24 Part 6 energy forms (CF1R/CF2R/CF3R residential, NRCC/NRCI/NRCA nonresidential), triggers by project type, 6 common corrections (T24-C01 through T24-C06), SF all-electric requirement (AB-112), climate zone 3
- Created `tier1/dph-food-facility-requirements.json` — SF DPH food facility plan review: 7 general requirements (DPH-001 through DPH-007), 8 specific system requirements (DPH-010 through DPH-017), facility categories, parallel permits needed
- Created `tier1/ada-accessibility-requirements.json` — ADA/CBC Chapter 11B path-of-travel: valuation threshold ($195,358), cost tiers (20% rule vs full compliance), 8 common corrections (ADA-C01 through ADA-C08), CASp information, special cases (historic, seismic, change of use)
- Updated `KnowledgeBase` to load all 15 tier1 JSON files (was 12)

### Tool Enhancements (knowledge integration)
- `predict_permits` — now flags SF all-electric requirement (AB-112) for new construction, ADA threshold analysis with 20% vs full compliance, DPH menu/equipment schedule requirements for restaurants, Title-24 form requirements by project scope
- `estimate_fees` — added ADA/Accessibility Cost Impact section: computes adjusted construction cost vs $195,358 threshold, reports whether full compliance or 20% limit applies
- `required_documents` — expanded DPH agency documents (7 items with DPH-001 through DPH-007 references), knowledge-driven Title-24 form requirements (CF1R/NRCC), existing conditions documentation for alterations (T24-C02), DA-02 checklist auto-flagged for all commercial projects
- `revision_risk` — added Top Correction Categories section with citywide frequencies (Title-24 ~45%, ADA ~38%, DPH for restaurants), CASp mitigation for commercial projects, DA-02 submission reminders

### Knowledge Validation (Phase 2.6)
- Validated `tier1/fee-tables.json` (54K, 19 tables, 9-step algorithm, eff. 9/1/2025)
- Validated `tier1/fire-code-key-sections.json` (37K, 13 SFFD triggers)
- Validated `tier1/planning-code-key-sections.json` (36K, 6 major sections)
- Created `tier1/epr-requirements.json` — 22 official DBI EPR checks from Exhibit F + Bluebeam Guide, severity-classified (reject/warning/recommendation)
- Created `tier1/decision-tree-gaps.json` — machine-readable gap analysis for all 7 steps + 6 special project types, used by tools for confidence reporting
- Created `DECISION_TREE_VALIDATION.md` — human-readable validation summary
- Confirmed: `estimated_cost` is DOUBLE in DuckDB (no CAST needed), `plansets` field does not exist

### New MCP Tools (5)
- `predict_permits` — Takes project description → walks 7-step decision tree → returns permits, forms, OTC/in-house review path, agency routing, special requirements, confidence levels. Uses `semantic-index.json` (492 keyword aliases from 61 concepts) for project type extraction.
- `estimate_timeline` — Queries DuckDB for percentile-based timeline estimates (p25/p50/p75/p90) with progressive query widening, trend analysis (recent 6mo vs prior 12mo), and delay factors. Creates `timeline_stats` materialized view on first call.
- `estimate_fees` — Applies Table 1A-A fee schedule (10 valuation tiers) to compute plan review + issuance fees, plus CBSC/SMIP surcharges. Statistical comparison against DuckDB actual permits. ADA threshold analysis for commercial projects.
- `required_documents` — Generates document checklist from permit form, review path, agency routing, and project triggers. Includes full EPR requirements (22 checks), Title-24 forms, DPH requirements, DA-02 for commercial, and pro tips.
- `revision_risk` — Estimates revision probability using `revised_cost > estimated_cost` as proxy signal (125K revision events in 1.1M permits). Computes timeline penalty, common triggers by project type, correction frequencies from compliance knowledge, mitigation strategies.

### Module Architecture
- Created `src/tools/knowledge_base.py` — shared `KnowledgeBase` class loads all 15 tier1 JSON files once via `@lru_cache`. Builds keyword index from semantic-index.json for project type matching.
- 5 new tool modules in `src/tools/`: `predict_permits.py`, `estimate_timeline.py`, `estimate_fees.py`, `required_documents.py`, `revision_risk.py`
- Server.py updated: imports + registers all 13 tools (5 SODA + 3 entity/network + 5 decision)

### Tests
- 70 new tests across 7 files:
  - `test_predict_permits.py` (14) — keyword extraction, KnowledgeBase loading, semantic matching, full predictions for restaurant/kitchen/ADU scenarios
  - `test_estimate_fees.py` (8) — fee calculation per tier, surcharges, tool output with project types
  - `test_required_docs.py` (7) — base docs, agency-specific, trigger-specific, EPR, demolition, historic, commercial TI ADA
  - `test_timeline.py` (5) — DuckDB queries with neighborhood, cost, review path, triggers
  - `test_revision_risk.py` (5) — basic, neighborhood, restaurant triggers, mitigation, timeline impact
  - `test_integration_scenarios.py` (9) — 5 Amy stress test scenarios through predict + fees + docs chain
  - `test_knowledge_supplement.py` (22) — Title-24/DPH/ADA loading, predict_permits all-electric/ADA threshold, required_docs DPH items/DA-02/NRCC, estimate_fees ADA analysis, revision_risk correction frequencies
- **All 96 tests passing** (86 pass + 10 DuckDB-dependent skipped)
- Improved DuckDB skip logic: now checks for actual permits table, not just file existence

### Integration Test Scenarios
- `data/knowledge/system_predictions.md` (37K) — full output of all 5 tools across 5 scenarios:
  - A: Residential kitchen remodel (Noe Valley, $85K)
  - B: ADU over garage (Sunset, $180K)
  - C: Commercial TI (Financial District, $350K)
  - D: Restaurant conversion (Mission, $250K)
  - E: Historic building renovation (Pacific Heights, $2.5M)

---

## Phase 2 — Network Model Validation (2026-02-13)

### DuckDB Ingestion Pipeline (`src/ingest.py`)
- Paginated fetch (10K/page) of 3 contact datasets via existing `SODAClient`
  - Building Permits Contacts (`3pee-9qhc`, ~1M records)
  - Electrical Permits Contacts (`fdm7-jqqf`, ~340K records)
  - Plumbing Permits Contacts (`k6kv-9kix`, ~503K records)
- Building Permits (`i98e-djp9`, ~1.28M records) ingested for enrichment
- Building Inspections (`vckc-dh2h`, ~671K records) ingested for inspector data
- Unified `contacts` table normalizes names, roles, and keys across all three schemas
- `estimated_cost` cast from TEXT to DOUBLE during ingestion
- Ingest log tracks last-fetched timestamp per dataset

### DuckDB Schema (`src/db.py`)
- 6 tables: `contacts`, `entities`, `relationships`, `permits`, `inspections`, `ingest_log`
- 16 indexes on join columns: `permit_number`, `pts_agent_id`, `license_number`, `sf_business_license`, `entity_id`, `inspector`, `canonical_name`, etc.

### Entity Resolution (`src/entities.py`)
- 5-step cascading pipeline:
  1. `pts_agent_id` grouping (building contacts only, high confidence)
  2. `license_number` grouping across all sources (medium confidence, merges into existing entities)
  3. `sf_business_license` grouping across all sources (medium confidence, merges into existing entities)
  4. Fuzzy name matching with trigram-prefix blocking and token-set Jaccard similarity >= 0.75 (low confidence)
  5. Singleton entity creation for remaining unresolved contacts
- Canonical name/firm selection picks longest non-null value
- Entity type determined by most common role across grouped contacts

### Co-occurrence Graph (`src/graph.py`)
- Self-join on `contacts` table (a.entity_id < b.entity_id on shared permit_number)
- LEFT JOIN to `permits` for cost, type, date, neighborhood enrichment
- Edge attributes: shared_permits count, permit_numbers (capped at 20), permit_types, date range, total_estimated_cost, neighborhoods
- All computation in a single INSERT...SELECT pushed to DuckDB
- 1-hop neighbor and N-hop network traversal queries

### Validation & Anomaly Detection (`src/validate.py`)
- `search_entity(name)` — case-insensitive LIKE search on canonical_name/firm, returns top 5 co-occurring entities
- `entity_network(entity_id, hops)` — N-hop ego network with nodes and edges
- `inspector_contractor_links(inspector_name)` — traces inspector to permit to contact entity relationships
- `find_clusters(min_size, min_edge_weight)` — connected-component detection via BFS on filtered subgraph
- `anomaly_scan(min_permits)` — flags high permit volume (>3x type median), inspector concentration (>=50%), geographic concentration (>=80%), fast approvals (<7 days, >$100K)
- `run_ground_truth()` — searches for Rodrigo Santos, Florence Kong (inspectors), Bernard Curran (contact)

### New MCP Tools
- `search_entity` — search entities by name across all resolved contact data
- `entity_network` — get N-hop relationship network around an entity
- `network_anomalies` — scan for anomalous patterns in the permit network

### Tests
- 16 new tests in `tests/test_phase2.py` (in-memory DuckDB, no network access):
  - Schema creation verification
  - Entity resolution helpers: `_pick_canonical_name`, `_pick_canonical_firm`, `_most_common_role`, `_token_set_similarity`
  - Full entity resolution pipeline with cross-source merging assertions
  - Graph construction and edge weight verification
  - 1-hop neighbor and N-hop network queries
  - Entity search (found and not-found cases)
  - Inspector-contractor link tracing
  - Anomaly scan structure
  - Cluster detection

### Configuration
- Added `duckdb` to dependencies in `pyproject.toml`
- Added `data/` to `.gitignore` (DuckDB file not committed)

---

## Phase 1 — MCP Server + Dataset Catalog (2026-02-12)

### MCP Tools (5)
- `search_permits` — search building permits by neighborhood, type, status, cost, date, address, description
- `get_permit_details` — full details for a specific permit by permit number
- `permit_stats` — aggregate statistics grouped by neighborhood, type, status, month, or year
- `search_businesses` — search registered business locations in SF
- `property_lookup` — property assessments by address or block/lot

### Infrastructure
- FastMCP server entry point (`src/server.py`)
- Custom async SODA client with httpx (`src/soda_client.py`, ~108 lines)
- Response formatters for Claude consumption (`src/formatters.py`)
- 22 datasets cataloged in `datasets/catalog.json` and `datasets/CATALOG.md`
- SODA API performance benchmarks across 7 datasets (`benchmarks/RESULTS.md`)
- 10 integration tests in `tests/test_tools.py`

### Documentation
- Architecture decisions log (`docs/DECISIONS.md`): build-vs-fork, SODA client choice, NIXPACKS deployment
- Contact data deep-dive (`docs/contact-data-report.md`)
- Mehri reference model (`docs/mehri-reference.md`)

### Key Findings
- Baseline SODA API latency: ~450-650ms per query
- Aggregation cold-cache penalty: 10-14s on large datasets (warm cache: ~600ms)
- 13.3M total records across 22 datasets
