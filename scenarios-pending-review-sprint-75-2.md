## SUGGESTED SCENARIO: beta approval sends welcome email with magic link

**Source:** web/auth.py — send_beta_welcome_email(), web/routes_admin.py — admin_approve_beta()
**User:** admin
**Starting state:** Admin is logged in; a beta request exists in "pending" status; SMTP is configured
**Goal:** Approve a beta request and notify the new user
**Expected outcome:** New user receives a branded HTML email with a one-click sign-in button; email contains a valid magic link URL; admin sees "Approved and sent welcome email" confirmation; if SMTP fails, fallback plain magic link email is sent instead
**Edge cases seen in code:** SMTP failure triggers fallback to send_magic_link(); dev mode (no SMTP_HOST) logs to console and returns True; already-approved requests return "not found" redirect
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: new beta user completes 3-step onboarding

**Source:** web/routes_misc.py — /welcome route, web/templates/welcome.html
**User:** homeowner
**Starting state:** User has just received beta approval email and clicked the magic sign-in link; onboarding_complete is FALSE in DB
**Goal:** Get oriented to the app (search, report, watchlist) and start using it
**Expected outcome:** /welcome shows 3-step page with search, property report, and watchlist cards; user can navigate to any step via CTA buttons; clicking "Start searching now" or the skip link fires POST /onboarding/dismiss which sets onboarding_complete = TRUE in DB; subsequent visits to /welcome redirect to dashboard instead of showing onboarding again
**Edge cases seen in code:** Unauthenticated access redirects to login; if onboarding_complete already TRUE, immediate redirect to /; dismiss is fire-and-forget (non-blocking JS fetch); banner dismiss (HTMX) and page dismiss both use same endpoint
**CC confidence:** high
**Status:** PENDING REVIEW
