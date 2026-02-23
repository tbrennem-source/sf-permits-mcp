# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->

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
