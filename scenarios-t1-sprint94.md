## SUGGESTED SCENARIO: Stuck permit showcase shows visual pipeline at a glance
**Source:** web/templates/components/showcase_stuck.html redesign (Sprint 94)
**User:** homeowner
**Starting state:** User is on the landing page, scrolled to the Diagnostic Intelligence showcase card
**Goal:** Quickly understand why a permit is stuck without reading dense text
**Expected outcome:** User sees 4 labeled station blocks in a horizontal row, each with a red X or green check, and immediately grasps which agencies are blocked
**Edge cases seen in code:** All 4 blocks may be critically_stalled, resulting in all red icons — card must still be scannable
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit showcase CTA navigates to full playbook
**Source:** web/templates/components/showcase_stuck.html redesign (Sprint 94)
**User:** expediter
**Starting state:** User sees the "See full playbook →" CTA on the showcase card
**Goal:** Access the full intervention playbook with all 3 steps and contact info
**Expected outcome:** Clicking the CTA navigates to /tools/stuck-permit?permit=202412237330 (or equivalent demo permit), showing the complete playbook
**Edge cases seen in code:** CTA uses ghost-cta class and data-track="showcase-click" for analytics
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit card headline immediately conveys scope
**Source:** web/templates/components/showcase_stuck.html — headline "432 days · 4 agencies blocked"
**User:** homeowner
**Starting state:** User views the landing page for the first time
**Goal:** Instantly understand the severity of a stuck permit without reading body text
**Expected outcome:** Headline displays "{N} days · {N} agencies blocked" in mono font, with a pulsing CRITICAL badge alongside it
**Edge cases seen in code:** If days_stuck or block_count is 0, the headline degrades gracefully (Jinja2 renders 0 values without error)
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit card shows only first intervention step
**Source:** web/templates/components/showcase_stuck.html — playbook[0] only
**User:** expediter
**Starting state:** User views the showcase card and reads the intervention hint
**Goal:** Get a single actionable next step without being overwhelmed by the full playbook
**Expected outcome:** Card shows "Step 1: [action text]" — only one step, not all three. The "See full playbook" CTA leads to the rest.
**Edge cases seen in code:** If playbook is empty, the intervention block is omitted entirely (wrapped in {% if stuck.playbook %})
**CC confidence:** medium
**Status:** PENDING REVIEW
