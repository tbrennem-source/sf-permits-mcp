## SUGGESTED SCENARIO: Question query routes to AI consultation not permit search
**Source:** Agent 3C — search routing + intent_router.py
**User:** homeowner
**Starting state:** User is on the public landing page, unauthenticated
**Goal:** Ask "Do I need a permit for a kitchen remodel?" in the search box
**Expected outcome:** Instead of "No permits found", user sees guidance that this is an AI-answerable question, with a prompt to sign up for AI consultation, not a failed literal permit lookup
**Edge cases seen in code:** Queries with construction context (kitchen, bathroom, ADU, garage, deck) + question prefix are classified as `question` intent; validate_plans and address patterns still take priority
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Validate query beats question intent
**Source:** Agent 3C — intent_router.py priority ordering
**User:** architect | expediter
**Starting state:** User types "how do I validate plans?" in search
**Goal:** Access the plan validation feature
**Expected outcome:** Query routes to validate_plans intent, not question/AI consultation — the validate keyword wins over question prefix detection
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user property click goes to full search not loop
**Source:** Agent 3C — landing.html state machine
**User:** homeowner (beta tester, authenticated)
**Starting state:** User is on the landing page in beta state with a watched property shown
**Goal:** Click a watched property link (e.g., "487 Noe — PPC stalled 12d")
**Expected outcome:** User goes directly to the full search results page for that property, not back to the landing page via /search redirect loop
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta badge shows correct label for beta users
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (beta tester)
**Starting state:** User is on landing page in beta state (via admin toggle)
**Goal:** See their account context clearly labeled
**Expected outcome:** Badge next to wordmark reads "Beta Tester" (not "beta"), giving a polished look for beta program participants
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Scroll-cue arrow is clearly visible after page load
**Source:** Agent 3C — landing.html UX fixes
**User:** homeowner (new visitor)
**Starting state:** User arrives on landing page, hero section is visible
**Goal:** Notice the call-to-action scroll arrow to see the showcase
**Expected outcome:** After 3.6s, the scroll cue arrow fades in and is visible at 60% opacity — noticeable without dominating the hero section
**CC confidence:** low
**Status:** PENDING REVIEW
