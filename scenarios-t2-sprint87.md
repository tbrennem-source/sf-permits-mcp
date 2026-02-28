## SUGGESTED SCENARIO: Admin switches to Beta Active persona to preview watch state
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** admin
**Starting state:** Admin is logged in with the feedback widget open; no persona is active
**Goal:** Switch to "Beta Active (3 watches)" persona to preview the UI as a beta user with 3 active watches
**Expected outcome:** The persona dropdown shows "Beta Active (3 watches)" as selected; applying it injects the persona into the session and shows a success status; navigating to any watch-aware page reflects the beta-user watch state (3 watches visible)
**Edge cases seen in code:** Applying a persona does not modify the real user_id — the admin's account is preserved
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin resets impersonation and returns to their own session
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** admin
**Starting state:** Admin has an active persona ("Beta Active") injected into the session
**Goal:** Clear the impersonation and return to their real admin session state
**Expected outcome:** After clicking the Reset link (or navigating to reset URL), all persona session keys are cleared; the UI no longer shows any active persona; the admin sees their real account state
**Edge cases seen in code:** Reset does not clear the user_id — only the impersonation overlay keys are removed
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Non-admin user cannot access the impersonation endpoint
**Source:** QS10 T2 Agent 2A — admin persona impersonation
**User:** expediter (non-admin authenticated user)
**Starting state:** A regular (non-admin) user is logged in
**Goal:** Attempt to POST to the persona impersonation endpoint directly
**Expected outcome:** The server returns 403 Forbidden; no session changes are made; the user remains in their original state
**CC confidence:** high
**Status:** PENDING REVIEW

---

# T2 Sprint 87 — Suggested Scenarios

## SUGGESTED SCENARIO: admin sees pending visual QA badge count in widget
**Source:** feedback_widget.html qa-review-panel, qa-results/pending-reviews.json
**User:** admin
**Starting state:** Tim is logged in as admin. vision_score.py has written 3 entries to pending-reviews.json for pages scoring below 3.0.
**Goal:** Tim opens the feedback widget and immediately sees how many visual QA items need his review.
**Expected outcome:** The "QA Reviews" panel is visible at the top of the feedback modal with a badge showing "3 pending". Non-admin users do not see this panel.
**Edge cases seen in code:** Badge defaults to 0 when qa_pending_count is not injected by the rendering route.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: admin accepts a borderline visual QA item with an explanatory note
**Source:** web/routes_admin.py admin_qa_decision, qa-results/review-decisions.json
**User:** admin
**Starting state:** A page scored 2.8/5 — above the auto-reject threshold but flagged for human review. The pending entry is loaded into the widget via window.qaLoadItem().
**Goal:** Tim reviews the screenshot context, decides the layout is acceptable for data-dense pages, and accepts it with a note for training purposes.
**Expected outcome:** The Accept button returns a green "Accepted" confirmation. The decision is written to review-decisions.json with tim_verdict="accept", the note field populated, and a timestamp. The entry is removed from pending-reviews.json.
**Edge cases seen in code:** Note is capped at 500 characters; pipeline_score coerced to float.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: admin rejects a layout regression; item tracked for follow-up
**Source:** web/routes_admin.py admin_qa_decision, qa-results/pending-reviews.json
**User:** admin
**Starting state:** A page scored 1.6/5 — clearly broken centering. Entry loaded into widget via window.qaLoadItem().
**Goal:** Tim rejects the item so it remains tracked for a fix in the next sprint.
**Expected outcome:** The Reject button returns a red "Rejected — flagged for fix" message. The decision appears in review-decisions.json with tim_verdict="reject". The entry is removed from pending-reviews.json (verdict recorded; fix tracking handled separately by the sprint workflow).
**Edge cases seen in code:** Missing pending-reviews.json is handled gracefully — endpoint does not crash.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Accept/Reject/Note decisions persist as training data across sessions
**Source:** qa-results/review-decisions.json (append-only array)
**User:** admin
**Starting state:** Tim has made 10+ decisions across multiple QA sessions. review-decisions.json contains entries from previous sprints.
**Goal:** The QS10 orchestrator reads review-decisions.json to build a training dataset for vision_score.py calibration.
**Expected outcome:** review-decisions.json is a valid JSON array containing all decisions in append order with page, persona, viewport, dimension, pipeline_score, tim_verdict, sprint, note, and timestamp fields. No entries are overwritten — only appended.
**Edge cases seen in code:** Atomic write (tmp + rename) prevents partial writes on crash.
**CC confidence:** medium
**Status:** PENDING REVIEW
