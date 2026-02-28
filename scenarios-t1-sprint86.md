# Scenarios — T1 Sprint 86 (Agent: visual-qa structural mode)

## SUGGESTED SCENARIO: structural baseline capture on first run

**Source:** scripts/visual_qa.py — run_structural_qa(), check mode auto-save
**User:** admin
**Starting state:** No structural baseline files exist in qa-results/structural-baselines/
**Goal:** Run structural check against staging and establish baselines for the first time
**Expected outcome:** Fingerprint JSON files are created for each page/viewport combination; results summary shows "NEW BASELINE" for all pages; no FAIL status reported
**Edge cases seen in code:** If TEST_LOGIN_SECRET is absent, auth/admin pages are skipped with status "skip" rather than failing — baselines are only captured for reachable pages
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: structural diff detects layout skeleton change

**Source:** scripts/visual_qa.py — diff_fingerprints(), StructuralResult
**User:** admin
**Starting state:** Structural baselines exist for all pages; a developer then renames or removes a key CSS class from the landing page template (e.g. removes .obs-container from the main container)
**Goal:** Run structural QA to detect whether the layout skeleton changed without a pixel diff
**Expected outcome:** The affected page/viewport combinations show FAIL status with a diff entry describing the removed container class; other pages continue to show PASS; results markdown lists the specific class change
**Edge cases seen in code:** Only CSS classes on the first matched container are compared — changes to deeply nested containers are not detected
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: --structural-changed-only skips unaffected pages

**Source:** scripts/visual_qa.py — slugs_for_changed_files(), --structural-changed-only flag
**User:** admin (CI pipeline)
**Starting state:** Structural baselines exist for all 21 pages; git diff HEAD~1 shows only web/templates/admin/feedback.html was changed
**Goal:** Run structural QA in changed-only mode to skip unaffected pages and speed up CI
**Expected outcome:** Only the admin-feedback page is fingerprinted across all viewports; all other pages are omitted from the run; if no structural changes were made, the report shows PASS for admin-feedback only; total run time is proportionally shorter
**Edge cases seen in code:** If a shared template (base.html, nav.html, obsidian.css) is in the diff, all 21 pages are included regardless of the --structural-changed-only flag
**CC confidence:** medium
**Status:** PENDING REVIEW
