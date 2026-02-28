## SUGGESTED SCENARIO: Design token lint detects computed color drift on staging
**Source:** scripts/design_lint.py --live mode
**User:** admin
**Starting state:** Staging environment is running; design_lint.py has --live flag available
**Goal:** Verify that a deployed page's rendered CSS colors match the token palette
**Expected outcome:** Running --live against staging reports any computed colors that
  deviate more than ±2 RGB channels from the expected ALLOWED_TOKENS_VARS values,
  producing medium-severity violations with selector and expected/actual color detail
**Edge cases seen in code:** Pages with no matching token selectors produce zero violations (not errors);
  pages that fail to load produce a medium "Page load failed" violation instead of crashing
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: axe-core WCAG AA contrast check catches insufficient contrast
**Source:** scripts/design_lint.py check_axe_contrast()
**User:** admin
**Starting state:** --live mode running against a page with --text-tertiary on interactive copy
**Goal:** Verify that axe-core detects and reports contrast ratio failures on rendered pages
**Expected outcome:** Each axe color-contrast violation is reported as high severity with the
  element selector and failure summary; violations from multiple elements are reported individually
**Edge cases seen in code:** axe-core load failure produces a medium "axe-core load failed" violation;
  zero axe violations produces no entries in the report
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Viewport overflow flag catches mobile breakage
**Source:** scripts/design_lint.py check_viewport_overflow()
**User:** admin
**Starting state:** --live mode running against a page that overflows horizontally at 1440px desktop viewport
**Goal:** Detect horizontal scrollbars that indicate layout breakage
**Expected outcome:** A medium-severity violation is reported with scrollWidth vs innerWidth values;
  pages with no overflow produce no viewport violation
**Edge cases seen in code:** scrollWidth exactly equal to innerWidth is not a violation;
  the check runs per-page and per-viewport (always 1440x900 in --live mode)
**CC confidence:** medium
**Status:** PENDING REVIEW
