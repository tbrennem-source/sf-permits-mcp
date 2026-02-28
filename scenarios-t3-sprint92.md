## SUGGESTED SCENARIO: Contractor shares permit analysis via native mobile share sheet
**Source:** web/templates/components/share_button.html, web/static/js/share.js
**User:** expediter
**Starting state:** User has run a station predictor or stuck permit analysis and can see results.
**Goal:** Forward the analysis link to their contractor without copying and pasting manually.
**Expected outcome:** On mobile, the native share sheet opens with the page URL pre-filled. The user can send via Messages, WhatsApp, or any installed app. On desktop, the URL is copied to clipboard and a "Copied!" confirmation appears briefly.
**Edge cases seen in code:** AbortError from navigator.share (user dismissed share sheet) is silently caught and does not show an error. execCommand fallback runs when clipboard API is unavailable.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Desktop user copies tool result URL to share with team
**Source:** web/static/js/share.js — clipboard path
**User:** architect
**Starting state:** User has run a what-if simulation or cost-of-delay calculation and wants to share with a project owner.
**Goal:** Copy the tool result page URL to paste into email or Slack.
**Expected outcome:** Clicking "Send this to your contractor" copies the current URL. A "Copied!" confirmation appears for 2 seconds, then disappears. The button label briefly updates to "Copied!" before reverting.
**Edge cases seen in code:** If navigator.clipboard is unavailable, textarea execCommand fallback runs silently. Both paths end with the same visual confirmation.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: User navigates to entity network tool and sees empty state
**Source:** web/templates/tools/entity_network.html
**User:** expediter
**Starting state:** User is logged in and navigates to /tools/entity-network.
**Goal:** Understand what the tool does before entering a query.
**Expected outcome:** Page loads with a clear heading, subtitle, and input field. Results area shows a helpful hint about what to enter. Share button is visible below the results area.
**Edge cases seen in code:** Route redirects to /auth/login if user is not authenticated.
**CC confidence:** medium
**Status:** PENDING REVIEW
