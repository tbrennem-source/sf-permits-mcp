# Sprint 91 T2 — Suggested Scenarios

## SUGGESTED SCENARIO: consultant search renders on first page load
**Source:** web/templates/consultants.html migration
**User:** homeowner | expediter | architect
**Starting state:** User navigates to /consultants without any prefill query parameters
**Goal:** User wants to find a consultant for their SF permit project
**Expected outcome:** Page loads successfully with a search form (street name, block, lot, neighborhood, permit type fields), two checkboxes, and a "Find Consultants" button. No results shown on initial load.
**Edge cases seen in code:** prefill context banner only shown when prefill.signal is truthy — should be absent on direct navigation
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: consultant search prefill from property report
**Source:** web/templates/consultants.html — prefill context banner
**User:** homeowner | expediter
**Starting state:** User navigates to /consultants with block/lot/address query parameters (from property report link)
**Goal:** User wants to find consultants familiar with their specific property
**Expected outcome:** Page loads with form pre-filled with block, lot, address values. Context banner appears showing "Searching for consultants matching your property at Block X, Lot Y". Form auto-submits within 300ms and shows ranked results.
**Edge cases seen in code:** neighborhood pre-fill only shown in banner if prefill.neighborhood is set
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: consultant results sorted by user preference
**Source:** web/templates/consultants.html — sort-chip controls
**User:** expediter | architect
**Starting state:** User has performed a consultant search and results are showing
**Goal:** User wants to find the consultant with the most recent permit activity
**Expected outcome:** Sort chips (Best Match, Most Permits, Most Recent, Largest Network) appear above results. Clicking "Most Recent" re-submits the form with sort_by=recency and re-renders results ordered by recency. Active chip visually differs from inactive ones.
**Edge cases seen in code:** sort_by hidden input defaults to 'score' if undefined
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: login page accessible without account
**Source:** web/templates/auth_login.html
**User:** homeowner (new)
**Starting state:** User has no account and navigates to the login page
**Goal:** User wants to sign in or create an account via magic link
**Expected outcome:** Login form shows email input, optional invite code field (when invite_required), and "Send magic link" button. Page explains no password needed. Footer links to About and Methodology.
**Edge cases seen in code:** invite_code field hidden unless invite_required flag is true
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: beta request form submission with honeypot
**Source:** web/templates/beta_request.html — honeypot field
**User:** homeowner (prospective)
**Starting state:** User navigates to the beta request page
**Goal:** User wants to request access to sfpermits.ai
**Expected outcome:** Form shows email, name, and reason fields. Hidden honeypot field (website) is invisible to real users. On submission with the website field filled, bot protection triggers silently. On legitimate submission, confirmation shown.
**Edge cases seen in code:** Already-signed-in users see prefill_email populated; submitted state hides the form
**CC confidence:** medium
**Status:** PENDING REVIEW
