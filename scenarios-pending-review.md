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

---

## SUGGESTED SCENARIO: HIGH_RISK compound detection — NOV + stale permit
**Source:** src/signals/ (Session A — Severity v2)
**User:** expediter
**Starting state:** Property has an open NOV and an issued permit 2yr+ old with recent inspections
**Goal:** Property flagged as HIGH_RISK with both signals surfaced
**Expected outcome:** property_health shows tier=high_risk, signal_count=2, at_risk_count=2. Both nov and stale_with_activity signals appear in signals table. Morning brief shows AT RISK with v2 reason.
**Edge cases seen in code:** NOV must be non-closed status; stale_with_activity requires 2+ real inspections within 5yr AND issued 2yr+. If latest inspection is >5yr old, it's stale_no_activity (slower) instead.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Single at-risk signal stays at_risk (not high_risk)
**Source:** src/signals/aggregator.py (Session A — Severity v2)
**User:** expediter
**Starting state:** Property has one open NOV and no other signals
**Goal:** Property correctly classified as at_risk, not high_risk
**Expected outcome:** property_health tier=at_risk. Only 1 unique compounding type, so HIGH_RISK does not fire.
**Edge cases seen in code:** Two signals of the SAME type (e.g., 2 NOVs from different violations) still count as 1 unique compounding type → at_risk, not high_risk.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Complaint alone never triggers at_risk
**Source:** src/signals/aggregator.py (Session A — Severity v2)
**User:** homeowner
**Starting state:** Property has an open complaint but no NOV, no holds, no expired permits
**Goal:** Property shows as SLOWER, not AT RISK
**Expected outcome:** property_health tier=slower. Complaint is not in COMPOUNDING_TYPES, so it never compounds to high_risk even when combined with at_risk signals.
**Edge cases seen in code:** Complaint + NOV at same block_lot → the complaint detector's NOT EXISTS clause means the complaint signal is suppressed. Only the NOV signal fires.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: hold_stalled does not compound into HIGH_RISK
**Source:** src/signals/aggregator.py (Session A — Severity v2)
**User:** expediter
**Starting state:** Property has a non-planning station stall (30d-1yr) and an open NOV
**Goal:** Property shows at_risk, not high_risk
**Expected outcome:** hold_stalled has severity=behind and is NOT in COMPOUNDING_TYPES. Combined with NOV (at_risk), the property gets at_risk tier — not high_risk.
**Edge cases seen in code:** hold_stalled_planning IS in compounding types (station dwell >1yr at PPC/CP-ZOC/CPB). Only hold_stalled (non-planning, 30d-1yr) is excluded.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Nightly signal pipeline is idempotent
**Source:** src/signals/pipeline.py (Session A — Severity v2)
**User:** admin
**Starting state:** Signal pipeline has been run once via /cron/signals
**Goal:** Run the pipeline again and get the same results
**Expected outcome:** Pipeline truncates all signal tables before re-detecting. Running twice produces identical property_health rows. No duplicate signals accumulate.
**Edge cases seen in code:** Pipeline uses DELETE FROM (not TRUNCATE) for DuckDB compatibility. DuckDB doesn't support TRUNCATE. Postgres uses ON CONFLICT for upserts.
**CC confidence:** high
**Status:** PENDING REVIEW
