# Changelog

## Session 48 — Protocol Hardening: venv + RELAY gate (2026-02-23)

### Process Fixes
- **venv instructions**: Added explicit `source .venv/bin/activate` requirement to Development section of CLAUDE.md — agents were hitting "No module named pytest" because system Python 3.14 doesn't have project deps
- **RELAY gate in CHECKCHAT**: Added validation step to CHECKCHAT VERIFY — now checks `qa-results/` for unprocessed files and requires RELAY to run before CHECKCHAT can proceed. Previously agents could skip RELAY entirely.

### Files Changed
- `~/.claude/CLAUDE.md` — RELAY gate added to CHECKCHAT `### 1. VERIFY`
- `CLAUDE.md` (main repo + 3 worktrees) — venv instructions in Development section, RELAY gate mention in CHECKCHAT summary

---

## Session 47 — GitHub Actions CI Workflow (2026-02-23)

### CI Pipeline
- **New**: `.github/workflows/ci.yml` — runs pytest on every push to `main` and every PR
- Python 3.11, ubuntu-latest, installs via `pip install -e ".[dev,web]"`
- Excludes `test_tools.py` (live SODA API), `test_plan_images.py` and `test_plan_ui.py` (orphaned — `src.plan_images` module missing)
- PR #17 open, CI green: 1211 tests pass in ~3 minutes

### Issues Found
- `test_plan_images.py` and `test_plan_ui.py` import `src.plan_images` which no longer exists — orphaned tests flagged for cleanup

---

## Session 46 — UX Audit Fixes: Analysis History (2026-02-22)

### Bug Fix
- **`web/plan_jobs.py`**: Added `version_group` to `get_user_jobs()` SELECT query — the column was missing, causing `g["_version_group"]` to always be `""`, which prevented the Notes panel from rendering in grouped view

### QA Results (RELAY)
- 21-step QA on Analysis History, Grouped View, and Comparison Page
- 19 PASS, 1 FAIL → fixed (Step 10: notes character counter), 1 SKIP (Step 7: no failed jobs in test data)
- Fix deployed to prod; verified "📝 Notes" toggle and live "9 / 4,000" counter working on production

### Files Changed
- `web/plan_jobs.py` — add `version_group` to SELECT in `get_user_jobs()`

---

## Session 30 — Branch Audit + Developer Onboarding Infrastructure (2026-02-22)

### Branch Cleanup
- Audited all 13 branches (12 local worktrees + 1 remote-only) — confirmed zero conflicting work, all merged to main via PRs #1–#15
- Removed 11 stale worktrees, deleted 12 local branches, deleted 14 remote branches
- Caught and resolved 4 additional hidden remote branches (`angry-tu`, `practical-jepsen`, `zen-swanson`, `tender-knuth`) missed in initial audit; merged `angry-tu`'s DECISIONS.md commit (entries 11+12)
- Closed 4 stale chief tasks: #20 (bot stability), #41 (dup), #42 (RAG shipped), #57 (regulatory watch shipped)

### Developer Onboarding Infrastructure
- **`.github/PULL_REQUEST_TEMPLATE.md`** — "show your work" PR template: what changed, how it works, test output paste, 4-item checklist
- **`docs/ONBOARDING.md`** — new developer guide: local setup, Claude Code workflow, git conventions, project structure, key concepts, safety rules
- **`CLAUDE.md`** — updated Branch & Merge Workflow: role-based rules (Tim pushes direct, contributors use PRs), link to onboarding doc

### Files Changed
- `.github/PULL_REQUEST_TEMPLATE.md` — NEW
- `docs/ONBOARDING.md` — NEW
- `CLAUDE.md` — branch workflow, test count fix (812 → 1,033+), removed stale branch reference

## Session 38j — Nightly Chief Sync Phase 3 + 4 (2026-02-22)

### Phase 3: GitHub Actions Workflow
- **New**: `.github/workflows/nightly-chief-sync.yml` — runs at 3:30 AM PT (11:30 UTC)
- Checks out sf-permits-mcp with full history, generates nightly diff
- Pushes CLAUDE.md, scenarios, QA scripts, STATUS, CHANGELOG to chief-brain-state
- Works even when Mac is asleep (cloud-based)
- Uses `CHIEF_GITHUB_TOKEN` secret for push access to chief-brain-state repo
- Manually triggered and verified: completed in 9s, all artifacts pushed

### Phase 4: Telegram Compliance Alerts
- **Updated**: `~/scripts/nightly-chief-sync.py` — sends Telegram alert on ERROR-severity compliance failures
- Errors only, not warnings (no noise)
- Uses Telegram Bot API via `urllib` (no extra dependencies)
- Credentials in launchd plist `com.dforge.chief-sync` environment variables
- Test message sent and delivered successfully

### Infrastructure
- `CHIEF_GITHUB_TOKEN` secret added to sf-permits-mcp GitHub repo
- launchd plist reloaded with TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars
- **Task #194**: Replaced temporary `gho_` OAuth token with fine-grained PAT (`chief-brain-state-nightly-sync`, 90-day expiry, scoped to chief-brain-state repo, Contents read/write). Workflow re-verified: 13s, success.

## Session 38i — dforge MCP Server Launch (2026-02-22)

### dforge MCP Server — `github.com/tbrennem-source/dforge`
- **Deployed**: FastMCP streamable-http server on Railway at `https://dforge-mcp-production.up.railway.app/mcp`
- **9 tools**: `list_templates`, `get_template`, `list_frameworks`, `get_framework`, `run_intake`, `audit_project`, `list_lessons`, `get_lesson`, `portfolio_status`
- **Content**: 9 project templates (CANON, PRINCIPALS, STATUS, etc.), 3 methodology frameworks (Five Levels, intake interview, project-framework), portfolio dashboard
- **Package**: switched from `fastmcp>=2.0.0` to `mcp[cli]>=1.26.0` for claude.ai compatibility (same fix as sfpermits)
- **Auto-deploy**: GitHub → Railway wired, pushes to `main` trigger rebuild

### Protocol Update — `sf-permits-mcp/CLAUDE.md`
- **Cross-repo routing**: QA scripts for features in other repos go to that repo's `qa-drop/`; scenarios always land in sf-permits `scenarios-pending-review.md`
- **Step 2 clarified**: "Always here, regardless of which repo the feature lives in"

### QA Artifacts
- `dforge/qa-drop/dforge-mcp-server-qa.md` — 12-step QA script for dforge MCP server
- `scenarios-pending-review.md` — 5 new scenarios: MCP connect, get_template, run_intake, audit_project, empty lessons state

## Session 38h — CHECKCHAT Protocol, dforge Framework, QA Cleanup (2026-02-22)

### Protocol Formalization — `~/.claude/CLAUDE.md`
- **Black Box Session Protocol**: READ → BUILD → TEST → SCENARIOS → QA (RELAY) → CHECKCHAT. Every session.
- **CHECKCHAT**: 6-step session close — VERIFY, DOCUMENT, CAPTURE, SHIP, PREP NEXT, BLOCKED ITEMS REPORT.
- **Failure Escalation Policy**: 3 attempts per FAIL, mark BLOCKED if unresolvable, accumulate for end-of-session report.
- **RELAY rewrite**: Simplified — CC runs QA directly via browser tools, no Cowork/clipboard dependency.

### dforge Framework — `~/AIprojects/dforge/`
- **Project Standards Enforcement**: Every onboarded project must have `qa-drop/`, `qa-results/`, `scenarios-pending-review.md`, RELAY active, CHECKCHAT active.
- **Intake interview**: 17 questions including 4 new QA infrastructure checks.
- **Maturity diagnostic**: 10 scored dimensions (0–100) including RELAY, Scenarios, CHECKCHAT, Failure Escalation.
- **Template CLAUDE.md**: New projects auto-get RELAY + CHECKCHAT one-liners.

### Cross-Project Updates
- `sf-permits-mcp/CLAUDE.md`: Added `## CHECKCHAT: active` one-liner.
- `chief/CLAUDE.md`: Created with RELAY + CHECKCHAT active.
- `dforge/CLAUDE.md`: Created with Project Standards Enforcement + RELAY + CHECKCHAT active.

### QA Artifact Cleanup — `sf-permits-mcp/`
- Removed RELAY header block from `qa-drop/session-38f-admin-ops-severity-qa.md` (protocol is now global, not per-script).
- Deleted `qa-drop/launcher.html` and `Makefile` + `scripts/gen_qa_launcher.py` (superseded by direct browser QA execution).

### RELAY Execution
- Ran session-38f QA script: **17/17 PASS** via browser tools. Results in `qa-results/done/`.

## Session 38g (cont.) — RELAY Protocol, QA Launcher, Cowork QA (2026-02-22)

### RELAY Protocol — `~/.claude/CLAUDE.md`, `CLAUDE.md`
- **RELAY (QARELAY)**: Universal QA loop — QA scripts include a RELAY header, results saved to `qa-results/`, fix sessions check for pending FAILs, loop until 0 FAILs, move to `done/`.
- Global protocol lives in `~/.claude/CLAUDE.md` (not project-specific). Project CLAUDE.md has a one-liner pointer: `## RELAY: active`.
- Results use local disk writes (`cat >`) instead of Chief MCP — tool-agnostic.

