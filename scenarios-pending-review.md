# Scenarios Pending Review

## SUGGESTED SCENARIO: Pasted email routes to AI draft response
**Source:** Intent router Priority 0 (src/tools/intent_router.py)
**User:** expediter
**Starting state:** Expediter is on homepage, has received an email from a homeowner asking about permits
**Goal:** Paste the email into the search box and get an AI-drafted reply
**Expected outcome:** AI generates a contextual response addressing the homeowner's question, using RAG knowledge base. Does NOT trigger complaint search, address lookup, or project analysis even if email contains those keywords.
**Edge cases seen in code:** Single-line greeting without substance ("Hi Amy") should NOT trigger draft — falls through to general_question. "draft:" prefix always triggers regardless of length.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Expired permit does not alarm active site
**Source:** Portfolio health logic (web/portfolio.py, web/brief.py)
**User:** expediter
**Starting state:** Expediter watches a property with 1 expired mechanical permit and 1 active permit, last activity 3 days ago
**Goal:** See accurate health status on portfolio and morning brief
**Expected outcome:** Property shows ON_TRACK (green), not BEHIND or AT_RISK. No health_reason text about the expired permit. Expediter is not distracted by administrative noise.
**Edge cases seen in code:** Property with expired permit AND no activity for 90+ days AND no other active permits → SLOWER (gentle nudge). Property with open violations → still AT_RISK regardless of expired permits.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: What Changed shows specific permit details
**Source:** Morning brief "What Changed" section (web/brief.py)
**User:** expediter
**Starting state:** Watched property had a permit status_date update in SODA but nightly change detection didn't log a specific transition
**Goal:** See what actually changed at the property on the morning brief
**Expected outcome:** Card shows permit number, permit type, and current status badge instead of generic "Activity Xd ago" with "1 active of 2 permits"
**Edge cases seen in code:** If permits table query fails or returns no results, falls back to generic activity card. Multiple permits at same address that changed → one card per permit.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Multi-line email with signature detected
**Source:** Intent router signature detection (src/tools/intent_router.py)
**User:** expediter
**Starting state:** Expediter receives a forwarded email with sign-off ("— Karen", "Best regards,", "Sent from my iPhone")
**Goal:** Paste the full email thread into search box for AI analysis
**Expected outcome:** Routes to draft_response even without explicit "Hi" greeting, based on signature detection + multi-line structure
**Edge cases seen in code:** Single dash "- Karen" matches but "-Karen" (no space) does not. "Sent from my iPhone" only matches at line start.
**CC confidence:** medium
**Status:** PENDING REVIEW
