# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->

## SUGGESTED SCENARIO: CI catches broken test on PR
**Source:** .github/workflows/ci.yml
**User:** architect | admin
**Starting state:** Developer has pushed a branch with a failing test
**Goal:** CI blocks merge until tests pass
**Expected outcome:** PR shows red check, reviewer sees which test failed, merge is blocked
**Edge cases seen in code:** Tests that timeout (30s limit) appear as failures not skips; orphaned test files (missing modules) cause import errors not test failures
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CI passes on clean branch
**Source:** .github/workflows/ci.yml
**User:** architect | admin
**Starting state:** Developer has pushed a branch with all tests passing
**Goal:** CI confirms branch is safe to merge
**Expected outcome:** PR shows green check within ~3 minutes, 797+ tests reported as passed
**CC confidence:** high
**Status:** PENDING REVIEW

_Last reviewed: never_

---

## SUGGESTED SCENARIO: Admin Ops tab timeout recovery
**Source:** Session 38f — Admin Ops infinite spinner fix
**User:** admin
**Starting state:** Logged in as admin, database under heavy load or slow
**Goal:** View any Admin Ops tab and get either content or a clear error within 30 seconds
**Expected outcome:** Tab loads data OR shows "loading slowly" / "timed out" fallback with retry link. Never shows infinite spinner past 30s. Clicking "Reload page" link in error state recovers.
**Edge cases seen in code:** Server-side SIGALRM (25s) fires before client-side HTMX timeout (30s) — both paths must produce a user-visible message, not a blank or stuck state. Race between the two timeouts should not produce duplicate error messages.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin Ops tab switching under load
**Source:** Session 38f — rapid tab switching QA
**User:** admin
**Starting state:** Logged in as admin, on `/admin/ops`, one tab currently loading
**Goal:** Switch to a different tab before the first tab finishes loading
**Expected outcome:** Previous request is superseded by the new tab request. New tab loads or times out gracefully. No orphaned spinner from the canceled tab. Active state (blue highlight) tracks the most-recently-clicked tab.
**Edge cases seen in code:** HTMX doesn't auto-cancel in-flight requests by default. If both responses arrive, the last-clicked tab's content should win. The `loading` CSS class must be removed from the abandoned tab button.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity scoring preserves hold signal through post-processing
**Source:** Session 38f — 532 Sutter hold bug
**User:** expediter
**Starting state:** Property has ≥5 active permits, 1 expired permit, AND an active hold at a routing station
**Goal:** Morning brief correctly shows AT RISK for the hold, not ON TRACK from expired-permit downgrade
**Expected outcome:** Property card shows AT RISK (red) with "Hold at [station]" reason. The expired permit's automatic downgrade logic does NOT fire because holds are a real action signal.
**Edge cases seen in code:** Hold upgrade runs AFTER per-permit scoring but BEFORE post-processing. If the per-permit worst_health is already `at_risk` from expiration, the hold must still overwrite the reason text so post-processing doesn't match "permit expired". Properties with both holds AND enforcement should show whichever was set last (enforcement check runs after hold check).
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Hash routing aliases for Admin Ops
**Source:** Session 38f — hash mapping fix
**User:** admin
**Starting state:** Not on Admin Ops page
**Goal:** Navigate directly to a specific tab via URL hash
**Expected outcome:** `/admin/ops#luck` opens LUCK Sources, `#dq` opens Data Quality, `#watch` opens Regulatory Watch, `#pipeline` opens Pipeline Health. Unknown hashes fall back to Data Quality.
**Edge cases seen in code:** Hash aliases map friendly names to data-tab values (`luck→sources`). If someone bookmarks a tab with the canonical hash (`#sources`), it should also work. Empty hash defaults to `quality`.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity not downgraded when property has open enforcement
**Source:** Session 38f — enforcement guard in post-processing
**User:** expediter
**Starting state:** Property has expired permit + open violations/complaints + multiple active permits
**Goal:** Morning brief shows AT RISK for the enforcement, not downgraded to ON TRACK
**Expected outcome:** Property card shows AT RISK (red) with "Open enforcement: X violations" reason. Post-processing skips this property because `has_enforcement` flag is True.
**Edge cases seen in code:** Enforcement check runs after hold check in the per-property loop. If both hold and enforcement exist, enforcement overwrites the hold reason. Post-processing guards check both `has_holds` and `has_enforcement` independently.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: DQ cache serves instant results; refresh populates fresh data
**Source:** Session 38g — DQ cache architecture
**User:** admin
**Starting state:** Logged in as admin, DQ cache has been populated by nightly cron (or a previous manual refresh)
**Goal:** Open Data Quality tab and see check results instantly, then trigger a manual refresh to get updated data
**Expected outcome:** DQ tab loads in <1s from cache, showing "Last refreshed: [timestamp]" and all check cards. Clicking "Refresh" button runs all checks (may take 10-30s), then replaces content with fresh results and updated timestamp. If cache is empty (first deploy), tab shows "No cached results yet" with instructions to click Refresh.
**Edge cases seen in code:** Two gunicorn workers both running startup migrations can race on `CREATE TABLE IF NOT EXISTS dq_cache`, producing a harmless duplicate-key error. Cache stores a single row (DELETE then INSERT), so stale rows never accumulate. If a check query times out during refresh, it's caught and skipped — remaining checks still run.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin dropdown submenu reachable on hover
**Source:** Session 38g — CSS hover gap fix in nav.html
**User:** admin
**Starting state:** Logged in as admin, on any page with the top nav bar
**Goal:** Hover over "Admin" in the nav bar, then move cursor down to click a submenu item (e.g., "Data Quality")
**Expected outcome:** Submenu appears on hover over "Admin" and remains visible as the cursor moves from the trigger to the submenu items. Clicking any submenu item navigates to that Admin Ops tab. Submenu disappears only when cursor leaves both the trigger and the menu.
**Edge cases seen in code:** A visual gap between the trigger element and the dropdown can cause hover loss when the cursor crosses the gap. The fix uses an invisible padding bridge (6px) so the hover target is contiguous. Fast diagonal mouse movements should still keep the menu open.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin Ops initial tab loads on first visit without double-click
**Source:** Session 38g — htmx.ajax() race condition fix
**User:** admin
**Starting state:** Not on Admin Ops page; navigating for the first time in session
**Goal:** Navigate to `/admin/ops` (or via Admin dropdown) and see the default tab content load automatically
**Expected outcome:** Page loads, default tab (Data Quality or hash-specified tab) content appears without needing to click any tab button. Tab button shows active (blue) state. URL hash updates to reflect the active tab. No infinite spinner unless the server genuinely fails.
**Edge cases seen in code:** Inline script at bottom of `<body>` runs before HTMX's DOMContentLoaded handler processes `hx-get` attributes on buttons. Using `htmx.ajax()` directly bypasses this race. Hash aliases (`#luck` → sources, `#dq` → quality) resolve before the initial load fires.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: DQ tab shows bulk index health diagnostic
**Source:** Session 38g — check_bulk_indexes() in data_quality.py
**User:** admin
**Starting state:** Logged in as admin, DQ cache populated, on Data Quality tab
**Goal:** Verify that critical PostgreSQL indexes exist on bulk tables
**Expected outcome:** Bottom of DQ tab shows a row of index tags — green checkmark for indexes that exist, red X for missing ones. At least 6 key indexes are checked: contacts_permit, permits_number, permits_block_lot, inspections_ref, entities_name, addenda_app_num. Missing indexes indicate a deployment issue.
**Edge cases seen in code:** `check_bulk_indexes()` queries `pg_indexes` system catalog; on DuckDB (local dev), it returns empty list and the bar doesn't render. Index creation runs at startup but can silently fail if the table doesn't exist yet (e.g., before first ingest).
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: DQ checks degrade gracefully when individual checks error
**Source:** Session 38g QA — 5 of 10 cached DQ checks showed "Error / Check failed"
**User:** admin
**Starting state:** Logged in as admin, DQ cache populated, some checks failing due to missing cron data or query errors
**Goal:** Open Data Quality tab and see results even when some checks have errors
**Expected outcome:** Tab loads fully. Passing checks show green OK or yellow WARN with real data. Failing checks show red FAIL badge with "Error — Check failed — see logs" message. Summary line at top correctly counts passing/warning/failing. The tab never crashes or shows a spinner because one check errored.
**Edge cases seen in code:** Each check in `run_all_checks()` is wrapped in try/except. A failed check produces a result dict with `status: "fail"` and `detail: "Check failed — see logs"`. The cache stores whatever results completed. If ALL checks fail, the tab still renders with 0 passing / 0 warning / N failing.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Expired stalled permit shows AT RISK not SLOWER
**Source:** web/brief.py + web/portfolio.py severity fix (Session cool-pike)
**User:** expediter
**Starting state:** User has a watched property with 1 expired permit, last activity 400+ days ago, no other active permits
**Goal:** See an accurate risk signal for the stale permit
**Expected outcome:** Property card shows AT RISK (red dot) with reason "permit expired Xd ago (no recent activity)". Not SLOWER.
**Edge cases seen in code:** The downgrade block at brief.py:1342 only fires when `worst_health == "at_risk"` AND reason contains "permit expired". If the per-permit health was set to something other than at_risk initially, this post-processing never runs.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Expired permit at active site stays ON TRACK
**Source:** web/brief.py + web/portfolio.py severity post-processing (Session cool-pike)
**User:** expediter
**Starting state:** User has a property with 1 expired permit but 5+ other active permits and activity within 90 days
**Goal:** See that the expired permit does not trigger a false AT RISK
**Expected outcome:** Property card shows ON TRACK (green dot) — expired permit dismissed as routine at an active construction site
**Edge cases seen in code:** `has_other_active = active > 1` is the threshold. With exactly 2 active permits the condition fires. With >=5 active the dismiss-to-on_track branch fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Pasted email routes to AI draft response
**Source:** Intent router Priority 0 (src/tools/intent_router.py)
**User:** expediter
**Starting state:** Expediter is on homepage, has received an email from a homeowner asking about permits
**Goal:** Paste the email into the search box and get an AI-drafted reply
**Expected outcome:** AI generates a contextual response addressing the homeowner's question, using RAG knowledge base. Does NOT trigger complaint search, address lookup, or project analysis even if email contains those keywords.
**Edge cases seen in code:** Single-line greeting without substance ("Hi Amy") should NOT trigger draft — falls through to general_question. "draft:" prefix always triggers regardless of length.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Expired permit does not alarm active site
**Source:** Portfolio health logic (web/portfolio.py, web/brief.py)
**User:** expediter
**Starting state:** Expediter watches a property with 1 expired mechanical permit and 1 active permit, last activity 3 days ago
**Goal:** See accurate health status on portfolio and morning brief
**Expected outcome:** Property shows ON_TRACK (green), not BEHIND or AT_RISK. No health_reason text about the expired permit. Expediter is not distracted by administrative noise.
**Edge cases seen in code:** Property with expired permit AND no activity for 90+ days AND no other active permits → SLOWER (gentle nudge). Property with open violations → still AT_RISK regardless of expired permits.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: What Changed shows specific permit details
**Source:** Morning brief "What Changed" section (web/brief.py)
**User:** expediter
**Starting state:** Watched property had a permit status_date update in SODA but nightly change detection didn't log a specific transition
**Goal:** See what actually changed at the property on the morning brief
**Expected outcome:** Card shows permit number, permit type, and current status badge instead of generic "Activity Xd ago" with "1 active of 2 permits"
**Edge cases seen in code:** If permits table query fails or returns no results, falls back to generic activity card. Multiple permits at same address that changed → one card per permit.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Multi-line email with signature detected
**Source:** Intent router signature detection (src/tools/intent_router.py)
**User:** expediter
**Starting state:** Expediter receives a forwarded email with sign-off ("— Karen", "Best regards,", "Sent from my iPhone")
**Goal:** Paste the full email thread into search box for AI analysis
**Expected outcome:** Routes to draft_response even without explicit "Hi" greeting, based on signature detection + multi-line structure
**Edge cases seen in code:** Single dash "- Karen" matches but "-Karen" (no space) does not. "Sent from my iPhone" only matches at line start.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Badge count matches permit table count
**Source:** Session 45 — badge-table count sync fix
**User:** expediter
**Starting state:** User searches an address with permits across multiple parcels/historical lots
**Goal:** Understand how many permits exist at a property at a glance
**Expected outcome:** The PERMITS badge total matches the count shown in the permit results table
**Edge cases seen in code:** Address-only queries return fewer permits than parcel-level merge; single-permit results don't show "Found N permits" line
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Feedback screenshot on content-heavy page
**Source:** Session 45 — feedback screenshot capture/submit
**User:** homeowner
**Starting state:** User is viewing permit results page with 10+ permits in table
**Goal:** Report a bug or suggestion with a visual screenshot of what they see
**Expected outcome:** Screenshot captures within 5MB limit, attaches to feedback form, submits successfully with screenshot icon visible in admin queue
**Edge cases seen in code:** html2canvas CDN load failure shows fallback message; JPEG quality degrades from 0.7 to 0.4 if first pass exceeds 5MB
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Exact street name matching prevents false positives
**Source:** Session 45 — exact match fix
**User:** expediter
**Starting state:** User searches "146 Lake" (LAKE ST exists, BLAKE ST also exists)
**Goal:** See permits only for LAKE ST, not substring matches like BLAKE
**Expected outcome:** Results contain only LAKE ST permits; no BLAKE, LAKE MERCED HILL, or other partial matches appear
**Edge cases seen in code:** Space-variant street names (VAN NESS vs VANNESS) should still match; "Did you mean?" suggestions appear for non-matching addresses
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Undo accidental delete within grace period
**Source:** Session 46 — UX audit fix #14 (soft-delete + undo)
**User:** expediter
**Starting state:** User has a completed analysis on the history page
**Goal:** Accidentally delete an analysis, then undo before 30-second grace period expires
**Expected outcome:** After clicking Delete, a toast appears with "Undo" button; clicking Undo within 30s restores the job; job reappears in the list
**Edge cases seen in code:** Bulk delete returns multiple job_ids for undo; grace period timer auto-dismisses toast after 30s; restore fails gracefully if job was already permanently purged
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Retry failed analysis with prefilled metadata
**Source:** Session 46 — UX audit fix #3 (retry with prefill)
**User:** expediter
**Starting state:** User has a failed or stale analysis card visible
**Goal:** Retry the analysis without re-entering all the metadata (address, permit, stage)
**Expected outcome:** Clicking "Retry" opens the upload form with address, permit number, submission stage, and project description pre-filled from the original job
**Edge cases seen in code:** If original job had no address/permit, fields should be empty (not "null"); file must still be re-uploaded manually
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Filter persistence across page reloads
**Source:** Session 46 — UX audit fix #10 (URL param persistence)
**User:** expediter
**Starting state:** User is on the analysis history page with many jobs
**Goal:** Set a status filter, share the URL with a colleague, and have the same view load
**Expected outcome:** Clicking a filter chip updates the URL with `?status=...`; reloading the page restores the active filter; sharing the URL loads the filtered view
**Edge cases seen in code:** Multiple filters (status + mode) should both persist; clearing "All" should remove params
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Compare page shows human-readable labels
**Source:** Session 46 — UX audit fixes #5a/b, #9, #17
**User:** expediter
**Starting state:** User navigates to the comparison page for two versions of the same plan set
**Goal:** Understand the comparison results without needing to know internal terminology
**Expected outcome:** Column headers say "Original" / "Resubmittal"; type chips say "Plan Checker Note", "Compliance Issue" etc. (not raw values); version labels show actual version numbers from data; EPR checks show human names with raw ID as secondary text
**Edge cases seen in code:** Unknown type values fall through to title-cased raw value; EPR check names loaded from tier1 knowledge base
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Project notes visible for pre-existing jobs in grouped view
**Source:** Session 46 — analysis_grouping.html notes panel NULL version_group fix
**User:** expediter
**Starting state:** User has existing plan analysis jobs created before `version_group` column was added; grouped view enabled
**Goal:** Open notes panel for a project group and save a note
**Expected outcome:** "📝 Notes" toggle appears on every project group regardless of whether jobs have `version_group` populated. Clicking toggle opens textarea. Typing and saving works. Char counter updates live. Saved confirmation ("✓ Saved") appears briefly after save.
**Edge cases seen in code:** Groups keyed by group `key` (normalized address/filename) when `version_group` is NULL — notes persist correctly across page reloads using that key. Single-job groups also show the notes panel.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Project notes persist across grouped view reloads
**Source:** Session 46 — saveProjectNotes() API call
**User:** expediter
**Starting state:** User has saved notes on a project group (text was saved via `/api/project-notes/{key}`)
**Goal:** Reload the grouped view and verify notes are still there
**Expected outcome:** Notes text reappears in the textarea on reload. Preview truncation (first 60 chars + "…") appears in the "📝 Notes" button label. Character count shows correct length.
**Edge cases seen in code:** Notes keyed by version_group UUID when available, otherwise by group key (address/filename). Key collision unlikely but possible if two users have same filename.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Notes character counter shows live count
**Source:** s46-ux-audit-analysis-history-qa.md / analysis_grouping.html
**User:** expediter
**Starting state:** User is in grouped view with at least one project group visible
**Goal:** Add project notes and verify character limit is visible
**Expected outcome:** When user opens the Notes panel and types, a live counter (e.g., "42 / 4,000") updates with each keystroke. Counter starts at "0 / 4,000" when empty. Counter prevents saving beyond 4,000 characters.
**Edge cases seen in code:** Counter keyed by version_group UUID — if version_group is missing from the DB query, the panel never renders at all (was the root cause of this session's FAIL).
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Filter chip selection persists on page reload
**Source:** s46-ux-audit-analysis-history-qa.md / analysis_history.html
**User:** expediter
**Starting state:** User is on the Analysis History page with multiple jobs in different states
**Goal:** Filter to "Completed" jobs, bookmark or share the URL, return to page
**Expected outcome:** The URL updates to reflect the selected filter (e.g., ?status=completed). On reload, the same filter is active and only completed jobs show.
**Edge cases seen in code:** Both status and mode filters are persisted. Combining filters (e.g., status=completed&mode=quick) should also persist correctly.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Retry pre-fills upload form with original job data
**Source:** s46-ux-audit-analysis-history-qa.md / analysis_history.html
**User:** expediter
**Starting state:** An analysis job has failed (status = failed or stale)
**Goal:** Resubmit the same job without re-entering address and permit number
**Expected outcome:** Clicking "Retry" on a failed/stale job card opens the upload form pre-filled with the original job's address, permit number, and analysis stage. User only needs to upload a new file and submit.
**Edge cases seen in code:** Pre-fill fetched via /api/plan-jobs/<id>/prefill endpoint. If the job has no address/permit stored, fields may be empty.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CI gates PR merge with lint + unit tests
**Source:** .github/workflows/ci.yml + branch protection
**User:** admin
**Starting state:** A contributor opens a pull request against main
**Goal:** Verify that lint and unit tests pass before the PR can be merged
**Expected outcome:** GitHub Actions CI triggers automatically, runs ruff lint and 1,227+ unit tests on Python 3.11. Branch protection blocks merge until both `lint` and `unit-tests` checks pass. Network tests are skipped (only run nightly).
**Edge cases seen in code:** Network-dependent tests use `@pytest.mark.network` and are excluded via `-m "not network"`. Branch protection has `enforce_admins: false` so Tim can bypass if needed.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly CI validates SODA API before data import
**Source:** .github/workflows/ci.yml + nightly-cron.yml
**User:** admin
**Starting state:** It's 2:30 AM Pacific, scheduled CI fires
**Goal:** Validate SODA API endpoints are reachable before running the nightly data import at 3 AM
**Expected outcome:** Network tests run with 3 retry attempts (0s/30s/60s backoff). If all 3 fail, CI fails, Telegram alert sent, and nightly-cron.yml does NOT trigger (gated via `workflow_run` with `conclusion == 'success'` condition). If retries succeed, nightly import proceeds normally.
**Edge cases seen in code:** `workflow_run` trigger only fires on `schedule` events (not push/PR CI). `workflow_dispatch` bypasses the success check for manual triggers.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Planning layer queries inspection rates via run_query
**Source:** src/tools/project_intel.py (run_query)
**User:** admin
**Starting state:** Planning session in Claude Chat with sfpermits MCP connected
**Goal:** Query the production database for inspection pass/fail rates by permit type to calibrate severity scoring
**Expected outcome:** run_query accepts `SELECT permit_type, result, COUNT(*) FROM inspections GROUP BY 1,2`, returns markdown table with row counts and execution time. Query completes within 10s timeout.
**Edge cases seen in code:** LIMIT auto-appended if missing; user-specified LIMIT capped at 1000; Postgres statement_timeout enforced at 10s; comments stripped before keyword validation
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: run_query blocks SQL injection attempts
**Source:** src/tools/project_intel.py (run_query security)
**User:** admin
**Starting state:** MCP tool invoked with malicious SQL
**Goal:** Prevent any write operations through run_query
**Expected outcome:** INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE/GRANT/REVOKE/COPY all rejected with clear error message. Comment-disguised writes (e.g., `-- SELECT\nDELETE`) also rejected. Column names containing keywords (e.g., `deleted_at`, `update_count`) do NOT trigger false positives.
**Edge cases seen in code:** _strip_sql_comments removes both `--` and `/* */` before keyword check; regex uses `\b` word boundaries to avoid false positives
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: read_source blocks directory traversal
**Source:** src/tools/project_intel.py (read_source security)
**User:** admin
**Starting state:** MCP tool invoked with path traversal attempt
**Goal:** Prevent reading files outside the repository
**Expected outcome:** Absolute paths (`/etc/passwd`) rejected. Relative traversal (`../../../etc/passwd`) rejected. Symlink traversal that resolves outside repo rejected. Only files within repo root served.
**Edge cases seen in code:** Path resolved with `.resolve()` then checked with `.relative_to(_REPO_ROOT)` — handles symlinks correctly
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: schema_info provides table overview for planning
**Source:** src/tools/project_intel.py (schema_info)
**User:** admin
**Starting state:** Planning session needs to understand database structure
**Goal:** Get table list with row counts, then drill into specific table columns
**Expected outcome:** Without args: lists all tables sorted by row count with approximate counts. With table arg: shows columns (name, type, nullable, default), row count, and indexes (Postgres only). Invalid table names rejected.
**Edge cases seen in code:** DuckDB uses SHOW TABLES + per-table COUNT; Postgres uses information_schema + pg_stat_user_tables; table name sanitized with regex before interpolation
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: list_tests surfaces test coverage for feature area
**Source:** src/tools/project_intel.py (list_tests)
**User:** admin
**Starting state:** Planning session wants to check test coverage before building a feature
**Goal:** Find all tests related to "brief" or "severity" functionality
**Expected outcome:** Pattern filter returns matching test files with function counts. Matching function names listed under each file. No unrelated test files appear.
**Edge cases seen in code:** Pattern matched case-insensitively against both filename and function name; show_status=True delegates to `pytest --collect-only` with 15s timeout
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CI failure sends Telegram notification
**Source:** .github/workflows/ci.yml notify job
**User:** admin
**Starting state:** Nightly scheduled CI has failed (any of lint, unit-tests, or network-tests)
**Goal:** Get notified of the failure without having to check GitHub manually
**Expected outcome:** Telegram message sent with failed job names and link to the GitHub Actions run. Message indicates nightly data import was skipped.
**Edge cases seen in code:** Telegram secrets may not be configured — `curl || echo` fallback prevents notify job itself from failing. `env.TELEGRAM_BOT_TOKEN != ''` check skips the step gracefully if secrets are missing.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Expired seismic permit scores CRITICAL
**Source:** src/severity.py (Session 51)
**User:** expediter
**Starting state:** Property has a seismic retrofit permit, status=issued, filed 4 years ago, issued 13+ months ago ($50k), zero inspections
**Goal:** Severity model identifies this as a critical-risk permit
**Expected outcome:** Severity score >= 80 (CRITICAL tier). Top driver is expiration_proximity or inspection_activity. Explanation mentions the expired permit. permit_lookup output shows "Severity Score: XX/100 — CRITICAL" section.
**Edge cases seen in code:** $50k permits have 360-day Table B validity; $200k+ have 1080 days. A $200k seismic issued 13 months ago would NOT be expired (1080 days remaining) — tier would be lower.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Fresh low-cost filing scores GREEN
**Source:** src/severity.py (Session 51)
**User:** homeowner
**Starting state:** Homeowner just filed a $5k window replacement permit 5 days ago
**Goal:** Severity model confirms permit is on track
**Expected outcome:** Severity score < 20 (GREEN tier). All dimensions score near zero. permit_lookup shows "GREEN" tier. Morning brief shows "on_track" health.
**Edge cases seen in code:** Filed permits get zero inspection penalty (inspections not expected yet). Category "windows_doors" has risk score of 25 — lowest non-trivial category.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Severity model replaces manual health calculation in brief
**Source:** web/brief.py (Session 51)
**User:** expediter
**Starting state:** User has multiple watched properties with various permit states
**Goal:** Morning brief property cards use the new severity model for health classification
**Expected outcome:** Property cards show health status derived from severity tiers: CRITICAL→at_risk, HIGH→behind, MEDIUM→slower, LOW/GREEN→on_track. Cards include severity_score and severity_tier fields. No visible difference in UX — backward compatible with 4-tier health display.
**Edge cases seen in code:** Brief passes inspection_count=0 (Phase 1 — doesn't batch-fetch per-permit inspections). This means inspection_activity dimension is underweighted in brief context. Post-processing enforcement upgrades and expired-permit downgrades still run after severity scoring.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: permit_severity tool handles missing permit gracefully
**Source:** src/tools/permit_severity.py (Session 51)
**User:** expediter
**Starting state:** User asks to score a permit number that doesn't exist in the database
**Goal:** Get a clear message, not an error
**Expected outcome:** Returns "No permit found matching permit number **XXXX**" message. No traceback, no 500 error.
**Edge cases seen in code:** DB unavailable returns "Database unavailable" message. Empty/whitespace-only inputs return usage message. Block+lot search with no results returns "No permit found".
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Station velocity v2 shows cleaned percentile ranges
**Source:** src/station_velocity_v2.py, src/tools/estimate_timeline.py
**User:** expediter | architect
**Starting state:** User asks for a timeline estimate with fire_review trigger
**Goal:** Get station-level velocity data for SFFD showing p25-p75 range
**Expected outcome:** Timeline estimate includes a "Station-Level Plan Review Velocity" section with SFFD stats showing typical range and median days. Data note mentions post-2018, deduped, excludes administrative.
**Edge cases seen in code:** If station_velocity_v2 table is empty or missing, falls back to v1 (no station section shown). If trigger maps to multiple stations, all are shown.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Velocity v2 separates initial review from revision cycles
**Source:** src/station_velocity_v2.py
**User:** expediter
**Starting state:** Station velocity data has been computed
**Goal:** See different timelines for initial plan review vs revision rounds
**Expected outcome:** estimate_timeline shows initial review velocities by default. Revision cycle data exists in DB separately (metric_type='revision') with typically longer durations.
**Edge cases seen in code:** Stations with <10 revision records are excluded (MIN_SAMPLES threshold). Some stations have zero revisions (only initial review).
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Velocity refresh cron deduplicates reassignment rows
**Source:** src/station_velocity_v2.py
**User:** admin
**Starting state:** Admin triggers /cron/velocity-refresh
**Goal:** Velocity baselines use one data point per permit+station+addenda, not inflated by reassignment dupes
**Expected outcome:** For a permit that was reassigned 5 times at CPB (different reviewers), only the latest finish_date is used. Sample counts reflect unique permit-station pairs.
**Edge cases seen in code:** ROW_NUMBER() partitions by (application_number, station, addenda_number) with ORDER BY finish_date DESC. If all finish_dates are NULL, row is excluded entirely.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Velocity v2 excludes garbage data
**Source:** src/station_velocity_v2.py
**User:** admin
**Starting state:** Addenda table contains pre-2018 data, Administrative pass-throughs, and >365 day outliers
**Goal:** Velocity baselines reflect actual plan review work, not administrative routing noise
**Expected outcome:** Pre-2018 records excluded. "Administrative" and "Not Applicable" review results excluded. Durations > 365 days excluded as outliers. Negative durations (finish < arrive) excluded.
**Edge cases seen in code:** 90.6% of addenda rows have NULL review_results — these ARE included (they're real routing steps). Date range in raw data spans 1721-2205 (garbage dates) — filtered by 2018+ arrive date.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Estimate timeline degrades gracefully without v2 data
**Source:** src/tools/estimate_timeline.py
**User:** expediter | homeowner
**Starting state:** station_velocity_v2 table doesn't exist (fresh deploy or DuckDB-only)
**Goal:** User still gets a useful timeline estimate
**Expected outcome:** Falls back to v1 percentiles from timeline_stats table. If that also fails, shows knowledge-based fallback ranges. No station velocity section shown. No errors.
**Edge cases seen in code:** Three fallback levels: v2 station velocity → v1 timeline_stats → knowledge-based ranges. Source citations reflect which data was actually used.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Property health lookup by block/lot
**Source:** src/tools/property_health.py, src/signals/pipeline.py
**User:** expediter | architect
**Starting state:** Signal pipeline has run at least once; property_health table populated
**Goal:** User asks about health status of a specific parcel
**Expected outcome:** Returns tier label (HIGH RISK/AT RISK/BEHIND/SLOWER/ON TRACK), signal count, individual signal table with type/severity/permit/detail, and recommended actions appropriate to tier.
**Edge cases seen in code:** Property with no signals returns "No health data" with explanation about nightly pipeline. Address lookup resolves to block/lot via permits table. DB unavailable returns graceful error.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: High-risk compound detection
**Source:** src/signals/aggregator.py, src/signals/detector.py
**User:** expediter | admin
**Starting state:** Property has permits with Issued Comments hold AND open Notice of Violation
**Goal:** System correctly identifies convergent risk
**Expected outcome:** Property tier is HIGH_RISK (not just AT_RISK). Signal table shows both independent risk signals. Recommended actions include "Immediate review" and "multiple independent risk factors converging."
**Edge cases seen in code:** Two at_risk signals from the SAME compounding type = AT_RISK not HIGH_RISK. hold_stalled (behind severity) does NOT compound. complaint (slower) does NOT compound. Need 2+ unique types from COMPOUNDING_TYPES set.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Morning brief v2/v1 health fallback
**Source:** web/brief.py (property snapshot section)
**User:** homeowner | expediter
**Starting state:** User has watched properties; signal pipeline may or may not have run
**Goal:** Morning brief shows property health cards with correct tier
**Expected outcome:** If property_health table exists and has data for the property's block/lot, uses pre-computed v2 tier (including high_risk). If table missing or empty, falls back to v1 per-permit severity scoring. No errors either way.
**Edge cases seen in code:** v2 adds "high_risk" tier that v1 doesn't have. health_order map includes high_risk=4. Synthetic severity_score (0-100) derived from v2 tier for sorting. Mixed v1/v2 properties on same brief if some block/lots are in property_health and others aren't.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Signal pipeline cron endpoint
**Source:** web/app.py /cron/signals, src/signals/pipeline.py
**User:** admin
**Starting state:** Production database with permits, addenda, violations, inspections, complaints tables populated
**Goal:** Nightly cron triggers signal detection and property health computation
**Expected outcome:** POST /cron/signals with CRON_SECRET returns JSON with total_signals, properties count, tier_distribution, and per-detector stats. property_health table is refreshed (truncate + rebuild). Idempotent — running twice produces same results.
**Edge cases seen in code:** Individual detector failures are caught and logged (count=-1) without crashing pipeline. Empty tables produce zero stats. DuckDB sequences for auto-increment IDs. ON CONFLICT upsert without CURRENT_TIMESTAMP in DuckDB.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Detector handles mixed date types
**Source:** src/signals/detector.py
**User:** admin
**Starting state:** Database has dates stored as both strings and date objects (DuckDB returns date objects, Postgres may return strings)
**Goal:** Detectors format dates correctly in signal detail strings
**Expected outcome:** All detector detail strings show dates as "YYYY-MM-DD" regardless of whether the DB returns a date object or string. No "object is not subscriptable" errors.
**Edge cases seen in code:** DuckDB returns datetime.date objects that can't be sliced with [:10]. Fix: wrap in str() before slicing. Affects hold_stalled_planning, hold_stalled, stale_with_activity, stale_no_activity detectors.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Anonymous user discovers site via landing page
**Source:** web/templates/landing.html, web/app.py (index route)
**User:** homeowner
**Starting state:** User has no account, visits sfpermits.ai for the first time
**Goal:** Understand what the tool offers and search for their address
**Expected outcome:** Landing page renders with hero, search box, feature cards, and stats. Search box submits to /search and returns public permit results.
**Edge cases seen in code:** Empty query redirects to home; rate limiting applies to /search
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Anonymous user searches address and sees public results
**Source:** web/app.py (public_search route), web/templates/search_results_public.html
**User:** homeowner
**Starting state:** User is on landing page, not logged in
**Goal:** Look up permit history for their address
**Expected outcome:** Public results show basic permit data with locked premium feature cards (Property Report, Watch & Alerts, AI Analysis) and sign-up CTAs
**Edge cases seen in code:** Intent classifier may route query as general knowledge question instead of address lookup; no-results case shows helpful message
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Authenticated user bypasses landing page
**Source:** web/app.py (index route)
**User:** expediter | homeowner | architect
**Starting state:** User is logged in with a session
**Goal:** Access the full app dashboard
**Expected outcome:** Home route serves index.html (full app) instead of landing.html; all premium features visible
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Anonymous user tries to access premium feature
**Source:** web/app.py (@login_required decorator on premium routes)
**User:** homeowner
**Starting state:** User has no account, tries to visit /brief, /portfolio, /consultants, or /account/analyses
**Goal:** Access premium content without logging in
**Expected outcome:** User is redirected to /auth/login. After signing up and logging in, they can access the feature.
**Edge cases seen in code:** /health, /search, /, and /auth/* remain public; /report/<block>/<lot> remains public
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Authenticated user searching via /search gets redirected
**Source:** web/app.py (public_search route)
**User:** expediter | architect
**Starting state:** User is logged in and navigates to /search?q=123+Main+St (e.g., from a shared link)
**Goal:** See full search results, not the limited public view
**Expected outcome:** User is 302-redirected to /?q=123+Main+St to use the full conversational search experience
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: TESTING not set — test-login endpoint does not leak
**Source:** web/auth.py + web/app.py (handle_test_login, auth_test_login)
**User:** homeowner | architect | any unauthenticated user
**Starting state:** App running in production (TESTING env var not set)
**Goal:** Attempt to access /auth/test-login
**Expected outcome:** HTTP 404 — the endpoint does not exist on production. No information about the endpoint or secret is disclosed in the response body.
**Edge cases seen in code:** TESTING="" (empty string) also returns 404; TESTING=false also returns 404
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Every page shows yellow staging banner when ENVIRONMENT=staging
**Source:** web/app.py (inject_environment context processor) + templates/index.html, landing.html, auth_login.html
**User:** expediter | admin
**Starting state:** App deployed to Railway staging service with ENVIRONMENT=staging
**Goal:** Navigate through the app (homepage, login page, main search page)
**Expected outcome:** A yellow banner reading "STAGING ENVIRONMENT — changes here do not affect production" is visible at the top of every page. Banner is NOT present on production.
**Edge cases seen in code:** Default value when ENVIRONMENT not set is "production" (no banner)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Desktop CC POSTs correct test secret and gets admin session
**Source:** web/auth.py (handle_test_login) + web/app.py (auth_test_login route)
**User:** admin (automated / Desktop CC RELAY)
**Starting state:** Staging app running with TESTING=true and TEST_LOGIN_SECRET configured
**Goal:** Authenticate as test-admin@sfpermits.ai without email magic link flow
**Expected outcome:** POST to /auth/test-login with correct JSON body returns HTTP 200, sets a valid session cookie, and the session is authenticated as test-admin@sfpermits.ai with is_admin=True. Subsequent requests to /account and /admin succeed without redirect.
**Edge cases seen in code:** User is created if they don't exist yet; admin flag is force-set to True for the default test-admin persona
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Kill switch blocks AI endpoints and returns 503
**Source:** web/cost_tracking.py (@rate_limited decorator, set_kill_switch) + web/app.py (@_rate_limited_ai on /ask)
**User:** expediter | homeowner
**Starting state:** Admin has activated the kill switch (set_kill_switch(True))
**Goal:** User submits a question via /ask
**Expected outcome:** HTTP 503 is returned with an error message explaining AI features are temporarily unavailable. Basic permit search and lookup still work. Kill switch does NOT block non-AI routes.
**Edge cases seen in code:** The kill switch only blocks "ai", "plans", and "analyze" rate types — "lookup" type is not blocked.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin dashboard shows today's Claude API spend
**Source:** web/cost_tracking.py (get_cost_summary, log_api_call) + templates/admin_costs.html
**User:** admin
**Starting state:** One or more AI calls have been made today (logged via log_api_call)
**Goal:** Admin navigates to /admin/costs
**Expected outcome:** Dashboard shows today's spend (non-zero), the endpoint breakdown, and the kill switch status. Non-admin users get 403.
**Edge cases seen in code:** If api_usage table is empty (no calls today), cost shows $0.0000 with empty endpoint list — not an error state.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Cost auto-triggers kill switch when daily spend exceeds threshold
**Source:** web/cost_tracking.py (_check_cost_thresholds, COST_KILL_THRESHOLD)
**User:** system (automated)
**Starting state:** COST_KILL_THRESHOLD set to $20.00/day; daily spend is $19.99
**Goal:** A new API call is logged that pushes daily spend to $20.01
**Expected outcome:** Kill switch automatically activates. Subsequent /ask requests return 503. Admin can see kill switch is active on /admin/costs dashboard.
**Edge cases seen in code:** Kill switch only auto-activates once — subsequent calls while kill switch is already active don't re-trigger the activation logic.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Per-user rate limit is separate from IP rate limit
**Source:** web/cost_tracking.py (check_rate_limit, _user_rate_buckets, _get_user_key)
**User:** expediter (logged in)
**Starting state:** Two different users logged in from the same IP address
**Goal:** Each user makes 5 AI requests within 60 seconds (RATE_LIMIT_AI=5)
**Expected outcome:** Both users can make up to 5 requests each before being rate-limited. User A hitting their limit does not affect User B's quota. Rate buckets key on (user_id, rate_type), not IP.
**Edge cases seen in code:** Anonymous (not logged in) users key on IP address — multiple anonymous users from same IP share a bucket.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Pipeline health dashboard shows critical when cron hasn't run
**Source:** web/pipeline_health.py, /admin/pipeline route
**User:** admin
**Starting state:** Nightly cron has not run in 3+ days (Railway cron failure or outage)
**Goal:** Admin wants to see pipeline status at a glance and trigger a manual re-run
**Expected outcome:** /admin/pipeline page shows "CRITICAL" banner, lists the last failed run, and the manual run button triggers a fresh nightly job
**Edge cases seen in code:** No cron_log rows at all (first deploy); stuck jobs from previous crash
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Addenda staleness detected in morning brief
**Source:** web/brief.py pipeline_health section, web/pipeline_health.py check_data_freshness
**User:** expediter | admin
**Starting state:** Addenda data_as_of is >5 days old (sync gap)
**Goal:** User opens morning brief and sees a data freshness warning
**Expected outcome:** Brief shows a pipeline health warning indicating addenda data is stale, with the last known data_as_of date
**Edge cases seen in code:** Pipeline check fails silently — brief still renders without health section
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck cron job swept before next nightly run
**Source:** scripts/nightly_changes.py sweep_stuck_cron_jobs
**User:** admin (system-level)
**Starting state:** Previous nightly run crashed (OOM kill, Railway restart) leaving status='running' in cron_log
**Goal:** Next nightly run starts cleanly without false "running" state in cron_log
**Expected outcome:** sweep_stuck_cron_jobs marks old 'running' entry as 'failed' before starting; swept_stuck_jobs count > 0 in result
**Edge cases seen in code:** Multiple stuck jobs from repeated crashes; query errors during sweep (non-fatal, returns 0)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: SODA fetch retry recovers from transient network error
**Source:** scripts/nightly_changes.py fetch_with_retry
**User:** admin (system-level)
**Starting state:** SODA API returns a connection error on first attempt
**Goal:** Nightly run completes successfully despite transient error
**Expected outcome:** fetch_with_retry retries with exponential backoff; second attempt succeeds; result shows attempts=2 in step_results
**Edge cases seen in code:** All retries exhausted → returns empty list with ok=False but doesn't crash entire run
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Addenda step failure isolated from permit processing
**Source:** scripts/nightly_changes.py run_nightly step isolation
**User:** admin (system-level)
**Starting state:** Addenda SODA endpoint is temporarily unavailable
**Goal:** Permit changes still get processed even when addenda step fails
**Expected outcome:** run_nightly logs warning for addenda step, processes permit changes normally, logs success with addenda_inserted=0
**Edge cases seen in code:** detect_addenda_changes fails (DB error); fetch_recent_addenda fails (network)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Migration runner skips on DuckDB backend
**Source:** scripts/run_prod_migrations.py
**User:** admin / developer
**Starting state:** Dev environment with DuckDB backend (no PostgreSQL connection)
**Goal:** Run migrations without errors on local dev
**Expected outcome:** All SQL-file migrations are skipped with "DuckDB mode" reason. signals migration also reports skipped. Exit code 0.
**Edge cases seen in code:** migrate_signals.py explicitly checks BACKEND != "postgres" and returns ok=True with skipped=True
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Migration runner --only flag targets single migration
**Source:** scripts/run_prod_migrations.py
**User:** admin / developer
**Starting state:** Production Postgres DB — signals tables might not exist yet
**Goal:** Run only the signals migration without running all other migrations
**Expected outcome:** Only the signals migration runs; SQL schema migrations and other steps are not touched. Output shows "1 migration(s) to run".
**Edge cases seen in code:** --only with unknown name returns exit code 2 with helpful error message listing valid names
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile user navigates to landing page without horizontal scroll
**Source:** web/static/mobile.css, web/templates/*.html
**User:** homeowner (mobile)
**Starting state:** User opens sfpermits.ai on iPhone SE (375px viewport)
**Goal:** Search for a permit address on a phone without needing to scroll sideways
**Expected outcome:** No horizontal overflow. Nav badges are scrollable. Search box stacks correctly below 480px. All touch targets are >= 44px.
**Edge cases seen in code:** iOS Safari auto-zooms if input font-size < 16px — mobile.css sets min 16px on all inputs
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Velocity dashboard table scrollable on mobile
**Source:** web/templates/velocity_dashboard.html, web/static/mobile.css
**User:** expediter (mobile)
**Starting state:** User views the velocity dashboard on a 375px phone
**Goal:** Read the stalled permits table without the whole page overflowing
**Expected outcome:** Table is contained inside a scrollable .section container. Body does not overflow. Page-level horizontal scroll is absent.
**Edge cases seen in code:** velocity_dashboard tables do not have explicit overflow-x:auto wrappers (unlike report.html) — mobile.css adds it via .section overflow-x:auto
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin views cron endpoint docs to set up scheduler
**Source:** docs/cron-endpoints.md
**User:** admin
**Starting state:** Admin is setting up Railway cron or cron-job.org for nightly jobs
**Goal:** Quickly find the correct URL, auth header, and recommended run order for all cron endpoints
**Expected outcome:** docs/cron-endpoints.md provides exact curl commands, CRON_SECRET auth instructions, recommended schedule table, and future endpoints section
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Stale addenda data triggers morning brief warning
**Source:** Sprint 53B — FIX-STALENESS + FIX-BRIEF
**User:** expediter | architect | admin
**Starting state:** Addenda data_as_of is >3 days old (SODA outage or stale import)
**Goal:** User receives morning brief with visible pipeline health warning
**Expected outcome:** Morning brief email shows yellow/red banner above "What Changed" section with message about stale addenda data. Nightly script also logs STALENESS CHECK warning.
**Edge cases seen in code:** data_as_of can be None if addenda table is empty; far-future dates (2205) in SODA data won't trigger staleness; check runs inside try/except so failures don't crash nightly job
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly cron failure triggers Telegram alert
**Source:** Sprint 53B — FIX-CRON
**User:** admin
**Starting state:** Nightly cron workflow runs on schedule, one or more steps fail (e.g. /cron/nightly returns 500)
**Goal:** Tim receives Telegram notification within 5 minutes of failure
**Expected outcome:** Telegram message with "Nightly Cron Failed" text and link to GitHub Actions run. Non-critical step failures (signals, velocity, RAG) emit ::warning but don't trigger Telegram. Only job-level failure triggers alert.
**Edge cases seen in code:** Telegram secrets may not be configured (step skips gracefully); signals and velocity are non-critical (::warning not ::error)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Signal pipeline runs on prod via nightly cron
**Source:** Sprint 53B — FIX-CRON + Phase 1 migrations
**User:** admin
**Starting state:** Signal tables exist on prod (migrated), nightly cron fires on schedule
**Goal:** /cron/signals runs, detects permit signals, computes property health tiers
**Expected outcome:** signal_types seeded (13 rows), permit_signals populated based on current permit data, property_health tiers computed. Pipeline health reports "ok" status.
**Edge cases seen in code:** Signal pipeline uses DuckDB-style conn.execute() — may need compatibility fix for psycopg2 on Postgres; pipeline truncates tables before each run (full refresh, not incremental)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin runs /cron/migrate after deploy
**Source:** Amendment C — /cron/migrate endpoint
**User:** admin
**Starting state:** New code deployed to production with pending schema changes
**Goal:** Run all database migrations via HTTP endpoint instead of manual CLI
**Expected outcome:** All 8 migrations execute, response JSON shows each migration's ok/skipped status, idempotent re-runs produce no errors
**Edge cases seen in code:** DuckDB backend skips all migrations (returns skipped=true), migration runner catches per-migration exceptions without halting
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Test-login correctly assigns admin based on email pattern
**Source:** Amendment D — handle_test_login fix
**User:** admin
**Starting state:** Test user exists in database with incorrect is_admin flag
**Goal:** Test-login endpoint always sets correct admin status regardless of whether user already exists
**Expected outcome:** "test-admin" in email -> is_admin=true; any other email -> is_admin=false; applies to both new and existing users
**Edge cases seen in code:** Race condition if two test-logins fire simultaneously for same email; DuckDB vs Postgres placeholder difference handled by dual backend pattern
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Signal pipeline runs on Postgres without placeholder errors
**Source:** Q3 — Signal Pipeline Postgres Fix
**User:** admin
**Starting state:** Signal pipeline configured, Postgres backend active, permits/addenda/violations tables populated
**Goal:** /cron/signals completes successfully on Postgres production database
**Expected outcome:** All 12 detectors run, signals inserted with %s placeholders, property health tiers computed, no placeholder errors
**Edge cases seen in code:** _ensure_signal_tables() correctly skips on Postgres; _pg_execute() commits after each statement; detector._execute() handles None params with empty tuple
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Route manifest accurately reflects all app routes
**Source:** Q1 — Route Manifest Generator
**User:** admin
**Starting state:** web/app.py has 100+ routes with various auth levels
**Goal:** Generate a complete, accurate route manifest for QA automation
**Expected outcome:** siteaudit_manifest.json contains all routes with correct auth_level classification, template references, and 4 user journeys
**Edge cases seen in code:** Admin routes detected by path prefix OR body guard pattern; multi-decorator routes correctly classified; routes with dynamic segments preserved
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CHECKCHAT blocked without QA screenshots
**Source:** Sprint 54B enforcement hooks — stop-checkchat.sh
**User:** admin
**Starting state:** Agent has built a feature and is attempting to close session with CHECKCHAT
**Goal:** Session cannot close without Playwright QA evidence
**Expected outcome:** Stop hook detects `## CHECKCHAT` header, checks qa-results/screenshots/ for PNG files with valid magic bytes, blocks with exit 2 and specific failure messages if no screenshots exist. Agent gets one retry (stop_hook_active bypass).
**Edge cases seen in code:** DeskCC sessions (contain "DeskRelay" but not "BUILD") skip screenshot requirement; stop_hook_active=true provides infinite loop escape; temp file (.stop_hook_fired) is backup loop prevention
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Descoped item blocked without user approval
**Source:** Sprint 54B enforcement hooks — plan-accountability.sh
**User:** admin
**Starting state:** Agent has descoped a plan item and is writing CHECKCHAT report
**Goal:** Descoped items require documented user approval before session can close
**Expected outcome:** Plan accountability hook scans CHECKCHAT message for descoping language ("descoped", "deferred", "out of scope", "dropped", "removed from scope", "moved to sprint"). Each match must have approval evidence within 2 lines ("user approved", "per user", "tim approved", "tim confirmed"). BLOCKED items must have 3-attempt documentation. Missing evidence blocks CHECKCHAT.
**Edge cases seen in code:** Context window of 2 lines for approval evidence; multiple descoped items each need individual approval; BLOCKED items need different evidence format (attempt counts)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Normal development unaffected by enforcement hooks
**Source:** Sprint 54B enforcement hooks — block-playwright.sh
**User:** admin
**Starting state:** Developer is working on code in a Claude Code session (not during CHECKCHAT)
**Goal:** Hooks do not interfere with normal git, pytest, python, curl commands
**Expected outcome:** Non-CHECKCHAT Stop events pass through (exit 0). Non-Playwright Bash commands pass through (git, pytest, curl, pip all allowed). Write operations outside qa-results/ are not scanned for descope language. Only Playwright execution commands (chromium.launch, page.goto, etc.) are blocked in the main agent — pytest is allowed even if it internally uses Playwright.
**Edge cases seen in code:** Allowed patterns checked before blocked patterns in block-playwright.sh; subagent bypass via CLAUDE_SUBAGENT=true or nested worktree CWD detection; pip install playwright is explicitly allowed
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Build/Verify separation enforced
**Source:** Sprint 54B enforcement hooks — block-playwright.sh
**User:** admin
**Starting state:** Main agent attempts to run Playwright directly (not in a QA subagent)
**Goal:** Main agent cannot self-certify QA — Playwright must run in subagents
**Expected outcome:** PreToolUse hook on Bash detects Playwright patterns (playwright, chromium.launch, page.goto, page.screenshot, page.click, sync_playwright) and blocks with exit 2. Agent must use Task tool to spawn QA subagent. Subagents are allowed through via CLAUDE_SUBAGENT env var or nested worktree detection.
**Edge cases seen in code:** Pattern matching is case-insensitive for blocked patterns; allowed patterns override blocked (so "grep playwright" passes); "expect(page" blocked to prevent assertion commands in main agent
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Planning record enriches property report
**Source:** Sprint 54C — planning_records table + block/lot join
**User:** expediter
**Starting state:** A property at block/lot 3512/001 has both a building permit and a CUA planning record
**Goal:** When looking up the property, see planning entitlement data alongside building permits
**Expected outcome:** Property lookup returns planning records joined via block/lot, showing record_type, record_status, and assigned_planner
**Edge cases seen in code:** Some planning records have NULL block/lot; projects vs non-projects have different field completeness
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Fire permit signal available for property
**Source:** Sprint 54C — fire_permits table
**User:** expediter
**Starting state:** A property has had fire permits issued (stored by permit_address, no block/lot)
**Goal:** Fire permit data is queryable and accessible for properties that have fire permits
**Expected outcome:** Fire permits are searchable by permit_address text; fire signal data lands in the database for future severity scoring integration
**Edge cases seen in code:** No block/lot on fire permits — cross-referencing requires address parsing (follow-up); permit_address is free-text ("1 Citywide", "123 MAIN ST")
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Block/lot join between boiler and building permits produces matches
**Source:** Sprint 54C — boiler_permits table + cross-ref check
**User:** expediter
**Starting state:** Boiler permits and building permits both exist for the same parcel
**Goal:** Cross-reference boiler and building permits to get complete DBI 4-permit coverage
**Expected outcome:** Block/lot join between boiler_permits and permits produces >95% match rate, confirming data quality
**Edge cases seen in code:** 97.8% match rate observed — 2.2% of boiler permits have block/lot values that don't match any building permit
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Tax roll zoning code available for property context
**Source:** Sprint 54C — tax_rolls table
**User:** expediter
**Starting state:** A property has tax roll data with zoning_code, assessed values, and physical characteristics
**Goal:** Look up zoning code and property characteristics to determine permit routing requirements
**Expected outcome:** Tax roll query returns zoning_code, number_of_units, lot_area, assessed values for the latest tax year
**Edge cases seen in code:** Composite PK (block, lot, tax_year) — must filter to latest year; 3-year filter means only 2022+ data available
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Bulk SODA ingest handles memory-constrained environments
**Source:** Sprint 54C — streaming batch flush for tax_rolls + gunicorn timeout
**User:** admin
**Starting state:** Railway container has limited memory; tax rolls dataset is 636K rows
**Goal:** Ingest all 4 new datasets via cron endpoints without OOM
**Expected outcome:** All ingest endpoints complete successfully; tax rolls uses streaming pagination with 50K-row batch flushes; gunicorn timeout increased to 600s for long-running ingests
**Edge cases seen in code:** Original flat fetch caused OOM on 636K rows; batch flush every 50K rows keeps memory bounded; gunicorn worker killed at 120s timeout before fix
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: CRON_SECRET with trailing whitespace still authenticates
**Source:** web/app.py _check_api_auth() — Sprint 54 post-mortem Amendment A
**User:** admin
**Starting state:** Railway CRON_SECRET env var has trailing whitespace (e.g. newline from copy-paste)
**Goal:** Call any /cron/* endpoint with the visible secret value
**Expected outcome:** Auth succeeds because _check_api_auth() strips whitespace from both the header and the env var before comparing
**Edge cases seen in code:** GitHub Actions auto-trims secrets so it always worked; local curl with railway variable list output failed silently with 403; no diagnostic logging existed before this fix
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Failed cron auth logs diagnostic info
**Source:** web/app.py _check_api_auth() — Sprint 54 post-mortem Amendment A
**User:** admin
**Starting state:** A request hits a CRON_SECRET-protected endpoint with an invalid or mismatched token
**Goal:** Diagnose why auth failed without exposing the secret
**Expected outcome:** Railway logs show "API auth failed: token_len=X expected_len=Y path=/cron/..." — length mismatch indicates whitespace, same length indicates wrong value
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: All cron endpoints use consolidated auth function
**Source:** web/app.py — Sprint 54 post-mortem Amendment B
**User:** admin
**Starting state:** New cron endpoint is added to app.py
**Goal:** Auth behavior is consistent across all cron endpoints
**Expected outcome:** All cron endpoints call _check_api_auth() instead of inline auth; only pipeline-health POST has admin-session fallback (inline with .strip()); a fix to _check_api_auth() automatically applies to all endpoints
**Edge cases seen in code:** Before fix, 4 endpoints had copy-pasted auth that diverged from _check_api_auth(); a fix to the shared function missed the inline copies
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Full dataset coverage — 22 SODA datasets all ingestible
**Source:** src/ingest.py — Sprint 55A
**User:** admin
**Starting state:** All 22 SODA datasets cataloged; previously 5 lacked ingest capability
**Goal:** Admin triggers a full ingest run and all 22 datasets complete successfully
**Expected outcome:** All 22 tables populated, ingest_log has 22 rows with recent timestamps, no dataset returns 0 records
**Edge cases seen in code:** development_pipeline uses bpa_no as primary key with fallback to case_no for records without BPA; dwelling_completions lacks data_as_of field in SODA response
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Street-use permits streaming ingest under memory pressure
**Source:** src/ingest.py ingest_street_use_permits()
**User:** admin
**Starting state:** ~1.2M street-use permit records in SODA; Railway container has ~512MB RAM
**Goal:** Admin triggers /cron/ingest-street-use and all records load without OOM
**Expected outcome:** All records ingested in batches of 50K, total count reported correctly in response JSON, elapsed time reasonable
**Edge cases seen in code:** STREET_USE_BATCH_FLUSH=50K mirrors tax_rolls pattern; unique_identifier used as PK to handle permit_number duplicates across different CNNs
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Affordable housing pipeline supports entitlement research
**Source:** src/ingest.py _normalize_affordable_housing()
**User:** expediter | architect
**Starting state:** Affordable housing table populated with ~194 projects
**Goal:** Expediter looks up whether a specific planning case number has affordable housing requirements attached
**Expected outcome:** Record found by planning_case_number, shows total_project_units, affordable_units, affordable_percent, construction_status
**Edge cases seen in code:** SODA field uses 'mohcd_affordable_units' not 'affordable_units'; 'plannning_approval_address' has a typo in SODA (3 n's)
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: New cron endpoints reject requests without auth token
**Source:** web/app.py — 7 new cron endpoints
**User:** admin
**Starting state:** 7 new cron endpoints deployed: electrical, plumbing, street-use, development-pipeline, affordable-housing, housing-production, dwelling-completions
**Goal:** Unauthenticated caller (e.g. accidental browser visit) cannot trigger ingest
**Expected outcome:** All 7 endpoints return HTTP 403 without Authorization header; with wrong token also 403; with correct CRON_SECRET returns 200 or triggers ingest
**Edge cases seen in code:** _check_api_auth() uses .strip() on both header and env var to prevent trailing whitespace mismatch (learned from Sprint 54 CRON_SECRET postmortem)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: predict_permits zoning code routing lookup
**Source:** scripts/seed_reference_tables.py, src/tools/predict_permits.py
**User:** expediter | architect
**Starting state:** ref_zoning_routing table seeded with SF zoning codes
**Goal:** User asks which agencies must review a permit for a parcel with known zoning code (e.g. RC-4)
**Expected outcome:** Tool correctly identifies that RC-4 requires Planning + SFFD review and surfaces this alongside the permit prediction; RH-1 (single-family) does not require mandatory planning review for interior alterations
**Edge cases seen in code:** Historic district flag (HCD code) should trigger Planning preservation review; zoning codes with suffixes like RH-1(D) must match exactly
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: cron seed-references endpoint re-seeds without data loss
**Source:** web/app.py /cron/seed-references, scripts/seed_reference_tables.py
**User:** admin
**Starting state:** Reference tables already seeded from a previous deploy
**Goal:** Admin re-runs seed endpoint after a code update to refresh reference data
**Expected outcome:** Endpoint returns 200 with row counts for all 3 tables; row counts remain the same (no duplicates); idempotent behavior confirmed
**Edge cases seen in code:** DuckDB uses INSERT OR REPLACE; Postgres uses ON CONFLICT DO UPDATE; form/trigger tables use DELETE + re-insert for simplicity
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: migration registry includes reference_tables as last step
**Source:** scripts/run_prod_migrations.py
**User:** admin
**Starting state:** Production database has run all prior migrations
**Goal:** Deploy triggers run_prod_migrations which creates and seeds the 3 reference tables
**Expected outcome:** Migration completes with ok=True; tables created; row counts returned; re-running migration is safe (idempotent)
**Edge cases seen in code:** Migration skips table creation in DuckDB mode if tables already exist (CREATE TABLE IF NOT EXISTS); seed step runs in both backends
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: restaurant project triggers all required agencies
**Source:** scripts/seed_reference_tables.py ref_agency_triggers
**User:** expediter | architect
**Starting state:** ref_agency_triggers seeded; user describes a restaurant change of use project
**Goal:** predict_permits correctly identifies all routing agencies for a restaurant project
**Expected outcome:** Result includes DBI, Planning, SFFD (Fire), DPH (Public Health), DBI Mechanical/Electrical, and conditionally SFPUC + DPW/BSM; all backed by queryable trigger table entries
**Edge cases seen in code:** restaurant keyword appears in triggers for 5 different agencies; DPH must approve before permit issuance per G-20 Rule C
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Electrical permit surfaces in permit search results
**Source:** Sprint 55A — electrical/plumbing ingest into permits table
**User:** expediter
**Starting state:** Electrical permits from SODA (`ftty-kx6y`) have been ingested into the permits table
**Goal:** Search for electrical permits at a known address and see trade permits alongside building permits
**Expected outcome:** permit_lookup and search_permits return electrical permits with permit_type_definition indicating "electrical"; results appear in the same permit table results as building permits without any special filter required
**Edge cases seen in code:** Electrical permits use the same permits table — no separate endpoint; permit_type_definition differentiates trade type
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Plumbing permit surfaces in permit search results
**Source:** Sprint 55A — plumbing ingest into permits table
**User:** expediter
**Starting state:** Plumbing permits from SODA (`a6aw-rudh`) have been ingested into the permits table
**Goal:** Search for plumbing permits at a known address and confirm trade permits appear
**Expected outcome:** search_permits returns plumbing permits with permit_type_definition indicating "plumbing"; all 512K plumbing records are queryable through the same permit search interface
**Edge cases seen in code:** Same permits table as building and electrical — no schema distinction, only permit_type_definition differs
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Property lookup returns instant local tax data without SODA call
**Source:** Sprint 55C — property_lookup local tax_rolls DB fallback
**User:** expediter | homeowner
**Starting state:** tax_rolls table is populated for a known block/lot (e.g., 3512/001); SODA API is unreachable
**Goal:** Look up property characteristics (zoning code, lot area, assessed value) for a parcel
**Expected outcome:** property_lookup returns zoning_code, number_of_units, lot_area, and assessed values from local tax_rolls DB; response is instant (no SODA round-trip); response includes "source: local" or equivalent indicator
**Edge cases seen in code:** Fallback only triggers when local data exists; missing block/lot causes SODA fallback; composite PK (block, lot, tax_year) requires latest-year filter
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Morning brief shows planning context for watched parcels
**Source:** Sprint 55D — _get_planning_context() in web/brief.py
**User:** admin
**Starting state:** User has watch items for one or more parcels; planning_records table has CUA or variance records for those block/lots
**Goal:** Open morning brief and see active planning entitlements alongside building permit activity
**Expected outcome:** Morning brief includes a planning_context section showing record_type, record_status, assigned_planner for each watched parcel that has a planning record; parcels without planning records do not appear in this section
**Edge cases seen in code:** Some planning records have NULL block/lot — those cannot be joined to watch items; projects vs non-projects have different field completeness
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Compliance calendar surfaces expiring boiler permits in morning brief
**Source:** Sprint 55D — _get_compliance_calendar() in web/brief.py
**User:** admin
**Starting state:** boiler_permits table has records with expiration dates within 90 days of today; user has watched parcels that include those addresses
**Goal:** Morning brief proactively surfaces boiler permit renewals needed within the next 90 days
**Expected outcome:** Morning brief compliance_calendar section lists property address, permit number, expiration date, and days remaining for each expiring boiler permit; items are sorted by days remaining (soonest first)
**Edge cases seen in code:** 90-day window is the threshold; boiler permits do not have block/lot — address matching is required; parcels without expiring boilers do not appear in this section
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Morning brief data quality section shows cross-reference match rates
**Source:** Sprint 55D — _get_data_quality() in web/brief.py
**User:** admin
**Starting state:** boiler_permits, planning_records, and permits tables are all populated
**Goal:** Admin checks morning brief to see if the database cross-reference health is acceptable
**Expected outcome:** Morning brief data_quality section shows boiler↔permits match rate and planning↔permits match rate as percentages; rates below 5% trigger a warning indicator; rates above 5% show green/ok status
**Edge cases seen in code:** Match rates computed via block/lot join; new ingest can temporarily lower rates before full load completes
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly detects planning record status change for watched parcel
**Source:** Sprint 55D — planning monitoring in scripts/nightly_changes.py
**User:** admin
**Starting state:** A planning record for a watched parcel changes status from "filed" to "approved" in SODA
**Goal:** Next morning brief email includes notification of the planning status change
**Expected outcome:** Nightly cron fetches latest planning records from SODA, compares to stored state, writes a row to permit_changes with change_type "planning_status_change", field_name "record_status", old_value "filed", new_value "approved"; morning brief includes the change
**Edge cases seen in code:** Planning records use planning_case_number as the stable identifier; some status fields may be null in SODA responses (handled as empty string)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Reference table seed is idempotent on repeated calls
**Source:** Sprint 55B — scripts/seed_reference_tables.py + /cron/seed-references
**User:** admin
**Starting state:** ref_zoning_routing, ref_permit_forms, and ref_agency_triggers tables are already seeded from a prior deploy
**Goal:** Admin re-runs /cron/seed-references after a code update to pick up any new entries
**Expected outcome:** Endpoint returns 200 with row counts (29, 28, 38); row counts are identical to prior run (no duplicates created); DuckDB uses INSERT OR REPLACE, Postgres uses ON CONFLICT DO UPDATE — both are safe to re-run
**Edge cases seen in code:** ref_permit_forms and ref_agency_triggers use DELETE + re-insert for simplicity; idempotency guaranteed by unique key constraints
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: permit_lookup returns planning records for a parcel
**Source:** Sprint 55C — permit_lookup enriched with planning_records join
**User:** expediter | architect
**Starting state:** A parcel has both building permits and active planning records (e.g., a CUA conditional use authorization) in the database
**Goal:** Run permit_lookup for a known block/lot and see planning entitlements alongside building permit history
**Expected outcome:** permit_lookup response includes a planning_records section showing record_type, record_status, assigned_planner, and case number; building permit results appear in the same response; no duplicate calls needed
**Edge cases seen in code:** JOIN is on block/lot — planning records with NULL block/lot are excluded; some parcels have multiple open planning cases
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Homeowner gets instant permit preview without signing up
**Source:** web/app.py — /analyze-preview route, templates/landing.html
**User:** homeowner
**Starting state:** Unauthenticated user visits landing page with a remodel project in mind
**Goal:** Understand what permits are needed and how long it will take before committing to sign up
**Expected outcome:** User fills in project description, submits, sees review path (OTC vs in-house) and timeline estimate; three additional cards (fees, documents, risk) are shown locked with "Sign up free to unlock" CTA; no login required
**Edge cases seen in code:** Empty description redirects back to home; rate limit applies (10/min per IP); neighborhood is optional
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Kitchen remodel sees layout decision fork
**Source:** web/app.py — _detect_kitchen_bath(), analyze_preview route
**User:** homeowner
**Starting state:** Unauthenticated user on the preview page describes a kitchen remodel
**Goal:** Understand how fixture layout choice affects permit path and timeline
**Expected outcome:** Page shows a side-by-side fork comparison: "Keep existing layout → OTC, ~3-4 weeks" vs "Change layout → In-house, ~3-6 months"; decision is clearly tied to whether plumbing/gas lines move
**Edge cases seen in code:** Detection is keyword-based (kitchen, bath, sink, toilet, shower, etc.); non-kitchen projects do not show the fork
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Property owner with a Notice of Violation looks up their address
**Source:** web/app.py — public_search route, templates/search_results_public.html
**User:** homeowner
**Starting state:** Unauthenticated user received a NOV and arrives at the landing page via "Got a Notice of Violation?" CTA
**Goal:** Look up their property to see enforcement data
**Expected outcome:** Search results page shows a "Violation Lookup Mode" banner at the top; enforcement-related data is visibly highlighted; upsell to sign up for full complaint history and remediation steps
**Edge cases seen in code:** context=violation is a GET param; authenticated users are redirected to full search before template renders
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: New user sees welcome banner on first login
**Source:** web/app.py — auth_verify route, templates/index.html
**User:** homeowner | expediter
**Starting state:** User has just verified their magic link for the first time and has no watches yet
**Goal:** Understand where to start
**Expected outcome:** A dismissable welcome banner appears at the top of the home page saying "Welcome to sfpermits.ai! Start by searching an address or describing your project."; clicking Dismiss removes the banner permanently for this session
**Edge cases seen in code:** Banner only shows when show_onboarding_banner is in session AND onboarding_dismissed is not set; users with existing watches don't see it
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: User with 3+ watches gets brief enable prompt after adding a watch
**Source:** web/app.py — watch_add route, watch_brief_prompt, templates/fragments/brief_prompt.html
**User:** expediter | homeowner
**Starting state:** User has 2 watches and adds a third; brief_frequency is 'none'
**Goal:** Get reminded to enable the morning brief now that they have multiple properties tracked
**Expected outcome:** After watch is confirmed, a stronger prompt appears: "You're tracking 3 properties. Morning brief summarizes all of them." with an "Enable brief" link to account settings; users who already have brief enabled never see the prompt
**Edge cases seen in code:** Prompt is lazy-loaded via HTMX after watch confirmation; 1-watch shows soft prompt, 3+ shows strong prompt; prompt absent when already_enabled=True
**CC confidence:** medium
**Status:** PENDING REVIEW
