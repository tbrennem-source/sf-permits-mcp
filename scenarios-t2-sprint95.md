## SUGGESTED SCENARIO: revision risk pre-fill from URL param
**Source:** web/templates/tools/revision_risk.html — ?permit_type= pre-fill
**User:** expediter
**Starting state:** User on entity-network or search results page, follows a link with ?permit_type=restaurant
**Goal:** Land on Revision Risk page with form pre-filled and analysis auto-run
**Expected outcome:** Permit type selector pre-selects "restaurant", loading skeleton shows briefly, risk gauge and markdown results appear without any user interaction
**Edge cases seen in code:** If permitTypeParam is set but select has no matching option, auto-run skips gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: revision risk gauge shows colored arc by risk level
**Source:** web/templates/tools/revision_risk.html — renderGauge() function
**User:** architect
**Starting state:** User submits Revision Risk form for "new_construction" permit type
**Goal:** Understand revision probability at a glance
**Expected outcome:** SVG arc fills proportionally to risk percentage, arc color is red for HIGH, amber for MODERATE, green for LOW; risk level label and explanatory text appear alongside gauge
**Edge cases seen in code:** If API returns no explicit risk level keyword, gauge falls back to percentage extraction heuristic
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: entity network pre-fill from ?address= URL param
**Source:** web/templates/tools/entity_network.html — urlParams.get('address')
**User:** expediter
**Starting state:** User on a property report page, clicks "Explore contractor network" link with ?address=Smith+Construction
**Goal:** Land on Entity Network page with search pre-filled
**Expected outcome:** Input field shows "Smith Construction", loading skeleton appears immediately, network connections render when response returns
**Edge cases seen in code:** Also accepts ?q= as alternate param name
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: entity network shows connection stats before markdown
**Source:** web/templates/tools/entity_network.html — renderNetworkGraph()
**User:** expediter
**Starting state:** User searches for a contractor with >5 connected entities
**Goal:** Quickly assess network size before reading detailed markdown
**Expected outcome:** Three stat cards appear above connections (Connected entities count, Relationships count, Hops), followed by a center node display, then connection rows sorted by shared permits
**Edge cases seen in code:** If parsed.connections is empty, shows "No connections found" message instead of connection rows
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: revision risk tool graceful degradation on missing API endpoint
**Source:** web/templates/tools/revision_risk.html — fetch('/api/revision-risk') 404 handler
**User:** homeowner
**Starting state:** User fills revision risk form, but /api/revision-risk endpoint doesn't exist yet
**Goal:** See useful guidance even when backend isn't ready
**Expected outcome:** Error message explains the endpoint isn't available yet and suggests the What-If Simulator as an alternative; no unhandled JS exceptions
**Edge cases seen in code:** 404 response triggers informative redirect suggestion, not generic error
**CC confidence:** medium
**Status:** PENDING REVIEW