### QA Launcher — `Makefile`, `scripts/gen_qa_launcher.py`
- **`make qa-launcher`**: Generates `qa-drop/launcher.html` with copy-to-clipboard buttons for each QA `.md` script.
- Dark theme (#1a1a2e), large buttons with hover effects, clipboard API, "✓ Copied!" flash.
- Standalone Python generator avoids Makefile/shell/Python quoting nightmares.

### QA + Scenario Updates
- Updated `qa-drop/session-38f-admin-ops-severity-qa.md` with RELAY header (local disk version).
- Added `qa-results/` and `qa-results/done/` directories (gitignored).
- Cross-repo QA guidance added to CLAUDE.md: feature in another repo → QA script goes there, scenarios always come here.
- Cowork QA: 17/17 PASS on session-38f script (Admin Ops tabs, rapid switching, hash routing, severity holds, transition dates). Results in `qa-results/done/`.
- 1 new pending scenario: DQ checks degrade gracefully when individual checks error.

## Session 38g — DQ Cache, Bulk Indexes, Admin Ops UX Fixes (2026-02-22)

Three rounds of Cowork QA revealed that the Admin Ops DQ tab was unusable — queries on million-row tables hung indefinitely, HTMX error events failed silently, and the initial tab load had a race condition. Redesigned DQ as a cached system and fixed multiple UX issues.

### DQ Cache Architecture — `web/data_quality.py`, `web/app.py`
- **Problem**: DQ tab ran 10 analytical queries live on every load (1.8M contacts × 1.1M permits). Total query time could exceed 60s, hanging the tab.
- **Solution**: Pre-compute all checks into a `dq_cache` table. Tab reads cached results instantly.
- **`dq_cache` table**: stores JSON results + `refreshed_at` timestamp + `duration_secs`.
- **`refresh_dq_cache()`**: runs all 10 checks, stores results. Called by nightly cron + admin Refresh button.
- **`get_cached_checks()`**: reads latest cache entry — instant.
- **`POST /admin/ops/refresh-dq`**: admin UI button triggers live refresh.
- **`POST /cron/refresh-dq`**: external API endpoint (CRON_SECRET auth).
- **Nightly cron**: `refresh_dq_cache()` added to nightly pipeline (non-fatal).
- **Template**: Shows "Last refreshed: ..." timestamp, ⟳ Refresh button, empty state with instructions.

### PostgreSQL Bulk Table Indexes — `web/app.py`
- **Problem**: Bulk data tables (permits 1.1M, contacts 1.8M, addenda 3.9M, etc.) had ZERO indexes on PostgreSQL prod. DuckDB had indexes via `src/db.py _create_indexes()` but PostgreSQL startup migrations only indexed app tables.
- **Fix**: Added 18 indexes to startup migration mirroring DuckDB: `contacts.permit_number`, `permits.permit_number`, `permits.block,lot`, `permits.street_number,street_name`, `permits.status_date`, `inspections.reference_number`, `entities.canonical_name`, `relationships.entity_id_a/b`, `addenda.application_number/station/finish_date`, `timeline_stats.permit_number`, and more.
- **Result**: Orphaned contacts query dropped from 60s+ to 0.4s. Full DQ suite runs in 0.8s.

### DQ Query Hardening — `web/data_quality.py`
- **`_timed_query()`**: Uses PostgreSQL `SET LOCAL statement_timeout` for per-query timeouts at the DB level. SIGALRM doesn't interrupt psycopg2 C extension calls — DB-level timeout is the only reliable mechanism.
- **NOT EXISTS**: Orphaned contacts uses `NOT EXISTS` instead of `LEFT JOIN` for better performance.
- **`_ph()` fix**: Was importing non-existent `_placeholder` from `src.db`. Now uses `BACKEND` check.
- **Column fix**: `inspection_type_desc` → `inspection_description` (matching actual PostgreSQL schema).
- **`%` escaping**: `ILIKE '%new construction%'` → `'%%new construction%%'` (psycopg2 interprets bare `%` as format specifiers when params tuple is passed).
- **Index diagnostic**: `check_bulk_indexes()` queries `pg_indexes` and renders green ✓ / red ✗ tags at bottom of DQ tab.

### Admin Ops Initial Tab Race Condition — `web/templates/admin_ops.html`
- **Problem**: `setTimeout(fn, 0)` fired BEFORE HTMX's `DOMContentLoaded` handler processed `hx-get` attributes. The simulated `.click()` was a no-op — HTMX wasn't listening yet. Users had to click the tab button twice.
- **Fix**: Replaced with `htmx.ajax('GET', url, {target, swap})` which makes the request directly through HTMX's API — no element processing needed.

### Admin Dropdown Hover Gap — `web/templates/fragments/nav.html`
- **Problem**: `top: calc(100% + 6px)` created a 6px gap between the Admin badge and dropdown menu. Mouse loses hover crossing the gap, menu disappears.
- **Fix**: Outer wrapper uses `padding-top: 6px` as an invisible hover bridge. Inner div (`admin-dropdown-menu-inner`) carries the visible styling.

### HTMX Error Handler Robustness — `web/templates/admin_ops.html`
- **`getTrigger()` helper**: Checks both `evt.detail.elt` AND `evt.detail.requestConfig.elt` for HTMX 2.0 compatibility.
- **Simplified error handlers**: All three (`htmx:responseError`, `htmx:sendError`, `htmx:timeout`) call `showError()` unconditionally — no trigger-element guard that could silently fail.
- **35s fallback timer**: If `contentLoaded` is still false after 35s, force-shows an error. Catches edge cases where HTMX events don't fire at all.

### Self-Hosted HTMX — `web/static/htmx.min.js`, all 14 templates
- **Problem**: External CDN (`unpkg.com/htmx.org@2.0.4`) caused 60s+ page load blocks when CDN was slow or unreachable.
- **Fix**: Downloaded htmx.min.js (50KB) to `web/static/`. Replaced CDN reference across all 14 templates.

### Gunicorn Access Logging — `web/Procfile`
- Added `--access-logfile -` so request-level logs appear in Railway.

### Tests
- 1,227 passed, 1 skipped

---

## Session 46 — UX Audit: Analysis History Notes Panel Fix (2026-02-23)

RELAY QA run against s46-ux-audit-analysis-history-qa.md — 16 PASS, 4 SKIP, 1 FAIL fixed.

### Fix: Notes panel now renders for all project groups — `web/app.py`, `web/templates/fragments/analysis_grouping.html`
- **Bug**: `{% if group._version_group %}` blocked notes panel from rendering for all users with pre-existing jobs. The `version_group` column was added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` but existing rows were never backfilled, so `_version_group` was always `""`.
- **Fix**: Use group's normalized key (address/filename) as fallback notes identifier — `notes_key = vg or g.get("key", "")`. The panel now renders for all groups regardless of `version_group` population. Notes are correctly keyed by project identity (same file/address = same project).
- **QA result**: "📝 Notes" toggle visible on both groups in prod (verified in browser).

### QA Results (s46)
- Part A (Steps 1–8): 6 PASS, 2 SKIP (no failed/stale jobs to test retry/undo)
- Part B (Steps 9–11): 2 PASS, 1 FAIL → FIXED
- Part C (Steps 12–21): 8 PASS, 2 SKIP (EPR Changes tab needs EPR comparison data)

---

## Session 45 — Permit Lookup Search Accuracy (2026-02-21/22)

Four improvements to `permit_lookup` search accuracy plus one UX fix for feedback screenshots.

### Exact Street Name Matching — `src/tools/permit_lookup.py`, `web/app.py`
- **Bug**: Searching "146 Lake" matched "146 BLAKE" because `_lookup_by_address` used `LIKE '%LAKE%'` substring matching.
- **Fix**: Switched to exact `=` matching with space-variant support (e.g., `VAN NESS` vs `VANNESS`). All queries in both `permit_lookup.py` and `web/app.py` updated — including `_resolve_block_lot`, `_get_address_intel` (3 queries), `_get_primary_permit_context`, and the block/lot fallback.
- **"Did you mean?" suggestions**: When exact match returns no results, a `LIKE '%name%'` fallback runs and returns up to 5 suggestions (e.g., "Did you mean: BLAKE ST, LAKE MERCED HILL?").

### Historical Lot Discovery — `src/tools/permit_lookup.py`
- **Problem**: Condo conversions reassign lot numbers (e.g., Lot 017 → Lot 069 at 146 Lake St). Block/lot searches missed historical permits under the old lot.
- **New function `_find_historical_lots()`**: Discovers old lot numbers by resolving the street address from the current lot, then finding all distinct lots at the same block + address.
- **Applied to**: `_lookup_by_block_lot()` uses IN clause for multiple lots; `_get_related_location()` also uses historical lots for related-permit queries.

### Address Search Parcel Merge — `src/tools/permit_lookup.py`
- **Problem**: Searching "146 Lake" returned 5 permits, but the property report showed 13. Multi-unit buildings have permits filed under different street numbers (e.g., 144 vs 146).
- **Fix**: After address search returns results, resolves block/lot from the first result, runs `_lookup_by_block_lot()` (which includes historical lots), and merges/deduplicates all parcel-level permits into the response.

### Badge-Table Count Sync — `web/app.py`
- **Bug**: PERMITS badge showed different count than the permit table (badge used address-only query, table used MCP tool with parcel merge + historical lots).
- **Fix round 1**: Converted 5 remaining `LIKE '%name%'` substring queries to exact `=` matching.
- **Fix round 2**: Badge now syncs with MCP tool's actual count by parsing the `Found **N** permits` line from the result markdown. Applied to both address and parcel search handlers.

### Screenshot Limit Increase — `web/app.py`, `web/templates/fragments/feedback_widget.html`
- Raised max screenshot size from 2MB to 5MB (client-side JS + server-side validation).
- Updated error message to reflect new limit.

### Tests
- 3 new tests: `test_find_historical_lots_discovers_old_lot`, `test_find_historical_lots_no_address`, `test_lookup_by_block_lot_multi_lot`
- 5 existing tests updated for new mock call patterns
- Full suite: 1,226 passing, 18 pre-existing errors unchanged

---

## Session 44 — Analysis History Phases D2, E1, E2, F (2026-02-20)

Full implementation of the deferred Analysis History features from SPEC-analysis-history-phases-d-f.md.

### Phase D2: Document Fingerprinting (`web/plan_fingerprint.py`)
- SHA-256 content hash at upload time (Layer 1 — exact match = same file)
- Structural fingerprint: `(page_number, sheet_number)` composite pairs extracted from vision results (Layer 2 — ≥60% overlap = same document)
- Metadata fallback: `permit_number` / `property_address` / normalised filename (Layer 3)
- `find_matching_job()` — selects best match across all three layers
- `plan_analysis_jobs`: `pdf_hash`, `pdf_hash_failed`, `structural_fingerprint` columns

### Phase E1: Version Chain Data Model (`web/plan_jobs.py`, `web/plan_worker.py`)
- `plan_analysis_jobs`: `version_group`, `version_number`, `parent_job_id` columns
- `assign_version_group(job_id, group_id)` — auto-increments within group, sets parent link
- `get_version_chain(version_group)` — returns jobs ordered by `version_number ASC`
- `plan_worker.py`: wires fingerprint matching → version group assignment after each job completes
- `PROMPT_FULL_EXTRACTION`: structured `revisions: [{revision_number, revision_date, description}]` replaces flat `revision: null`

### Phase E2: Comparison Page (`web/plan_compare.py`, `web/templates/analysis_compare.html`)
- `GET /account/analyses/compare?a=<job_id>&b=<job_id>` with full access control
- AMB-1 comment matching: type-first bucketing, token overlap threshold 2 (1 for stamps), Euclidean position tiebreak
- Status classification: `resolved` / `unchanged` / `new`
- Sheet diff from structural fingerprints; EPR check diff (changed statuses only)
- `comparison_json` cached on job_b, invalidated when `completed_at > computed_at`
- Tab-based template: Comments (with filter buttons), Sheets, EPR Changes
- "Compare ↔" button on v2+ cards in grouped view

### Phase F1: Stats Banner (`web/plan_jobs.py`, `analysis_history.html`)
- `get_analysis_stats()`: monthly count, avg processing time (seconds), distinct projects tracked
- Banner rendered above filter chips: "12 analyses this month | Avg processing: 1m 30s | 3 projects tracked"

### Phase F2: Project Notes (`web/plan_notes.py`, DB migrations)
- `project_notes` table: free-text per `(user_id, version_group)`
- `GET/POST /api/project-notes/<version_group>` JSON endpoints
- Collapsible notes widget in grouped view (with 60-char preview in header)
- Notes also editable from the comparison page

### Phase F3: Visual Comparison (`analysis_compare.html`, `web/app.py`)
- `GET /api/plan-sessions/<session_id>/pages/<n>/image` — serves stored PNG with ownership check
- Visual tab on compare page: side-by-side layout + overlay mode with opacity slider
- Page selectors for V1 and V2 independently; lazy loads on tab open

### Phase F4: Revision Extraction Display (`analysis_compare.html`)
- Compare route extracts `title_block.revisions` from page_extractions, deduplicates by `(revision_number, revision_date)`
- Side-by-side "V1 Revision History" / "V2 Revision History" tables displayed below the version chain timeline

### Tests
- 66 new passing tests (17 E1, 26 E2, 23 F); full suite 1222 passed, 18 pre-existing errors unchanged

---

## Session 43 — Intent Router + Portfolio Health + What Changed (2026-02-20)

Three fixes: email-style queries now route to AI draft response instead of wrong search tools; expired permits no longer noise up portfolio health; "What Changed" shows actual permit details.

### Intent Router — `src/tools/intent_router.py`
- **Priority 0: Conversational detection**: Multi-line messages with greetings/signatures, or greeting + long text, now route to `draft_response` BEFORE keyword-based searches (complaint, address, analyze). Previously, pasting an email like "Hi, we got a notice about a complaint..." would match "complaint" at Priority 2 and do a complaint search instead of answering the question.
- **Signature detection**: Recognizes em-dash signatures ("— Karen"), sign-offs ("regards,"), mobile signatures.
- **Multi-line + greeting/signature → always draft**: 3+ lines with a greeting or signature is definitively an email, not a search.
- **All 73 existing tests pass** + new scenarios verified: kitchen remodel email → draft, Karen complaint email → draft, short "complaints at 4521 Judah" → still complaint search.

### Portfolio Health — `web/portfolio.py`, `web/brief.py`
- **Active site + expired permit → ON_TRACK**: If property has recent activity (≤90d) or other active permits, expired permits are administrative, not an emergency. Previously showed BEHIND.
- **Stale site + expired permit → SLOWER**: Downgraded from AT_RISK to SLOWER (informational). Previously stayed AT_RISK.
- **Applied same fix to brief.py**: Property snapshot in morning brief uses same logic.

### "What Changed" — `web/brief.py`
- **Show actual permit details**: When a property has recent activity but no permit_changes log entry, now queries the permits table to find which specific permits changed. Shows permit number, type, and current status badge instead of generic "3d ago · 1 active of 2".
- **Fallback preserved**: If no specific permits can be identified, still shows the generic activity card.

---

## Session 42 — Plan Analysis UX Polish (2026-02-20)

Iterative UX fixes for the plan analysis workflow based on live testing.

### Navigation & Breadcrumbs
- **Results page breadcrumb**: Added "← Analysis History" link at top of all results pages (`plan_results_page.html`)
- **Processing page breadcrumb**: Added "← Analysis History" link above processing card so users aren't stranded
- **"Analyze Another Plan" fix**: Changed link from `/#analyze-plans` (home page) to `/account/analyses#upload` (analysis history page with upload form auto-opened). Added `#upload` hash detection to `analysis_history.html`.
- **Upsell link fix**: "Upload for Full Analysis" now also goes to `/account/analyses#upload`

### Auto-Redirect on Completion
- **HX-Redirect fix**: Replaced broken inline `<script>` in `analyze_plans_complete.html` with `HX-Redirect` response header in `plan_job_status()`. HTMX doesn't execute inline scripts in swapped content — `HX-Redirect` is the correct approach for HTMX polling → navigation.

### Processing Time & Estimates
- **Quick Check timestamps**: Now records `started_at` and `completed_at` around the `validate_plans()` call so duration displays in history cards
- **Mode-aware time estimates**: Processing page shows "Typical: 30–60 sec" for Compliance, "1–3 min" for AI Analysis, "2–5 min" for Full Analysis (was hardcoded "1–3 min" for all)

### Compliance Mode Speed
- **Gallery rendering optimization**: Compliance mode now renders only 3 gallery pages (matching the 3 analyzed pages) instead of all pages (up to 50). Cuts total processing time roughly in half for large PDFs.

### Files Changed
| File | Changes |
|------|---------|
| `web/app.py` | `make_response` import, `HX-Redirect` for completion, Quick Check timestamps, `datetime` import |
| `web/plan_worker.py` | Compliance gallery rendering limited to 3 pages |
| `web/templates/plan_results_page.html` | Breadcrumb nav to Analysis History |
| `web/templates/analyze_plans_processing.html` | Breadcrumb link to Analysis History |
| `web/templates/analyze_plans_results.html` | "Analyze Another Plan" → `/account/analyses#upload`; upsell link updated |
| `web/templates/analyze_plans_polling.html` | Mode-aware time estimates |
| `web/templates/analysis_history.html` | `#upload` hash auto-opens upload section |

---

## Session 41 — MCP Server Fixes + Infrastructure (2026-02-20)

Fixed MCP server connectivity for claude.ai and deployed separate MCP service on Railway.

### MCP Protocol Fix — `src/server.py`, `src/mcp_http.py`, `pyproject.toml`, `web/requirements.txt`
- **Root cause**: Standalone `fastmcp>=2.0.0` package produces incompatible Streamable HTTP responses (adds `mcp-session-id` headers, requires specific Accept headers) that claude.ai's MCP client cannot parse. Caused 12+ hour outage.
- **Fix**: Switched to `mcp[cli]>=1.26.0` (Anthropic's official package) — `from mcp.server.fastmcp import FastMCP` instead of `from fastmcp import FastMCP`. Same constructor pattern as Chief MCP server (proven compatible).
- Rewrote `src/mcp_http.py` as standalone HTTP transport entry point with all 22 tools registered directly.
- Updated `Dockerfile.mcp` CMD from uvicorn to `python -m src.mcp_http`.

### MCP Railway Service — `sfpermits-mcp-api`
- Deployed new Railway service (`sfpermits-mcp-api`) for MCP Streamable HTTP access from claude.ai.
- **MCP URL**: `https://sfpermits-mcp-api-production.up.railway.app/mcp`
- Health check at `/health` returns tool count and server status.
- Separate from Flask web app (WSGI) since MCP requires ASGI transport.

### Bug Fixes
- **Zoning cross-check NoneType fix** — `_get_consensus_address()` in `analyze_plans.py` now handles `None` values from vision extractions using `(pe.get("project_address") or "")` instead of `pe.get("project_address", "")`.
- **Defensive event loop setup** — Added `asyncio.set_event_loop(loop)` in `plan_worker.py` background thread for compatibility with code that calls `asyncio.get_event_loop()`.

### Docs
- Updated `CLAUDE.md` with MCP service URL, connection instructions, and `mcp[cli]` vs `fastmcp` guidance.
- Pushed Phase D-F spec (`SPEC-analysis-history-phases-d-f.md`) to chief-brain-state for claude.ai access.

### Tests
696 passed, 1 skipped (pre-existing `src.plan_images` module issue).

---

## Session 40 — Analysis History Page: UX Overhaul Phases A-C (2026-02-20)

Major UX improvements to the Plan Analysis History page (`/account/analyses`), implementing Phases A through C of the three-role-reviewed plan.

### Phase A: Inline Upload + Duration Fix
- **Inline upload form**: "+ New Analysis" button now expands a collapsible upload form directly on the history page (no more navigation to home page). Includes drag-and-drop, all 4 analysis modes (Quick/Compliance/AI/Full), and "More options" for address/permit/stage fields.
- **Duration fix**: Cards now show actual processing time (`completed_at - started_at`) instead of queue+processing time (`completed_at - created_at`), with fallback for older jobs.
- **Live elapsed timer**: Processing jobs show a live-updating timer ("Processing for 42s...") using `setInterval`.
- **`started_at` in queries**: Added `started_at` to `get_user_jobs()` and `search_jobs()` SELECT statements.

### Phase B: Bulk Delete + Sort Controls
- **Bulk delete endpoint**: `POST /api/plan-jobs/bulk-delete` — accepts `job_ids` array, enforces ownership, caps at 100 items.
- **`bulk_delete_jobs()`**: New function in `plan_jobs.py` with parameterized IN clause and audit logging.
- **Sort controls**: 5 sort options (Newest, Oldest, Address A-Z, Filename A-Z, Status) via `order_by` parameter on `get_user_jobs()`. SQL injection prevented via allowlist mapping.
- **View options bar**: Sort dropdown and Group toggle rendered below filter chips (via grouping macros).

### Phase C: Project Grouping + Accordion View
- **Address normalization**: `_normalize_address_for_grouping()` strips unit/apt, then street type suffixes (ST/AVE/BLVD/etc). "1953 Webster St" and "1953 WEBSTER STREET" correctly group.
- **Filename normalization**: `_normalize_filename_for_grouping()` strips .pdf, version suffixes (-v2, _rev3, _final), date suffixes, copy markers.
- **`group_jobs_by_project()`**: Groups jobs by normalized address (preferred) or filename. Computes version numbers, date ranges, latest status per group.
- **Accordion grouped view**: New `fragments/analysis_grouping.html` with Jinja2 macros for grouped layout — project rows with expand/collapse, version badges (v1, v2...), date range display.
- **Flat view version badges**: In flat view, cards show "1 of 4 scans" badge when part of a multi-scan project.
- **"Group by Project" toggle**: Persists via URL query param (`?group=project`).

### Files Changed
| File | Changes |
|------|---------|
| `web/app.py` | +124 lines: normalization helpers, `group_jobs_by_project()`, bulk-delete endpoint, sort/group params in route |
| `web/plan_jobs.py` | +45 lines: `bulk_delete_jobs()`, `order_by` param with 5 sort options, `started_at` in SELECT |
| `web/templates/analysis_history.html` | +618 lines: inline upload form, duration fix, live timer, view options bar, group_mode conditional, version badges |
| `web/templates/fragments/analysis_grouping.html` | NEW: Jinja2 macros for grouped view CSS, HTML, JS |

### Tests
1,103 passed, 1 skipped (pre-existing `src.plan_images` module issue in test_plan_images.py/test_plan_ui.py).

## Session 38f — Admin Ops QA Bug Fixes (2026-02-22)

Fixes from Cowork QA of Sessions 38d/38e. 4 of 6 Admin Ops tabs had infinite spinners, hash routing was broken, and severity scoring missed active holds.

### P0: Admin Ops Infinite Spinner Fix — `web/app.py`, `web/templates/admin_ops.html`
- **Bug**: 4 of 6 Admin Ops tabs (Data Quality, User Activity, Feedback, LUCK Sources) showed infinite "Loading..." spinner. Only Pipeline Health (which had a SIGALRM timeout) and Regulatory Watch loaded.
- **Root cause 1**: No server-side timeout on 4 tabs — slow DB queries could hang indefinitely until gunicorn killed the worker.
- **Root cause 2**: Only `htmx:responseError` was handled (HTTP errors). Network-level failures (`htmx:sendError`) and timeouts (`htmx:timeout`) left the spinner running.
- **Root cause 3**: Initial page load used `htmx.trigger(btn, 'click')` which fired before HTMX finished processing the DOM.
- **Fix**: All 6 tabs now share a 25s SIGALRM timeout with graceful fallback. Added 30s client-side HTMX timeout (`htmx.config.timeout`), `htmx:sendError` and `htmx:timeout` event handlers. Deferred initial tab load via `setTimeout(fn, 0)`.

### P1: Hash-to-Tab Mapping Fix — `web/templates/admin_ops.html`
- **Bug**: `/admin/ops#luck` and `/admin/ops#pipeline` showed wrong tabs. `#luck` didn't match any `data-tab` value (button uses `sources`).
- **Fix**: Added hash aliases (`luck→sources`, `dq→quality`, `watch→regulatory`). The "wrong tab" issue for `#pipeline` was actually the initial-load race (P0 fix).

### P2: Severity Hold Bug — `web/brief.py`
- **Bug**: 532 Sutter showed ON TRACK despite having a hold at PPC + 3 stalled stations. The hold upgrade only fired when `worst_health < at_risk`, but an expired permit had already set it to `at_risk`. Then post-processing saw "permit expired" and downgraded to `on_track` (≥5 active permits).
- **Fix**: Active holds now always set the health reason (overwriting expired-permit reason). Post-processing explicitly skips properties with held stations or open enforcement.

### P2: What Changed Timestamps — `web/templates/brief.html`
- Permit status transition entries now show `change_date` alongside the status badges.

### Tests
- 1,103 passed, 1 skipped

---

## Session 38e — Pipeline Timeout + DQ Sort + Activity Detail + Severity Brainstorm (2026-02-20)

### Pipeline Health Timeout — `web/app.py`
- **Bug**: Pipeline Health tab triggered 6+ heavy SQL queries against 3.9M-row addenda table, taking 30-120s and often timing out (gunicorn kills at 120s).
- **Fix**: Added 30s SIGALRM timeout guard around Pipeline Health queries. On timeout, returns graceful HTML fallback ("Pipeline Health is loading slowly...") instead of crashing the worker.
- **Long-term**: Spec written for materialized views (Task #120, `specs/pipeline-health-materialized-views.md`) — nightly pre-compute into 4 summary tables.

### DQ Dashboard: Sort Problems First — `web/data_quality.py`
- DQ check results now sort red → yellow → green so problems surface at the top.
- Skip prod-only checks (cron_log, permit_changes, knowledge_chunks) when running on DuckDB — eliminates 5 false "Error" cards in local dev.

### Brief: Specific Permit Activity — `web/brief.py`, `web/templates/brief.html`
- **Before**: What Changed activity entries showed generic "Activity 3d ago" with no context.
- **After**: Activity entries now display permit number, status badge (FILED/ISSUED/etc), and permit type description. Users can see *what* changed, not just *that* something changed.
- Added `latest_permit`, `latest_permit_status`, `latest_permit_type` tracking per property.

### Severity Brainstorm: "Incomplete" Tier (not yet implemented)
- Identified that BEHIND/AT_RISK labels create noise for permits that are administratively incomplete but not urgent (expired permit on an active site, long plan check with recent activity).
- Proposed new `incomplete` tier with neutral blue/gray styling — signals "needs admin attention eventually" without alarm.
- Collapsible rendering to prevent noise: "4 incomplete" summary line vs showing all cards.
- **Decision pending** — implement or defer.

### Checkmark Dismiss Buttons (decision pending)
- Brainstormed whether ✓ dismiss buttons on What Changed cards are worth keeping. Currently client-side only (no persistence). Options: persisted reviewed state, acknowledge+snooze, convert to action items, or remove entirely.

### Tests
- 1,103 passing, 1 skipped

---

## Session 38d — Regulatory Watch Fix + Severity Busy-Site Dismiss + Demo Seeding (2026-02-20)

### Regulatory Watch Tab Fix — `web/templates/admin_regulatory_watch.html`, `web/templates/admin_ops.html`
- **Bug**: Regulatory Watch tab showed infinite "Loading..." spinner. Root cause: local dev server was running from stale `cool-pike` worktree that predated the admin ops hub entirely (routes returned 404). Additionally, no HTMX error handler existed — failed fragment requests left the spinner running forever.
- **Fix 1**: Namespaced all CSS classes with `rw-` prefix to prevent style collisions in fragment mode. Moved global resets (`*`, `body`) into standalone-only block.
- **Fix 2**: Added `htmx:responseError` handler to admin_ops.html — failed tab loads now show "Failed to load tab" with reload link instead of infinite spinner.

### Severity: Dismiss Expired Permits at Busy Sites — `web/brief.py`, `web/portfolio.py`
- **Bug**: 188 The Embarcadero showed "BEHIND" for 1 expired permit despite having 47 active permits (222 total). Properties with heavy active permit loads shouldn't flag on a single old expiration.
- **Fix**: Added ≥5 active permits tier — properties with ≥5 active permits and an expired permit are dismissed to `on_track` (not flagged at all). 2-4 active → `behind`. <2 active + no recent activity → `at_risk`.

### Regulatory Watch Demo Seeding — `web/app.py`
- New `/cron/seed-regulatory` endpoint (CRON_SECRET auth) accepts JSON array of watch items for bulk creation.

### RAG Chunk Deduplication Fix — `.github/workflows/nightly-cron.yml`, `web/app.py`
- **Bug**: knowledge_chunks grew 9x (1,012 → 9,011) because nightly workflow ran `tier=all&clear=0`, appending all chunks without clearing.
- **Fix**: Changed nightly workflow to `tier=ops`. Made `/cron/rag-ingest` default to `clear=true` for static tiers (tier1-4, all). Cleaned prod back to 2,684 chunks.

### What Changed Activity Badge Fix — `web/templates/brief.html`
- **Bug**: Activity entries in What Changed showed health reason badge ("PERMIT EXPIRED 378D AGO (ACTIVE SITE)") instead of recency.
- **Fix**: Activity entries now show "Activity 3d ago" badge with neutral styling.

### Tests
- 1,103 passing, 1 skipped

## Session 39 — Plan Analysis: Multi-Role Evaluation Sprint (2026-02-20)

9-role professional evaluation of analyze_plans output using real 12-page plan set (1953 Webster St). Fixed trust-breaking false positives and restructured report output for professional workflows.

### P0-1: Multi-Address False Positive Fix — `src/vision/epr_checks.py`, `web/plan_worker.py`
- **Bug**: EPR-017 reported FAIL with 9 different addresses — all were reference stamps from the firm's template, not actual address mismatches.
- **Fix**: `_assess_consistency()` now accepts `known_address` parameter. When user provides property address at upload, matching addresses downgrade from FAIL → INFO with explanation.
- Threaded `property_address` through: `web/plan_worker.py` → `analyze_plans()` → `run_vision_epr_checks()` → `_assess_consistency()`

### P0-2: Multi-Firm False Positive Fix — `src/vision/epr_checks.py`
- **Bug**: EPR-017 reported multiple firms ("EDG Collective", "Erik Schlicht Design") — OCR variants of the same firm.
- **Fix**: Added `_normalize_firm()` (strip suffixes: Inc, LLC, Architects, Design, Collective, Studio) and `_firms_match()` (token overlap scoring — 2+ shared words = same firm).

### P0-3: Categorized Comment Summary — `src/tools/analyze_plans.py`
- Replaced flat by-page comment dump with structured categorization
- 10 categories: Fire Safety/Rating, Property Line/Setback, Missing Sheets, Insulation/Energy, Natural Light/Ventilation, Mechanical/BBQ, Structural, Electrical/Lighting, Drawing Corrections, General
- Each category has priority level (must_fix / review / informational) and discipline routing
- Summary table at top with counts by category → comments grouped by category (not page) → collapsible by-page view in `<details>` tag
- Added `_categorize_comments()` and `_pair_comments_with_responses()` (page+position proximity matching)

### P0-4: Submission Stage Label — `web/templates/index.html`, `web/app.py`, `web/plan_jobs.py`, `web/plan_worker.py`, `src/tools/analyze_plans.py`
- New "Submission Stage" dropdown in upload form: Preliminary / Permit Application / Resubmittal
- Preliminary mode downgrades EPR-012, EPR-018, EPR-019 from FAIL/WARN → INFO with banner note
- `submission_stage` column added to `plan_analysis_jobs` table (auto-migrated)

### P0-5: Missing Sheet Comparison — `src/vision/epr_checks.py`, `src/tools/analyze_plans.py`
- EPR-011 now stores `sheet_index_entries` in `page_details` on FAIL
- New "Sheet Completeness" section in report: cover index vs actual PDF comparison
- Missing sheets highlighted with ❌, extra/unlisted sheets with ⚠️

### P1-2: Plain-English Executive Summary — `src/tools/analyze_plans.py`
- New "What This Means for Your Project" section after executive summary
- Counts actionable items, separates formatting vs design issues
- Timeline estimates, no acronyms, homeowner-friendly language

### Tests
- 1,103 passed, 1 skipped (pre-existing `plan_images` module error unchanged)
- 79 analyze_plans + EPR-specific tests all pass

### Files Changed (6 files, +522 / -24)
- `src/tools/analyze_plans.py` — P0-3, P0-4, P0-5, P1-2
- `src/vision/epr_checks.py` — P0-1, P0-2, P0-5
- `web/app.py` — P0-4 (form field + DB migration)
- `web/plan_jobs.py` — P0-4 (submission_stage in create/get)
- `web/plan_worker.py` — P0-1, P0-4
- `web/templates/index.html` — P0-4 (dropdown)

---

## Session 38c — Brief Fixes + DQ Calibration + Severity Expansion (2026-02-20)

### Brief "What Changed" Count Fix — `web/brief.py`, `web/templates/brief.html`
- **Bug**: Summary card showed "9 Changed" but What Changed section only listed 2 items. The count used property-level `days_since_activity` (from SODA `status_date`) while the section showed only sparse `permit_changes` detection log entries.
- **Fix**: Merge property-level activity into the changes list. Properties with recent `status_date` updates that aren't already in `permit_changes` get added as "activity" entries showing health reason, active/total permit counts, and days since activity.
- Template updated with two rendering paths: status transitions (FILED → ISSUED) for detection log entries, and health-reason cards for property-level activity entries.
- Added CSS for health-status badges (`status-on_track`, `status-behind`, `status-at_risk`, etc.)

### Brief Section Reorder — `web/templates/brief.html`
- What Changed section moved ABOVE Your Properties (was below)
- Summary cards now filter property grid (click to toggle) instead of scrolling
- Property cards sorted changed-first, then by risk severity

### Severity Expansion: Multi-Active-Permit Downgrade — `web/brief.py`, `web/portfolio.py`
- **Bug**: 125 Mason showed red "AT RISK" for a permit expired 5,825 days ago (16 years!) despite having 3 active permits. The ≤30d activity window was too narrow — the site isn't abandoned, it just hasn't had SODA updates recently.
- **Fix**: Expand expired-permit downgrade from AT RISK → BEHIND when property has >1 active permit (not just ≤30d activity). Shows "(3 active permits)" suffix.
- Applied to both Brief property cards and Portfolio view.

### Data Quality Check Fixes — `web/data_quality.py`
- **Cron checks**: Fixed wrong column names (`run_date` → `started_at`, `records_fetched` → `soda_records`) to match actual `cron_log` schema. Added `job_type = 'nightly'` filter and `datetime.date()` conversion for timestamps.
- **Temporal violations**: Changed from absolute count threshold (red at 100) to percentage-based (green < 0.5%, yellow < 1%). 2,031 violations = 0.18% — normal for SODA data (permit amendments, OTC permits).
- **Orphaned contacts**: Recalibrated from red at 15% to green < 55%. 45.7% is expected — contacts dataset covers 3 permit types (building + electrical + plumbing) but permits table only has building permits.

### Admin Ops Default Tab — `web/templates/admin_ops.html`
- Changed default from Pipeline Health (slow — 6 heavy queries against 3.9M-row addenda table) to Data Quality (fast — lightweight count queries).

### Tests
- 1,103 passing, 1 skipped

---

## Session 38b — Brief UX Fixes + Admin Hub Consolidation (2026-02-20)

### Brief "Changed" Count Fix — `web/brief.py`
- Changed count now derived from property-level `days_since_activity` instead of sparse `permit_changes` detection log
- Property cards pass `lookback_days` to `_get_property_snapshot()` for consistent filtering

### Admin Hub Consolidation — 12 files
- `/admin/ops` rewritten as single-page HTMX hub with 6 lazy-loaded tabs: Pipeline Health, Data Quality, User Activity, Feedback, LUCK Sources, Regulatory Watch
- New `web/data_quality.py`: 10 live DQ checks (cron status, records fetched, changes detected, temporal violations, cost outliers, orphaned contacts, inspection null rate, data freshness, RAG chunks, entity coverage)
- Existing admin templates converted to fragment mode (`{% if not fragment %}` wrapper)
- Fragment route dispatcher: `GET /admin/ops/fragment/<tab>`
- Nav dropdown links updated to `/admin/ops#<tab>`
- Tab bar with loading pulse animation, hash-based URL bookmarking

---

## Session 38 — Nav Bug Fixes + Severity Scoring Fix (2026-02-20)

### Severity Scoring Bug Fix — `web/brief.py`, `web/portfolio.py`
- **Bug**: Expired permits on active sites still showed red "AT RISK" despite Session 37's severity refinement. Root cause: the `recently_active` check used **per-permit** `status_date` (age of that specific permit's last update), but properties show "Activity 3d ago" based on the **property-level** latest activity across ALL permits at the address. A property with 10 permits where the expired one hasn't been touched in 200d would show red AT RISK even though another permit was updated 3 days ago.
- **Fix**: Removed per-permit `recently_active` heuristic. Added property-level post-processing after `days_since_activity` is computed: if `worst_health == at_risk` AND `health_reason` mentions "permit expired" AND `days_since_activity <= 30`, downgrade to `behind` with "(active site)" suffix. This correctly treats expired permits at active sites as administrative paperwork (SFBICC §106A.4.4).

### Admin Ops Stub — `web/app.py`, `web/templates/admin_ops.html`
- Created `/admin/ops` route + template to resolve 404 on Pipeline Health and Data Quality links in admin dropdown
- Tabbed UI with hash-based switching (`#pipeline`, `#quality`)
- Pipeline tab links to existing `/dashboard/bottlenecks`; Data Quality shows "Coming in Phase B"

### Admin Back-Links Fixed — 4 templates
- `admin_activity.html`: "← Back to account" → `/account` changed to "← Home" → `/`
- `admin_feedback.html`: "← Back to account" → `/account` changed to "← Home" → `/`
- `admin_sources.html`: "Back to Admin" → `/admin/activity` changed to "← Home" → `/`
- `admin_regulatory_watch.html`: "← Dashboard" → `/brief` changed to "← Home" → `/`; logo also pointed to `/brief`, fixed to `/`

### Voice Calibration Moved to /account — `web/app.py`, templates
- New routes: `/account/voice-calibration`, `/account/voice-calibration/save`, `/account/voice-calibration/reset` — no admin check, open to all logged-in users
- Old `/admin/voice-calibration*` routes now 301/307 redirect to new URLs (backward-compatible)
- New `voice_calibration.html` template (same as admin version, no Admin badge, HTMX URLs updated)
- Removed Voice Calibration from admin dropdown in `nav.html`
- Removed admin/consultant gate from Voice & Style card in `account.html` — now visible to all users
- Updated account route to load `cal_stats` for all users (was admin/consultant only)

### Lookback Button Loading Pulse — `web/templates/brief.html`
- Brief lookback buttons (Today/7d/30d/90d) now show blue outline pulse animation on click while page reloads
- Matches nav badge loading behavior; already-active button won't animate

### Tests
- 1,103 passing, 1 skipped (pre-existing `plan_images` module errors unchanged)

---

## Session 37 — Severity Refinement + Brief UX Enhancements (2026-02-20)

### Permit Expiration Severity Refinement — `web/brief.py`, `web/portfolio.py`
- **Problem**: All expired/expiring permits showed as red "AT RISK" — even active construction sites where expiration is routine paperwork. This created false urgency and noise for Amy.
- **Research**: Reviewed SFBICC Section 106A.4.4 (Table B) — expired permits on active sites need a recommencement application (alteration permit for uncompleted work, no new plan review). Not an emergency.
- **New tiered logic** (both Brief property cards and Portfolio):
  - Expired + recent activity (≤30d): ⚠️ `behind` (yellow) — "permit expired Xd ago (active site)"
  - Expired + no recent activity (>30d): 🔴 `at_risk` (red) — genuinely stalled
  - Expiring ≤30 days: 🔴 `at_risk` (red) — urgent, file extension now
  - Expiring 31–90 days: ⚠️ `behind` (yellow) — file extension soon
  - Expiring 91–180 days: 💛 `slower` (light yellow) — on the horizon
- **CSS consistency fix**: `behind` state was styled with red dot/text but yellow border — now fully yellow across all elements (dot, text, badge, progress bar, health reason) in both `brief.html` and `portfolio.html`

### 90-Day Lookback — `web/app.py`, `web/templates/brief.html`
- Extended maximum lookback from 30 days to 90 days (clamped at `max(1, min(90))`)
- Added 90-day toggle button to Brief lookback filter bar
- Updated empty-state text references from 30 to 90

### Clickable Summary Cards — `web/templates/brief.html`
- Summary card numbers (Properties, Changed, Inspections, Expiring) now clickable
- Click scrolls to the relevant section with a 1.5s highlight flash
- Added `data-target` attributes and section `id` anchors
- Hover cursor and subtle scale transition on clickable cards

### Tests
- Updated `test_brief_lookback_clamped` to expect "90 days lookback" (was 30)
- All 1,103 tests passing (18 pre-existing errors from missing `src.plan_images` module unchanged)

---

## Session 36 — UX Redesign Phase A: Nav + Admin Context (2026-02-20)

### UX Audit
- Full audit of Brief, Portfolio, and Pipeline features as senior UX/IA review
- Identified Brief's property_cards section as primary redundancy with Portfolio
- Confirmed Pipeline is admin-only territory (Amy doesn't use it)
- Produced spec: `specs/ux-redesign-nav-brief-portfolio-admin.md` in chief brain state

### Nav Redesign (Spec 1) — `web/templates/fragments/nav.html`
- Removed Pipeline link from main nav (was visible to all users, confusing for Amy)
- Added admin-only `⚙️ Admin ▾` dropdown with 6 links: Pipeline Health, Data Quality, User Activity, LUCK Sources, Voice Calibration, Regulatory Watch
- `/admin/ops#pipeline` and `/admin/ops#quality` are intentional dead links (Phase B)
- Dropdown uses CSS hover + `:focus-within` (no JS dependency)
- Amy's nav: `Search | Brief | Portfolio | My Analyses | account | Logout`
- Tim's nav: same + `⚙️ Admin ▾` dropdown before account

### Admin Context Badges — 6 admin templates
- Added `⚙ Admin` pill badge to `<h1>` in: Activity Feed, Feedback Queue, LUCK Sources, Regulatory Watch, Voice Calibration, Pipeline Bottlenecks
- Visual signal so Tim knows he's on an admin page

### Tests
- Updated `test_velocity_dashboard_in_nav` → `test_velocity_dashboard_hidden_from_non_admin` (asserts Pipeline NOT in nav for regular users)
- Added `test_velocity_dashboard_in_admin_dropdown` (asserts admin dropdown with Pipeline link appears for admin users)
- 1,103 passing, 0 failures (18 pre-existing errors from missing `src.plan_images` module)

### Already Implemented (confirmed during audit)
- Brief lookback filter buttons already at top of page (lines 247–251 of brief.html)
- Data freshness banner already exists (lines 239–244 of brief.html, computed from `cron_log`)

---

## Session 35 — Pipeline Dashboard, Filters, Reviewer Drill-down (2026-02-20)

### Morning Brief Fixes

#### Property Card Deduplication (`web/brief.py`)
- All property cards showed "125 MASON ST" — root cause was grouping by block/lot while 125 Mason spans 3 lots (0331/018, 003, 004)
- Fixed by grouping by normalized address (uppercased street_number + street_name + suffix) as primary key
- Added `street_suffix` to SQL query (was missing, causing "125 Mason" instead of "125 Mason St")
- Added `parcels: set()` per address card, tracking all block/lot pairs for enforcement queries
- Watch label matching changed to `startswith` (watch items don't store suffix)
- `parcels` set converted to `parcels_display` string ("0331/003, 0331/004, 0331/018") before render

#### Portfolio Nav in Morning Brief (`web/templates/brief.html`)
- Brief page had hardcoded header missing Portfolio link
- Replaced hardcoded header with `{% include 'fragments/nav.html' %}`, removed duplicate CSS
- Added `active_page='brief'` to route

### SODA Staleness Improvements (`scripts/nightly_changes.py`, `web/app.py`)

#### Auto-retry on Zero Records
- When 0 permits returned with 1-day lookback, automatically retries with 3-day window
- On retry success, logs "SODA data lag detected — likely holiday/weekend" instead of alerting
- Distinguishes holiday/weekend lag (expected) from real API outages (needs alert)

#### Admin Staleness Email Alerts
- `_send_staleness_alert()` in `web/app.py` — sends plain text email to all admins
- Three severity tiers: ⚠️ Warning (permits=0 but others ok), 🚨 Alert (multiple tables empty), 🚨🚨 Critical (everything empty after retry)
- Triggered at end of `POST /cron/nightly` when staleness detected

### RAG Fix (`src/rag/retrieval.py`)
- Fixed `KnowledgeBase()` called with no args in two places — caused WARNING on Railway
- Changed to `get_knowledge_base()` singleton which resolves `data_dir` correctly

### Pipeline Bottleneck Dashboard (`web/velocity_dashboard.py`, `web/templates/velocity_dashboard.html`)
**New page at `/dashboard/bottlenecks`** — DBI approval pipeline heatmap for plan review velocity

#### Station Velocity Heatmap
- Color-coded station cards by health tier: fast (green) / normal (blue) / slow (amber) / critical (orange) / severe (red)
- Shows median days, p90, sample count, pending count per station
- Sorted slowest-first for immediate triage

#### Filter Bar (client-side, instant)
- **View: All Stations / My Portfolio** — Portfolio mode filters to only stations where user's watched permits are currently pending (queries `addenda` for live plan-check status)
- **Dept filter** — dynamic from real data (DBI / CPC / SFFD / DPW / etc.), filters heatmap cards
- **Speed: All / 🔴 Bottlenecks only** — hides fast/normal, shows slow/critical/severe
- Portfolio stations get blue glow ring + `MINE` badge even in All view
- Stalled Permits tab also filters in Portfolio mode; `Mine` badge on user's stalled rows

#### Reviewer Drill-down
- Click any station card → modal drawer with per-reviewer velocity stats
- Shows median/avg turnaround, completed reviews, pending count per plan checker
- Reviewer median colored by health tier (fastest → slowest)
- `GET /dashboard/bottlenecks/station/<station>` JSON endpoint (login-required)
- `get_reviewer_stats()` in `velocity_dashboard.py` — 90-day lookback, min 2 reviews, sorted fastest-first, capped at 20
- Escape key + backdrop click close drawer

#### Department Rollup, Stalled Permits, Station Load tabs
- Stalled permits: 14+ day pending with no finish_date, shows hold reason + reviewer
- Station load: current pending count, held count, avg wait days
- Dept rollup: station count, avg median, slowest station per agency

### `list_feedback` MCP Tool (`src/tools/list_feedback.py`)
- New tool: query feedback queue from Claude sessions
- Filters: status, feedback_type, days_back, limit, include_resolved
- Returns markdown table with summary counts + truncated message preview
- Registered in `src/server.py` as Phase 6 operational intelligence tool

### Navigation (`web/templates/fragments/nav.html`)
- Added "Pipeline" link to shared nav (between Portfolio and My Analyses)

### Tests
- 23 tests in `tests/test_velocity_dashboard.py` (all passing)
- 1,004 passing total (7 pre-existing failures unrelated to this session)

---

## Session 34 — Tier 0 Operational Intelligence (2026-02-19)

### Concept
Introduced "Tier 0: Operational Intelligence" — a new knowledge layer derived from live data (3.9M addenda routing records) rather than static files. While existing tiers answer "what are the rules?" (Tier 1-3) and "what does Amy know?" (Tier 4), Tier 0 answers "what's happening right now?" across the entire permitting pipeline.

### Phase A: Activity Surface (DEPLOYED)

#### Addenda Activity in 30-Day Banner (`src/tools/permit_lookup.py`)
- New `_get_recent_addenda_activity()` function queries plan review completions across watched permits
- Enhanced `_summarize_recent_activity()` with 4th category: "🗂️ Plan reviews completed"
- Plan review activity displays first (most actionable), grouped by approved/comments/other

#### Routing Progress in Intel Panel (`web/app.py` + `web/templates/search_results.html`)
- Section 5 added to `_get_address_intel()`: finds primary active permit, gets latest addenda revision, counts total/completed stations
- Progress bar in Permits column: color-coded (green=100%, blue≥50%, amber<50%)
- Latest station name + approval/comment indicator

### Phase B: Pattern Detection

#### 6 Addenda Intelligence Rules (`web/intelligence.py`)
- **Rule 9: Station Stall** — routing step arrived >30 days ago with no finish/hold (critical >60d)
- **Rule 10: Hold Unresolved** — routing hold present with no completion
- **Rule 11: All Stations Clear** — all routing stations completed (celebration trigger)
- **Rule 12: Fresh Approval** — station approved within last 7 days
- **Rule 13: Comment Response Needed** — station issued comments, not yet resolved
- **Rule 14: Revision Escalation** — permit on addenda ≥3 (complex revision pattern)
- Each rule independently fault-tolerant with own try/except

#### Routing Completion Tracker (`web/routing.py`)
- **NEW FILE**: `StationStatus` + `RoutingProgress` dataclasses
- Computed properties: `completion_pct`, `is_all_clear`, `stalled_stations`, `held_stations`, `days_pending`
- `get_routing_progress()` — single permit detailed routing state
- `get_routing_progress_batch()` — batch query for portfolio dashboard efficiency

### Phase C: Knowledge Materialization

#### 8 Operational Concepts in Semantic Index (`data/knowledge/tier1/semantic-index.json`)
- Extended from 92 → 100 concepts
- New concepts: plan_review_velocity, station_bottleneck, reviewer_patterns, revision_cadence, routing_completion, hold_resolution, plan_review_timeline, station_routing
- Each has `data_freshness` field distinguishing live vs static sources

### Data Exploration Report (`docs/ADDENDA_DATA_EXPLORATION.md`)
- Comprehensive analysis of 3.9M addenda records via SODA API
- Key findings: 90.6% null review_results, PPC averages 174 days (6mo bottleneck), SFFD 24 days, 95% of rows are original routing (addenda #0)
- Station velocity baselines for 15 stations
- Feature implications documented (velocity dashboard, bottleneck alerts, addenda predictor, OTC detection)

### Phase D: Property Report + Velocity + RAG

#### Plan Review Routing in Property Report (`web/report.py` + `web/templates/report.html`)
- Enriches active permits with routing progress via `get_routing_progress_batch()`
- Shows color-coded progress bar (green=100%, blue≥50%, amber<50%), station counts
- Approved/comments breakdown, pending station names, stalled warnings (>14d)
- Latest activity with station name, result, and date

#### Station Velocity Baselines (`web/station_velocity.py`)
- **NEW FILE**: Rolling 90-day percentile baselines per plan review station
- `StationBaseline` dataclass: avg/median/p75/p90/min/max turnaround days
- PostgreSQL `station_velocity` table with `(station, baseline_date)` primary key
- `refresh_station_velocity()` — PERCENTILE_CONT aggregation with UPSERT
- DuckDB fallback for dev mode using MEDIAN()
- Wired into `/cron/nightly` as non-fatal post-processing step

#### Operational Knowledge Chunk Generator (`web/ops_chunks.py`)
- **NEW FILE**: Generates RAG chunks from live operational data (Tier 0 → pgvector)
- Station velocity chunks: one per station with natural language turnaround stats + summary ranking
- Routing pattern chunks: station volume rankings, addenda cycle counts, result distributions
- System stats chunk: global operational overview
- Stored as `source_tier='learned'`, `trust_weight=0.7`, `source_file='ops-live-data'`
- Clears previous ops chunks before each refresh (no stale accumulation)
- Wired into both `/cron/nightly` and `/cron/rag-ingest?tier=ops`

### Files Changed (7 modified + 4 new)
- `src/tools/permit_lookup.py` — _get_recent_addenda_activity(), enhanced _summarize_recent_activity()
- `web/app.py` — Section 5 routing progress in _get_address_intel(); station velocity + ops chunks in nightly cron; ops tier in rag-ingest
- `web/templates/search_results.html` — Plan Review progress bar in intel panel
- `web/intelligence.py` — 6 new addenda-based rules (Rules 9-14)
- `web/report.py` — Routing progress enrichment for active permits
- `web/templates/report.html` — Plan Review Routing section in permit details
- `data/knowledge/tier1/semantic-index.json` — 8 operational concepts (92→100)
- `web/routing.py` — **NEW**: RoutingProgress tracker module
- `web/station_velocity.py` — **NEW**: Station velocity baseline computation
- `web/ops_chunks.py` — **NEW**: Operational knowledge chunk generator
- `docs/ADDENDA_DATA_EXPLORATION.md` — **NEW**: Data exploration report

### Commits
- Phase A deployed to production via `main` (merged earlier in session)
- `7e3d932` — T0-B1: 6 addenda intelligence rules
- `d54498c` — T0-C2: 8 operational concepts in semantic index
- `96ff7ab` — T0-B3: Routing completion tracker module
- `de08908` — T0-A3: Plan review routing in property report
- `8117905` — T0-B2: Station velocity baselines + cron wiring
- `8095cfb` — T0-C1: Operational knowledge chunk generator


### Chief Brain State
- New spec: `specs/tier-0-operational-intelligence-live-data-as-knowledge.md`
- New goal #4: Tier 0 Operational Intelligence (quarterly, P0)
- Tasks #83-91: T0-A1 through T0-C3

---

## Session 31 — Smart Address Card Enhancements (2026-02-18)

### Problem Solved
The address search result card showed a static "Analyze Project" button that posted a useless literal string, and a "Check Violations" button that looked identical whether there were 0 or 10 open violations — no incentive to engage.

### Solution: Rich Quick Actions + Go Button Pulse

#### Smart "Analyze Project" button (`web/app.py`, `web/templates/search_results.html`)
- New `_get_primary_permit_context()` helper queries the most recent permit at an address
- Button label shows real permit type + cost: **"🔍 Analyze: Additions + Repairs · $85K"**
- Hidden fields `estimated_cost` + `neighborhood` POST directly to `_ask_analyze_prefill()`
- `_ask_analyze_prefill()` updated to read those fields, pre-filling the cost analyzer form with real data
- Falls back to "🔍 Analyze Project" if no permit context available

#### Violations badge — 3 visual states (`web/app.py`, `web/templates/search_results.html`)
- New `_get_open_violation_counts()` helper counts open violations + complaints by block/lot
- **Red badge** when violations exist: "⚠️ Check Violations · 3 open"
- **Green** when clean: "✓ No open violations"
- **Neutral** when violations table not yet ingested (auto-activates when data lands)

#### Active businesses row (gated on data)
- New `_get_active_businesses()` helper fetches up to 5 active businesses at the address
- Green-tinted card shows business name, operating since year, and type flag (🅿️ Parking, 🏨 Short-term rental)
- Auto-activates when `businesses` table is populated

#### "Who's Here" 4th button (gated on data)
- Appears only when businesses data exists
- "🏢 Who's Here · 3 businesses" or "🏢 Who's Here · Acme Corp" for single business
- Routes to AI question about who operates at the address

#### Go button pulse (`web/templates/index.html`)
- One CSS rule: `form.loading .search-btn` gets a breathing opacity animation (0.9s) while `/ask` response is loading
- Reuses existing `@keyframes pulse` + `.loading` class already toggled by HTMX event listeners

#### More detail + sources (`web/app.py`, `web/templates/draft_response.html`)
- "Cite sources" button removed; "More detail" renamed to **"More detail + sources"**
- `more_detail` modifier instructions updated to include citation rules:
  - SF Planning Code + SFBC: formatted as AM Legal markdown hyperlinks (clickable end-to-end)
  - CBC, Title 24, ASCE 7: inline citations only (paywalled)

### Gating Strategy
All new data-dependent features (`_get_open_violation_counts`, `_get_active_businesses`) check table population with `SELECT COUNT(*) … LIMIT 1` and return `None`/`[]` silently when empty. Template guards ensure zero UI change until data lands — safe to ship before ingest completes.

### Tests
985 passing, 6 pre-existing failures (unrelated: test_auth watch edit routes, test_report URL format, test_web Plan Set Validator).

---

## Session 32 — Populate 4 New SODA Tables in Production (2026-02-18)

### Problem Solved
4 new tables (addenda, violations, complaints, businesses) existed in prod Postgres with schema but no data. Needed full SODA → DuckDB → Postgres population for the first time.

### Solution: Full SODA Ingest + Push to Prod

#### Data Ingested (SODA → local DuckDB)
- **addenda** (87xy-gk8d): 3,920,710 rows — ~82 min, 50K page / 100K batch flush
- **violations** (nbtm-fbw5): 508,906 rows — ~5 min
- **complaints** (gm2e-bten): 325,977 rows — ~4 min
- **businesses** (g8m3-pdis, active only): 126,585 rows — ~1.5 min

#### Data Pushed to Production Postgres
Used `scripts/push_to_prod.py` via `/cron/migrate-data` endpoint:
- violations: 56s (~9K rows/sec)
- complaints: 32s
- businesses: 14s
- addenda: ~7.5 min (3.9M rows)

#### push_to_prod.py Script (New)
- `scripts/push_to_prod.py` — CLI tool for pushing any of the 4 tables from local DuckDB to prod Postgres
- Usage: `python scripts/push_to_prod.py --table violations` or `--all`
- Reads DuckDB in 5K-row batches, POSTs to `/cron/migrate-data` with truncate-on-first-batch
- Requires `CRON_SECRET` env var (get full value via `railway run -- printenv CRON_SECRET`)

#### Production State After
```
addenda:       3,920,710 rows
violations:      508,906 rows
complaints:      325,977 rows
businesses:      126,585 rows
contacts:      1,847,052 rows (unchanged — extraction runs separately)
entities:      1,014,670 rows (unchanged)
relationships:   576,323 rows (unchanged)
permits:       1,137,816 rows (unchanged)
inspections:     671,359 rows (unchanged)
```

### Notes
- DuckDB is single-writer — ingest jobs must run sequentially, not in parallel
- Full ingest is a one-time cost; daily updates only fetch changed records (seconds to minutes)
- Bulk data (SODA-sourced) is fully recoverable from API; only user-generated data needs Railway backups

### Files Changed
- `scripts/push_to_prod.py` — **NEW**: DuckDB → prod Postgres push script

---

## Session 30 — Building Permit Addenda Routing + Nightly Change Detection (2026-02-18)

### Problem Solved
Amy discovered permit 202509155257 ($13M, 125 Mason St) showed "no changes" despite 25 active plan review routing steps across 10 agencies with approvals as recent as 2/18. Root cause: our nightly change detection only watched the top-level `status` field on the Building Permits dataset (`i98e-djp9`), which stayed "filed" throughout the multi-month plan review process.

### Solution: Ingest Building Permit Addenda + Routing Dataset (87xy-gk8d)

#### Database Schema
- **`addenda` table** — 18 columns storing station-by-station plan review routing data (DuckDB + PostgreSQL)
- **`addenda_changes` table** — nightly delta tracking with 4 change types: `new_routing`, `review_completed`, `review_updated`, `routing_updated`
- **6 indexes** on addenda table: application_number, station, reviewer, finish_date, composite app/addenda/step, primary_key

#### Ingestion Pipeline (`src/ingest.py`)
- `_normalize_addenda()` — field extraction with int conversion for addenda_number/step, whitespace stripping, empty→None
- `ingest_addenda()` — DELETE + re-insert pattern for 3.9M rows from SODA endpoint `87xy-gk8d`
- CLI: `python -m src.ingest --addenda`

#### Nightly Change Detection (`scripts/nightly_changes.py`)
- `fetch_recent_addenda()` — queries SODA for `finish_date > since OR arrive > since`
- `detect_addenda_changes()` — compares SODA records against local addenda table by `primary_key`, detects 4 change types
- `_upsert_addenda_row()` — keeps local addenda table current via insert/update
- Non-fatal error handling — addenda failures don't block permit/inspection processing

#### Permit Lookup Enhancement (`src/tools/permit_lookup.py`)
- **Plan Review Routing section** between Inspection History and Related Permits
- Summary stats: routing steps, station count, completed/pending counts
- Markdown table with Station, Rev, Reviewer, Result, Finish Date, Notes
- **DBI Permit Details link** — direct URL to `dbiweb02.sfgov.org` permit tracker

#### New MCP Tool: `search_addenda` (Phase 5, tool #21)
- Search local addenda table by permit_number, station, reviewer, department, review_result, date range
- Returns markdown table + review notes section
- Registered in `src/server.py`

#### Morning Brief + Email Brief
- **Plan Review Activity section** in `web/brief.py` — joins `addenda_changes` with `watch_items` (permit, address, parcel watches)
- Color-coded result badges: green (Approved), orange (Issued Comments), blue (Routed)
- Up to 10 items in email brief, 50 in dashboard brief
- Added to `has_content` check in email delivery

#### Report Links
- `ReportLinks.dbi_permit_details(permit_number)` — URL builder for DBI permit tracker detail page

### Files Changed (12 modified + 2 new)
- `src/db.py` — addenda + addenda_changes tables, 6 indexes
- `src/ingest.py` — _normalize_addenda(), ingest_addenda(), --addenda CLI flag
- `src/report_links.py` — dbi_permit_details() method
- `src/server.py` — register search_addenda tool
- `src/tools/permit_lookup.py` — _get_addenda(), _format_addenda(), DBI details link
- `scripts/nightly_changes.py` — fetch_recent_addenda(), detect_addenda_changes(), _upsert_addenda_row()
- `web/app.py` — addenda_changes table in PostgreSQL migrations
- `web/brief.py` — _get_plan_review_activity(), plan_reviews in get_morning_brief()
- `web/email_brief.py` — plan_reviews in render context + has_content check
- `web/templates/brief.html` — Plan Review Activity section
- `web/templates/brief_email.html` — Plan Review Activity section (inline styles)
- `tests/test_permit_lookup.py` — added _get_addenda mock entries
- `src/tools/search_addenda.py` — **NEW**: search_addenda MCP tool
- `tests/test_addenda.py` — **NEW**: 14 tests (normalization, formatting, search, brief integration)

### Commits
- `b6fc3aa` — feat: ingest building permit addenda routing + nightly change detection

## Session 30b — Ingest 3 New SODA Datasets + Contact Extraction (2026-02-18)

### New Dataset Ingestion
- **Notices of Violation** (nbtm-fbw5, ~509K rows): Violation tracking by property, joins to permits via block+lot and to complaints via complaint_number
- **DBI Complaints** (gm2e-bten, ~326K rows): Complaint lifecycle tracking, links to violations
- **Registered Business Locations** (g8m3-pdis, active only): Entity resolution enrichment — fetches only active businesses via SODA-level `location_end_date IS NULL` filter

### Addenda Ingestion Enhancement
- Memory-efficient batch INSERT with 50K page size + 100K row flush (for 3.9M rows)

### Contact Extraction
- Plan checkers from addenda routing -> contacts table (source='addenda', role='plan_checker')
- Business owners/DBAs from business registry -> contacts table (source='business', role='owner'/'dba')
- All new contacts participate in entity resolution cascade automatically

### Schema Changes
- 3 new DuckDB tables: `violations`, `complaints`, `businesses`
- 3 new PostgreSQL tables with matching schema + pg_trgm indexes on business names
- 12 new indexes on join columns (complaint_number, block/lot, etc.)

### Pipeline Updates
- CLI flags: `--violations`, `--complaints`, `--businesses`
- Extended `_fetch_all_pages()` with `where` and `page_size` parameters
- Pipeline ordering: new datasets ingest before contacts so extraction can read them
- Updated `ALLOWED_TABLES` for data migration endpoint

### Files Changed
- `src/db.py` — 3 new table DDL in `init_schema`, 12 new indexes in `_create_indexes`
- `src/ingest.py` — 3 DATASETS entries, 3 normalizers, 3 ingest functions, 2 contact extractors, memory-efficient addenda batching, updated `run_ingestion` + CLI
- `scripts/postgres_schema.sql` — 3 new table definitions with indexes
- `web/app.py` — updated `ALLOWED_TABLES`
- `tests/test_phase2.py` — 11 new tests (normalizers, schema, contact extraction)

## Session 29 — Voice Calibration, Plan Viewer UX, Vision Prompt Enhancement (2026-02-17)

### Voice Calibration System (Phase A)
- **Voice templates**: 15 scenario templates across 7 audience types × 8 situation types in `web/voice_templates.py`
- **Voice calibration CRUD**: `web/voice_calibration.py` — seed, save, reset, get calibration data
- **Database schema**: `voice_calibrations` table added to both Postgres and DuckDB
- **Admin page**: `/admin/voice-calibration` — cards grouped by audience, side-by-side template/rewrite textareas, save/reset per scenario, HTMX inline updates
- **Account page**: calibration progress indicator + link to calibration page
- **Quick-action buttons**: "Get a meeting", "Cite sources", "Shorter", "More detail" pills on AI responses in `draft_response.html`
- **Modifier handling**: `/ask` route accepts `modifier` param, `_synthesize_with_ai()` prepends modifier instructions

### Inline Draft Editing & Voice Settings
- **Inline contenteditable editing** on AI draft responses — Edit button makes draft editable, Save submits diff to `/feedback/draft-edit`, "Used as-is" sends positive signal to `/feedback/draft-good`
- **Voice style textarea** on account page — stored in `users.voice_style`, injected into `_synthesize_with_ai()` system prompt
- **Button styling**: consistent primary/outline styling across plan analysis and response UI

### Plan Viewer UX Improvements
- **Label collision avoidance**: `resolveCollisions()` iterative algorithm pushes overlapping annotation labels apart with leader lines to original positions
- **Lasso/rubber-band zoom**: Click-drag to select rectangular area, zoom to fit selection — toggle via ⬚ button or keyboard
- **Minimap**: Shows viewport position indicator when zoomed beyond 1.1x, updates on pan/zoom
- **Left-side legend panel**: Slide-out panel with per-annotation-type toggle checkboxes, color swatches, counts, Show All / Hide All buttons
- **Per-type visibility**: Individual annotation type toggles persisted to localStorage
- **Enhanced keyboard shortcuts**: +/- zoom, 0 reset, L legend panel, Escape cascades (lasso → legend → lightbox)
- **Pan/dblclick handlers**: Updated to respect lasso mode state

### Vision Prompt Enhancement
- **Reviewer comment pattern recognition**: Enhanced `PROMPT_ANNOTATION_EXTRACTION` with specific visual patterns — revision clouds/bubbles (green, red, blue wavy outlines), callout bubbles with leader lines, handwritten markings, delta/revision triangles, strikethrough marks, circled items
- **Priority boost**: Reviewer notes prioritized first in annotation extraction
- **Max annotations**: Bumped from 12 to 15 per page to avoid crowding out reviewer notes

### Files Changed
- `web/voice_templates.py` — NEW: 15 scenario templates, audience/situation definitions
- `web/voice_calibration.py` — NEW: CRUD + seed + stats for voice calibrations
- `web/templates/admin_voice_calibration.html` — NEW: admin calibration page
- `web/templates/draft_response.html` — inline editing, quick-action modifier buttons
- `web/templates/account.html` — voice style textarea, calibration progress link
- `web/templates/analyze_plans_results.html` — lasso zoom, minimap, legend panel, collision avoidance (+629 lines)
- `web/app.py` — voice calibration routes, modifier handling in `/ask`, DB schema
- `src/db.py` — `voice_calibrations` table in DuckDB schema
- `src/vision/prompts.py` — enhanced reviewer comment detection patterns
- `src/vision/epr_checks.py` — max annotations 12→15

### Commits
- `bae27f2` — feat: inline draft editing, voice settings, and button styling fixes
- `af55176` — feat: voice calibration system + quick-action response modifiers (Phase A)
- `5c41c54` — feat: plan viewer UX — lasso zoom, minimap, legend panel, label collision avoidance
- `44f8167` — feat: enhance vision prompt to recognize reviewer comment patterns

## Session 27 — FS-Series Fire Safety Knowledge + Cookie Hardening (2026-02-17)

### FS-Series Fire Safety Info Sheets (Task #46)
- **New tier1 file**: `fire-safety-info-sheets.json` — 7 DBI fire safety info sheets encoded from raw OCR tier2 text
  - **FS-01**: Combustible Roof Decks — 500 sqft max, WUI-listed materials, ASTM E-84 Class B
  - **FS-03**: R-3 4-Story Sprinkler Rules — addition = full building, alteration = area only
  - **FS-04**: Wood-Frame Construction Fire Safety — Pre-Fire Plan for 50+ units / 350K+ sqft
  - **FS-05**: Dwelling Unit Sprinkler Rules — R3→R2 conversion scenario matrix (Ord 43-14/49-14/30-15)
  - **FS-06**: Deck Fire Separation — 3ft R3, 5ft R2 from property line
  - **FS-07**: High-Rise Elevator Lobbies — 20-min/45-min doors, CBC exceptions don't apply
  - **FS-12**: ADU Fire Exemption — state law Gov Code 65852.2 overrides local sprinkler requirements
- **Semantic index**: 80 → 86 concepts, 817 aliases, 273 source references
  - 6 new concepts: `roof_deck_fire`, `dwelling_unit_sprinkler`, `wood_frame_construction_fire`, `deck_fire_protection`, `elevator_lobby_highrise`, `r3_sprinkler_4story`
  - 4 existing concepts updated with FS cross-references: `sprinkler_required`, `fire_department`, `high_rise`, `adu`
- **KnowledgeBase**: `fire_safety_info_sheets` attribute registered
- **15 new tests**, 174 knowledge tests passing

### Session Cookie Hardening
- `SESSION_COOKIE_SECURE = True` in production (HTTPS-only)
- `SESSION_COOKIE_HTTPONLY = True` (XSS protection)
- `SESSION_COOKIE_SAMESITE = "Lax"` (CSRF protection)
- Auto-detects prod vs dev via `RAILWAY_ENVIRONMENT` / `BASE_URL`

### Files Changed
- `data/knowledge/tier1/fire-safety-info-sheets.json` — NEW (7 FS sheets)
- `data/knowledge/tier1/semantic-index.json` — 6 new concepts, 4 updated
- `src/tools/knowledge_base.py` — fire_safety_info_sheets attribute
- `tests/test_knowledge_supplement.py` — 15 new FS tests
- `web/app.py` — cookie security settings

## Session 26 — Vision Timing, Token Usage & Cost Tracking (2026-02-17)

### Per-Call Timing & Token Tracking
- **`VisionCallRecord`** dataclass: records call_type, page_number, duration_ms, input/output tokens, success for every API call
- **`VisionUsageSummary`** aggregator: total calls, tokens, duration, with `estimated_cost_usd` property (Sonnet pricing: $3/$15 per MTok)
- `VisionResult.duration_ms` field wraps `time.perf_counter()` around each `client.messages.create()` call
- `_timed_analyze_image()` wrapper in epr_checks threads usage through all 5 vision callsites
- `run_vision_epr_checks` return changed from 3-tuple to 4-tuple: `(checks, extractions, annotations, usage)`

### Database Persistence
- New columns: `vision_usage_json TEXT`, `gallery_duration_ms INTEGER` on `plan_analysis_jobs`
- Full per-call JSON blob stored for every completed analysis (call breakdown, timing, tokens, cost)
- Gallery render timing captured separately

### User-Facing UI
- **Elapsed timer during polling**: "Elapsed: 1m 23s · Typical: 1–3 min" (server-computed from started_at)
- **Vision stats on results page**: "AI Vision: 14 calls · 42,300 tokens · ~$0.19 · 87s · Gallery: 3.2s"
- Stats only shown for Full Analysis jobs with vision data

### Tests
- 8 new tests for VisionCallRecord, VisionUsageSummary (aggregation, cost math, JSON serialization)
- Updated 3→4 tuple unpacking in all existing vision/analyze_plans tests
- 67 targeted tests pass, 956 full suite pass

### Files Changed
- `src/vision/client.py` — duration_ms, VisionCallRecord, VisionUsageSummary dataclasses
- `src/vision/epr_checks.py` — _timed_analyze_image wrapper, 4-tuple return, usage threading
- `src/tools/analyze_plans.py` — 4-tuple unpack, API Usage line in report header
- `web/plan_worker.py` — 4-tuple unpack, gallery timing, persist usage to DB
- `web/plan_jobs.py` — extended get_job() SELECT with new columns
- `web/app.py` — ALTER TABLE migrations, elapsed_s in polling, vision_stats in results
- `web/templates/analyze_plans_polling.html` — elapsed timer display
- `web/templates/analyze_plans_results.html` — vision stats line
- `tests/test_vision_client.py` — 8 new tests
- `tests/test_vision_epr_checks.py` — 4-tuple unpacking, usage assertions
- `tests/test_analyze_plans.py` — 4-tuple unpacking, mock updates

## Session 25 — Rebrand: Expediter → Land Use Consultant + LUCK (2026-02-17)

### Terminology Rename
- **"Expediter" → "Land Use Consultant"** across all user-facing UI, tools, knowledge base, and tests
- **LUCK branding**: Knowledge base referenced as "LUCK (Land Use Consultants Knowledgebase)" in user-facing contexts
- **Internal `KnowledgeBase` class** preserved — LUCK is user-facing only
- **Backward compatibility**: Old `/expediters` routes 301/308 redirect to `/consultants`; "expediter" kept as search alias in semantic index and intent router

### Core Python (6 files)
- `src/tools/recommend_consultants.py` — **NEW** (replaces `recommend_expediters.py`): `ScoredConsultant`, `recommend_consultants()`, `_query_consultants()`, `_format_recommendations()`
- `src/server.py` — updated import and tool registration
- `src/ingest.py` — role map value `"pmt consultant/expediter": "consultant"` (raw SODA key preserved)
- `src/tools/intent_router.py` — `PERSON_ROLES`, `_ROLE_TYPOS`, regex patterns updated; old terms map to `"consultant"`
- `src/tools/team_lookup.py` — parameter `consultant=`, label "Land Use Consultant"
- `src/tools/search_entity.py` — docstrings and entity_type enum updated

### Web Backend (3 files)
- `web/app.py` — routes `/consultants`, `/consultants/search`; form field `consultant_name`; legacy redirects from `/expediters`
- `web/report.py` — `_compute_consultant_signal()`, `_SIGNAL_MESSAGES` rebranded, return key `consultant_signal`
- `web/owner_mode.py` — `compute_extended_consultant_factors()`

### Templates (7 files)
- `web/templates/consultants.html` — **NEW** (replaces `expediters.html`)
- `web/templates/report.html` — section "Do You Need a Consultant?", all `.expeditor-*` CSS → `.consultant-*`
- `web/templates/report_email.html` — "Consultant Assessment" section
- `web/templates/brief.html` — "Find a Consultant" badge
- `web/templates/index.html` — "Land Use Consultant" form label
- `web/templates/invite_email.html` — cohort `"consultants"`, "land use consultants"
- `web/templates/account.html` — cohort option "Land Use Consultants (professional)", LUCK source link

### Knowledge Base (3 JSON files)
- `tier1/semantic-index.json` — canonical name "Land Use Consultant", old terms kept as aliases
- `tier1/permit-consultants-registry.json` — field names updated, raw SODA values preserved
- `tier1/remediation-roadmap.json` — all "permit expediter" → "land use consultant" (~10 edits)

### LUCK Branding (5 files)
- `web/templates/account.html` — "LUCK (Land Use Consultants Knowledgebase) sources"
- `web/templates/admin_sources.html` — title "LUCK Sources", heading "LUCK Source Inventory"
- `web/templates/admin_regulatory_watch.html` — "may affect LUCK"
- `src/tools/revision_risk.py` — "LUCK-based assessment"
- `src/tools/estimate_timeline.py` — "LUCK-based estimates"

### Tests & Scripts (8 files)
- `tests/test_report.py` — `TestConsultantSignal`, `_compute_consultant_signal`
- `tests/test_owner_mode.py` — `TestExtendedConsultantFactors`
- `tests/test_intent_router.py` — role assertions → `"consultant"`
- `tests/test_team_lookup.py` — `consultant="Consultant C"`, "Land Use Consultant"
- `tests/test_web.py` — `"consultant_name"` assertion
- `tests/test_auth.py` — cohort `"consultants"`, "Land Use Consultants (professional)"
- `tests/test_sources.py` — "LUCK Source Inventory" assertion
- `scripts/feedback_triage.py` — `"/consultants": "Find a Consultant"`
- `scripts/add_user_tables.sql` — comment updated

### Documentation (3 files)
- `CHANGELOG.md` — this entry
- `data/knowledge/SOURCES.md` — "DBI Consultant Rankings"
- `data/knowledge/INGESTION_LOG.md` — terminology updates

### Production DB Migration (run manually)
```sql
UPDATE contacts SET role = 'consultant' WHERE role = 'expediter';
UPDATE entities SET entity_type = 'consultant' WHERE entity_type = 'expediter';
```

### Stats
- **~35 files changed**, 213 insertions, 986 deletions
- **949 tests passing** (7 pre-existing failures, 18 pre-existing errors — all unrelated)

## Session 24 — Annotation Polish, Legend, Reviewer Notes & Timeout Fix (2026-02-17)

### Critical Fix: Full Analysis Timeout
- **Root cause**: Gunicorn 300s worker timeout killed vision analysis (8+ min for 12-page PDF with 13+ API calls)
- **Fix**: Route ALL Full Analysis through async background worker (was only >10MB files)
- Removed ~95 lines of dead sync Full Analysis code from `web/app.py`
- Added user-visible error message to HTMX error handler (was silent failure — user saw "nothing appeared")

### Annotation UX Polish
- Button label: "Full Analysis" → "Full Analysis (AI Markup)"
- Updated subtitle and added feature hint below buttons promoting AI-powered annotations
- "AI Annotations" badge on analysis history cards for completed Full Analyses
- Annotation count in results page header (e.g., "· 24 annotations")
- **Color collisions fixed**: 10 unique colors — teal for construction type, warm gray for stamps, yellow for structural, violet for general notes (was 3 colors shared among 10 types)
- Window resize handler: debounced 200ms annotation repositioning
- localStorage persistence: annotation toggle + filter state survives page reloads
- Accessibility: ARIA labels on toggle button, filter dropdown, all SVG annotation layers

### Annotation Legend
- **"Legend" button** in annotation toolbar — opens collapsible dropdown panel
- Shows all 11 annotation types with color swatches and human-readable labels
- Click-outside-to-close behavior
- Auto-builds from ANNOTATION_COLORS map (always in sync)

### Reviewer Notes Capture
- **New annotation type**: `reviewer_note` (pink #ec4899)
- Vision prompt now identifies/transcribes existing reviewer comments, redlines, and handwritten notes
- Added to `VALID_ANNOTATION_TYPES` in `src/vision/epr_checks.py`
- Fixed filter dropdown: added 3 missing options (title_block, general_note, reviewer_note)

### Bug Fixes (Session 23 follow-up)
- Fixed DuckDB schema missing `page_annotations` column in `src/db.py`
- Fixed Full Analysis button visual feedback (`.btn-active` CSS + JS state management)
- Fixed `login_page` → `auth_login` endpoint crash in analysis_history route

### Files Changed
- `web/app.py` — async routing, dead code removal, annotation_count, error handler
- `web/templates/index.html` — button label, subtitle, feature hint, HTMX error feedback
- `web/templates/analyze_plans_results.html` — legend UI/CSS/JS, colors, resize, localStorage, a11y, filter options
- `web/templates/analysis_history.html` — AI Annotations badge
- `src/vision/prompts.py` — reviewer_note type + focus instruction in annotation prompt
- `src/vision/epr_checks.py` — reviewer_note in VALID_ANNOTATION_TYPES
- `src/db.py` — DuckDB page_annotations migration
- `tests/test_vision_annotations.py` — updated expected types set

## Session 22.6 — RAG Knowledge Retrieval System Phase 1 (2026-02-17)

### RAG Pipeline
- **`src/rag/` module** — Complete retrieval-augmented generation pipeline for the knowledge base
- **`chunker.py`** — Three chunking strategies: tier1 JSON section-level, tier2/3 paragraph sliding window (800 char, 150 overlap), tier4 code section boundaries
- **`embeddings.py`** — OpenAI `text-embedding-3-small` client with batching (100/batch), retries (3x exponential backoff), 30K char truncation
- **`store.py`** — pgvector CRUD: `knowledge_chunks` table with `vector(1536)` embeddings, IVFFlat indexing, tier/file/trust_weight columns, similarity search
- **`retrieval.py`** — Hybrid scoring pipeline: `final_score = (vector_sim × 0.60 + keyword_score × 0.30 + tier_boost × 0.10) × trust_weight`. Deduplication via Jaccard word-set comparison. Graceful fallback to keyword-only when embeddings unavailable.

### Ingestion Script
- **`scripts/rag_ingest.py`** — CLI to chunk, embed, and store all knowledge tiers. Supports `--tier`, `--dry-run`, `--clear`, `--rebuild-index`, `--stats`. Dry run shows 1,012 chunks across 38 tier1 JSON files, 52 tier2 text files, and 6 tier3 bulletins.

### Web Integration
- **`/ask` route** — General questions now attempt RAG retrieval before falling back to keyword-only concept matching. Results show source attribution with relevance scores.

### Infrastructure
- Added `openai>=1.0.0` to `pyproject.toml` dependencies
- **32 new tests** in `tests/test_rag.py` covering chunker (10), retrieval scoring (10), embeddings (2), store (6), ingestion (2), context assembly (2)

### Files Changed (7 files)
- `src/rag/__init__.py` — Module docstring
- `src/rag/embeddings.py` — OpenAI embedding client
- `src/rag/chunker.py` — Chunking strategies
- `src/rag/store.py` — pgvector store operations
- `src/rag/retrieval.py` — Hybrid retrieval pipeline
- `scripts/rag_ingest.py` — Ingestion CLI
- `web/app.py` — RAG integration in `_ask_general_question`
- `tests/test_rag.py` — 32 tests
- `pyproject.toml` — Added openai dependency

---
## Session 23 — AI-Generated Plan Annotations (2026-02-16)

### Vision Annotation Extraction
- **New prompt**: `PROMPT_ANNOTATION_EXTRACTION` in `src/vision/prompts.py` — asks Claude Vision to identify and spatially locate items on architectural drawings
- **Extraction function**: `extract_page_annotations()` in `src/vision/epr_checks.py` — validates coordinates (0-100%), type enum (10 types), label truncation (60 chars), max 12 per page
- **3-tuple return**: `run_vision_epr_checks()` now returns `(checks, extractions, annotations)` — annotations extracted from same sampled pages as title block data (no extra render cost)

### SVG Overlay Rendering
- **Client-side SVG overlays** on all image views: thumbnails (dots only), detail card (full callouts), lightbox (full callouts), comparison (both sides)
- **Color-coded by type**: red=EPR issues, green=code refs, blue=dimensions, purple=occupancy, orange=scope, gray=stamps/title blocks, teal=construction type
- **Resolution-independent**: coordinates stored as percentages (0-100), SVG viewBox maps to naturalWidth/naturalHeight
- **Toggle & filter controls**: toolbar button to show/hide all annotations, dropdown to filter by annotation type

### Storage & Plumbing
- **DB column**: `page_annotations TEXT` on `plan_analysis_sessions` (PostgreSQL + DuckDB migrations)
- **Pipeline threading**: `analyze_plans()` → `plan_worker.py` → `create_session()` → `get_session()` → template context → JavaScript
- **Graceful degradation**: old sessions with NULL annotations display normally (empty list)

### Tests
- **20 new tests** in `tests/test_vision_annotations.py` — extraction, validation, failure modes, constants
- Updated `test_analyze_plans.py` and `test_vision_epr_checks.py` for 3-tuple return signature

### Files Changed
- `src/vision/prompts.py` — new annotation extraction prompt
- `src/vision/epr_checks.py` — `extract_page_annotations()`, 3-tuple return
- `src/tools/analyze_plans.py` — 3-tuple unpacking, annotations threading
- `web/plan_images.py` — `page_annotations` in create/get session
- `web/app.py` — DB migration, route updates, `annotations_json` to templates
- `web/plan_worker.py` — 3-tuple unpacking, annotations to `create_session()`
- `web/templates/analyze_plans_results.html` — SVG overlay system, JS rendering engine, CSS, controls
- `src/db.py` — DuckDB schema migration for `page_annotations` column
- `tests/test_vision_annotations.py` — **NEW** 20 tests
- `tests/test_analyze_plans.py` — updated for 3-tuple
- `tests/test_vision_epr_checks.py` — updated for 3-tuple

## Session 22.5 — Plan Analysis UX Overhaul (2026-02-16)

### Multi-Stage Progress Indicator (Item 3)
- **DB migration**: `progress_stage` + `progress_detail` columns on `plan_analysis_jobs`
- **Worker updates**: 4 progress checkpoints — Analyzing → Rendering (with page count) → Finalizing
- **Step indicator UI**: Horizontal 3-dot stepper with pulsing active state, replaces generic bouncing bar
- Templates: `analyze_plans_processing.html` (initial state) + `analyze_plans_polling.html` (live updates)

### App Shell for Async Results (Item 1)
- **New template**: `plan_results_page.html` — full-page wrapper with shared nav fragment
- Async results route now renders inside app shell (header, nav, logout) instead of bare fragment
- `property_address` passed to template context for watch cross-sell

### Simplified Upload Form (Item 4)
- **Quick Check is now the default** primary action (instant metadata scan)
- Full Analysis (AI vision) is opt-in secondary button
- **Progressive disclosure**: description, permit type, address, permit number hidden behind "More options ▸" toggle
- Two side-by-side buttons replace single submit + checkbox

### Account Page "Plan Analyses" Card + Nav Links (Item 2)
- **Account page card**: shows 3 most recent analyses with status badges + "View all analyses →"
- **Header nav**: "My Analyses" badge added to shared `fragments/nav.html`
- **Below-form link**: "View your analysis history →" for logged-in users

### Card-Based History Layout (Item 5)
- **Full rewrite** of `analysis_history.html`: table → responsive card grid
- Cards show filename, status badge, file size, date, property/permit details, action links
- Adopted shared `fragments/nav.html` (was inline header)
- Responsive: single column below 640px

### Post-Analysis Watch Cross-Sell (Item 6)
- **Address parser**: `_parse_address("123 Main St")` → `("123", "Main St")` for watch system
- **Logged-in with address**: "Track changes to this property?" card with HTMX watch button
- **Logged-out with address**: "Sign in to watch {address}" prompt
- No address: nothing shown

### Files Changed
- `web/app.py` — migration, address parser, route updates (Items 1,2,3,6)
- `web/plan_jobs.py` — progress columns in `get_job()` SELECT (Item 3)
- `web/plan_worker.py` — 4 progress update calls (Item 3)
- `web/templates/plan_results_page.html` — **NEW** app shell wrapper (Item 1)
- `web/templates/analyze_plans_processing.html` — step indicator initial state (Item 3)
- `web/templates/analyze_plans_polling.html` — step indicator live updates (Item 3)
- `web/templates/index.html` — form restructure + nav link (Items 2,4)
- `web/templates/account.html` — Plan Analyses card (Item 2)
- `web/templates/analysis_history.html` — card grid + nav fragment (Item 5)
- `web/templates/analyze_plans_results.html` — watch cross-sell (Item 6)
- `web/templates/fragments/nav.html` — "My Analyses" badge (Item 2)

## Session 22.4 — Recent Searches (2026-02-16)

### Feature
- **Recent searches** — Last 5 searches saved to localStorage and rendered as clickable preset chips above quick-actions on the home page. Case-insensitive dedup, truncates long queries, clear button to wipe history. Pure client-side, no backend changes.

### Files Changed (1 file, +83 lines)
- `web/templates/index.html` — Recent searches container, CSS, JS (localStorage read/write, chip rendering, HTMX hook)

---

## Session 22.3 — Fix False Positive Assessor Use Mismatch (2026-02-16)

### Bug Fix
- **Assessor vs. permit use mismatch false positive** — "Single Family Residential" (Assessor) was flagged as a mismatch against "1 family dwelling" (permit) even though they mean the same thing. Added `"single family residential"` and `"two family residential"` to the `_USE_EQUIVALENTS` table in `web/owner_mode.py`.

### Tests
- Added `test_assessor_single_family_residential_equivalent` and `test_assessor_single_family_residential_no_mismatch` to `tests/test_owner_mode.py` — 49 tests passing.

### Files Changed (2 files)
- `web/owner_mode.py` — Added equivalents to `_USE_EQUIVALENTS`
- `tests/test_owner_mode.py` — 2 new tests for the fix

---

## Session 22 — Async Plan Analysis with Per-User Storage (2026-02-17)

### Async Background Processing
- **Large PDFs (>10 MB) processed asynchronously** via `ThreadPoolExecutor(max_workers=1)` — eliminates gunicorn timeout for 22+ MB architectural plan sets
- Immediate "Processing..." response with HTMX polling (3s interval)
- **Email notification** when analysis completes (success or failure) via existing SMTP
- Stale job recovery on worker restart — marks stuck jobs as "stale" after 15 min
- Gallery images rendered at **72 DPI** (vs 150 DPI for vision) for 4x faster rendering

### Per-User Persistent Storage
- **`plan_analysis_jobs` table** — tracks every analysis with full lifecycle: pending → processing → completed/failed/stale
- Original PDF stored as BYTEA during processing, cleared after completion
- **Tiered TTL**: 30-day retention for logged-in users, 24h for anonymous
- `user_id` column added to `plan_analysis_sessions` for ownership

### Property/Permit Tagging
- **Manual entry**: Property Address + Permit Number fields on upload form
- **Auto-extraction**: `_auto_extract_tags()` scans vision results for address and permit patterns
- Tags stored with source tracking: `manual`, `auto`, or `both`

### Analysis History
- **`/account/analyses` page** — searchable table of past analyses
- Search by address, permit number, or filename
- Status badges (completed, processing, failed, stale)
- Direct "View" links to completed results

### New Files
- `web/plan_jobs.py` — Job CRUD (385 lines, 8 functions)
- `web/plan_worker.py` — Background worker (336 lines)
- 6 new templates: processing, polling, complete, failed, stale, email, history

### Routes Added
- `GET /plan-jobs/<job_id>/status` — HTMX polling endpoint
- `GET /plan-jobs/<job_id>/results` — View completed async results
- `GET /account/analyses` — Analysis history page

## Session 21.10 — Fix 5 Analyze Plans QA Bugs (2026-02-17)

### Bug Fixes
- **ZIP Download 500 fix** — PostgreSQL JSONB returns Python objects (not JSON strings); `get_session()` now handles already-parsed list/dict via `isinstance()` check instead of always calling `json.loads()`
- **All thumbnails shown** — Thumbnail gallery now loops `range(page_count)` (all 17 pages) instead of `extractions` (only 5 vision-sampled pages)
- **Print/Download Report scoped** — Added `@media print` CSS that hides toolbar, gallery, lightbox, comparison, email modal; `printReport()` JS wrapper adds `printing-report` class to `<body>` during print
- **Email route fixed** — 4 sub-fixes: accept `session_id` route param, import `send_brief_email` (not `send_email`), use correct arg names (`to_email`, `html_body`), use `logging.error` (not `logger`)

### Files Modified
- `web/plan_images.py` — JSONB isinstance check (line 109)
- `web/templates/analyze_plans_results.html` — Thumbnail loop, @media print CSS (80+ lines), `printReport()` JS function
- `web/app.py` — Email route rewritten with correct imports, params, and error handling

## Session 20 — Phase 4.5: Visual Plan Analysis UI (2026-02-16)

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

## Session 19 — Bounty Points, Nightly Triage & Quick Fixes (2026-02-16)

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
