## SUGGESTED SCENARIO: Landing page displays key capability questions to new visitor
**Source:** tests/test_landing.py — test_landing_has_feature_cards
**User:** homeowner
**Starting state:** User is unauthenticated, visits the root URL
**Goal:** Understand what the product does before signing up
**Expected outcome:** The landing page presents the three core capability questions ("Do I need a permit?", "How long will it take?", "Is my permit stuck?") as navigable sections
**Edge cases seen in code:** Sub-row anchor links (#cap-permits, #cap-timeline, #cap-stuck) must resolve to the correct section IDs on the page
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Landing page shows data credibility stats to build trust
**Source:** tests/test_landing.py — test_landing_has_stats
**User:** homeowner
**Starting state:** User is unauthenticated, visits the root URL
**Goal:** Verify that the site is backed by real data before trusting it
**Expected outcome:** The landing page shows quantified stats including SF building permit count and city data source count, giving credibility to the AI guidance
**Edge cases seen in code:** The permit count is rendered via a JS counting animation (data-target attribute) — the static label "SF building permits" must be present even before JS runs
**CC confidence:** high
**Status:** PENDING REVIEW
