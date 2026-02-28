## SUGGESTED SCENARIO: Prod gate promotes when new issues differ from previous sprint
**Source:** scripts/prod_gate.py — hotfix ratchet logic
**User:** admin
**Starting state:** Previous sprint got score 3 with "Test Suite" failing. HOTFIX_REQUIRED.md exists recording "Test Suite". This sprint's builds fix the test suite but introduce a lint trend issue.
**Goal:** Understand whether the prod gate will block or allow promotion.
**Expected outcome:** Gate returns PROMOTE with mandatory hotfix, not HOLD. The ratchet does not trigger because the failing check changed from "Test Suite" to "Lint Trend". The hotfix file is overwritten to record the new failing check.
**Edge cases seen in code:** Partial overlap (some same, some new) still triggers ratchet. Legacy HOTFIX_REQUIRED.md files without the "## Failing checks" structured section do not trigger the ratchet.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Prod gate holds when same issue persists across sprints
**Source:** scripts/prod_gate.py — hotfix ratchet logic
**User:** admin
**Starting state:** Previous sprint got score 3 with "Migration Safety" failing. HOTFIX_REQUIRED.md exists recording "Migration Safety". This sprint still has migration safety issues and scores 3 again.
**Goal:** Understand whether the prod gate will escalate to HOLD.
**Expected outcome:** Gate returns HOLD with reason citing the overlapping check ("Migration Safety"). The ratchet message is clear that it is a repeat failure of the same specific check, not merely a consecutive score-3 sprint.
**Edge cases seen in code:** Score 4+ in any sprint between the two score-3 runs deletes HOTFIX_REQUIRED.md, so the ratchet resets — the second score-3 after a clean sprint is treated as first occurrence.
**CC confidence:** high
**Status:** PENDING REVIEW
