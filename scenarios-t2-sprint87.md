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
