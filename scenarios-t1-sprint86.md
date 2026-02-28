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
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Design token lint detects computed color drift on staging
**Source:** scripts/design_lint.py --live mode
**User:** admin
**Starting state:** Staging environment is running; design_lint.py has --live flag available
**Goal:** Verify that a deployed page's rendered CSS colors match the token palette
**Expected outcome:** Running --live against staging reports any computed colors that deviate more than ±2 RGB channels from the expected ALLOWED_TOKENS_VARS values, producing medium-severity violations with selector and expected/actual color detail
**Edge cases seen in code:** Pages with no matching token selectors produce zero violations (not errors); pages that fail to load produce a medium "Page load failed" violation instead of crashing
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: axe-core WCAG AA contrast check catches insufficient contrast
**Source:** scripts/design_lint.py check_axe_contrast()
**User:** admin
**Starting state:** --live mode running against a page with --text-tertiary on interactive copy
**Goal:** Verify that axe-core detects and reports contrast ratio failures on rendered pages
**Expected outcome:** Each axe color-contrast violation is reported as high severity with the element selector and failure summary; violations from multiple elements are reported individually
**Edge cases seen in code:** axe-core load failure produces a medium "axe-core load failed" violation; zero axe violations produces no entries in the report
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Viewport overflow flag catches mobile breakage
**Source:** scripts/design_lint.py check_viewport_overflow()
**User:** admin
**Starting state:** --live mode running against a page that overflows horizontally at 1440px desktop viewport
**Goal:** Detect horizontal layout breakage
**Expected outcome:** A medium-severity violation is reported with scrollWidth vs innerWidth values; pages with no overflow produce no viewport violation
**Edge cases seen in code:** scrollWidth exactly equal to innerWidth is not a violation; the check runs per-page and per-viewport (always 1440x900 in --live mode)
**CC confidence:** medium
**Status:** PENDING REVIEW
