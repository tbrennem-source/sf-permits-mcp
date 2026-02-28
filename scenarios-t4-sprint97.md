
## SUGGESTED SCENARIO: stakeholder follows guided demo link
**Source:** web/templates/demo_guided.html
**User:** expediter | homeowner | architect
**Starting state:** User has not visited sfpermits.ai before; received a share link to /demo/guided
**Goal:** Understand what the product does within 2 minutes and self-navigate to a relevant tool
**Expected outcome:** User lands on the guided page, reads all 6 sections in sequence, and clicks into at least one intelligence tool; no authentication required
**Edge cases seen in code:** All 4 tool card links include demo query params — tool pages must handle ?demo= gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: stakeholder searches pre-filled address
**Source:** web/templates/demo_guided.html — Section 3 search block
**User:** homeowner
**Starting state:** User is on /demo/guided and clicks the "Search 487 Noe St →" pre-filled link
**Goal:** See real permit data for a sample SF property without having to type an address
**Expected outcome:** /search?q=487+Noe+St returns results for 487 Noe St with permit data; address and permit timeline visible
**Edge cases seen in code:** If DuckDB lacks data for that address, search should return empty state gracefully not a 500
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: professional shares demo link with client before kickoff meeting
**Source:** web/templates/demo_guided.html — Section 5 "For Professionals"
**User:** expediter
**Starting state:** Expediter wants to orient a new property owner client before a project kickoff
**Goal:** Send a single link that explains the permit intelligence workflow and pre-warms the client on terminology
**Expected outcome:** Client opens /demo/guided unauthenticated, reads Amy workflow bullets, understands morning triage concept, and arrives at kickoff with baseline context
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: AI practitioner evaluates MCP integration via demo page
**Source:** web/templates/demo_guided.html — Section 6 "Connect Your AI"
**User:** architect
**Starting state:** Technical user is evaluating whether to integrate sfpermits.ai into their Claude or ChatGPT workflow
**Goal:** Understand the MCP capability scope (34 tools, 18M records) and navigate to learn more
**Expected outcome:** User reads Section 6, clicks "Learn more →", lands on /methodology with sufficient technical detail to decide on integration
**CC confidence:** medium
**Status:** PENDING REVIEW
