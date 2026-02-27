## SUGGESTED SCENARIO: Anonymous landing page renders with search and hero
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestAnonymousLanding
**User:** homeowner
**Starting state:** User is not logged in; navigates to the root URL
**Goal:** Understand what sfpermits.ai offers before signing up
**Expected outcome:** Page renders with an h1 heading, a search input, and at least one reference to "permit" in the body content. A CTA to sign up or log in is present.
**Edge cases seen in code:** Landing vs Index templates — anonymous users see landing.html, authenticated see index.html. Both must render the search bar.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Protected routes enforce login redirect for anonymous visitors
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestAuthRedirects
**User:** homeowner
**Starting state:** User is not logged in; attempts to navigate directly to /brief, /portfolio, or /account
**Goal:** Access a protected feature without being authenticated
**Expected outcome:** User is redirected to the login page. The login page renders with an email input. No protected content is exposed.
**Edge cases seen in code:** /auth/login itself must be publicly accessible (status 200). The redirect chain should always land on login, not a 500 or blank page.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile viewport has no horizontal overflow on key pages
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestMobileNoHorizontalScroll
**User:** homeowner
**Starting state:** User opens the app on a 375px-wide mobile device (iPhone SE / standard mobile)
**Goal:** Browse the landing page, demo, login, and beta-request page without side-scrolling
**Expected outcome:** document.body.scrollWidth <= window.innerWidth on all checked pages. No content is clipped or requires horizontal scrolling.
**Edge cases seen in code:** /demo and /beta-request pages are content-heavy and most likely to overflow if images or wide tables are not constrained.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Mobile navigation is accessible at 375px
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestMobileNavigation
**User:** homeowner
**Starting state:** User is on a 375px-wide viewport, either anonymous (landing) or authenticated (dashboard)
**Goal:** Access the site navigation without a wide screen
**Expected outcome:** A hamburger menu toggle, <nav> element, or navigation links in the header are present and accessible. Authenticated users see the nav after login.
**Edge cases seen in code:** Desktop nav may collapse entirely at mobile widths; hamburger button must remain tappable and visible.
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta request form renders and accepts input without JS errors
**Source:** tests/e2e/test_auth_mobile_scenarios.py — TestBetaRequestForm
**User:** homeowner
**Starting state:** User has not yet been invited; navigates to /beta-request
**Goal:** Request beta access by filling out the form
**Expected outcome:** Page returns HTTP 200. Form has email input, name input (or text input), a reason/message field, and a submit button. Filling all visible fields produces no JavaScript errors. Honeypot and rate limiting are backend-only and do not appear in the UI.
**Edge cases seen in code:** Honeypot field must not be visible to real users. Rate limit (3 requests/IP/hour) fires only on repeated POST submissions, not on page load.
**CC confidence:** high
**Status:** PENDING REVIEW
