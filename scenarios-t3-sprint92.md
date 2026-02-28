## SUGGESTED SCENARIO: what-if simulator two-panel comparison
**Source:** web/templates/tools/what_if.html (Sprint 92 — Agent 3B polish)
**User:** expediter | homeowner
**Starting state:** User is on the What-If Simulator page, unauthenticated or authenticated
**Goal:** Compare two project scopes (e.g., kitchen remodel vs. full gut + ADU) to understand timeline and fee differences before filing
**Expected outcome:** User fills Project A and Project B panels and sees a comparison table with green/red indicators on significant differences; a strategy callout summarizes key deltas
**Edge cases seen in code:** If Project B is empty, only base scenario is evaluated; if demo param is present, form auto-fills and auto-runs after 400ms

## SUGGESTED SCENARIO: entity network auto-fill from address link
**Source:** web/templates/tools/entity_network.html — ?address= param
**User:** expediter
**Starting state:** User is viewing a property report and clicks "View entity network" with address pre-filled.
**Goal:** See the professional network for a specific property without retyping the address.
**Expected outcome:** The entity network page loads with the address already filled in the search box, and the graph loads automatically.
**Edge cases seen in code:** If ?address= is empty, no auto-run fires. If the API returns no nodes, empty state is shown.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: what-if simulator demo auto-run
**Source:** web/templates/tools/what_if.html ?demo=kitchen-vs-full
**User:** homeowner
**Starting state:** User arrives at /tools/what-if?demo=kitchen-vs-full
**Goal:** See a pre-populated comparison without having to fill in the form manually
**Expected outcome:** Both Project A and B panels are pre-filled with demo data and the simulation runs automatically; user sees comparison table within a few seconds
**Edge cases seen in code:** 400ms timeout before auto-submit so user can see the pre-filled state

## SUGGESTED SCENARIO: entity network node click reveals entity detail
**Source:** web/templates/tools/entity_network.html — entity detail sidebar
**User:** expediter
**Starting state:** Entity network graph is rendered with multiple nodes.
**Goal:** Learn the license number, permit count, and average issuance time for a specific contractor.
**Expected outcome:** Clicking any non-central node populates the sidebar with the entity's name, role chip, permit count, license, and average issuance days.
**Edge cases seen in code:** If license or avg_days are null, sidebar shows "—" for those fields.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: revision risk low-probability result
**Source:** web/templates/tools/revision_risk.html — risk gauge render
**User:** homeowner
**Starting state:** User selects a straightforward permit type (e.g., roof replacement).
**Goal:** Understand whether plans are likely to be returned for corrections.
**Expected outcome:** Risk gauge shows a percentage below 15%, bar renders green, verdict says "Plans are likely to pass review without corrections."
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay percentile breakdown
**Source:** web/templates/tools/cost_of_delay.html (Sprint 92 — Agent 3B polish)
**User:** expediter | homeowner | architect
**Starting state:** User selects a permit type and enters monthly carrying cost
**Goal:** Understand the financial exposure across best/likely/worst-case permit timelines
**Expected outcome:** Percentile table shows p25/p50/p75/p90 scenarios with days, carrying cost, revision risk cost, and total; expected cost highlight card shows p50+revision probability-weighted total
**Edge cases seen in code:** Permit type dropdown limited to 12 known types; restaurant gets a DPH-HQ bottleneck alert
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay bottleneck alert
**Source:** web/templates/tools/cost_of_delay.html bottleneck-alert component
**User:** expediter | homeowner
**Starting state:** User selects a permit type with known slow stations (restaurant, commercial_ti, new_construction)
**Goal:** See a warning about known bottlenecks that will inflate the timeline
**Expected outcome:** An amber-dot bottleneck alert badge appears with a description of the specific slow station (e.g., "DPH-HQ averages +86% longer than DBI baseline" for restaurant)
**Edge cases seen in code:** Bottleneck message is permit-type-specific from a JS lookup table; generic message if unknown type

## SUGGESTED SCENARIO: revision risk demo auto-fill for restaurant-mission
**Source:** web/templates/tools/revision_risk.html — ?demo=restaurant-mission param
**User:** expediter
**Starting state:** User arrives at /tools/revision-risk?demo=restaurant-mission (from a demo link or walkthrough).
**Goal:** See a pre-filled, high-risk example without manually filling in the form.
**Expected outcome:** Permit type is set to "restaurant", neighborhood to "Mission", project description filled, and the assessment runs automatically showing triggers and mitigation steps.
**Edge cases seen in code:** If the API is unavailable, an error notice renders with a retry prompt.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: cost of delay demo auto-run
**Source:** web/templates/tools/cost_of_delay.html ?demo=restaurant-15k
**User:** homeowner
**Starting state:** User arrives at /tools/cost-of-delay?demo=restaurant-15k
**Goal:** See an example calculation without filling in the form
**Expected outcome:** Form pre-fills with restaurant permit type and $15K/month; calculation runs automatically and shows the percentile breakdown, expected cost card, and bottleneck warning for restaurant
**Edge cases seen in code:** 400ms delay before auto-submit; invalid monthly cost triggers inline error

## SUGGESTED SCENARIO: revision risk triggers list with mitigation
**Source:** web/templates/tools/revision_risk.html — triggers and mitigation sections
**User:** architect
**Starting state:** User has submitted a permit type and neighborhood for a commercial tenant improvement.
**Goal:** Identify the top correction triggers so they can be addressed in drawings before submittal.
**Expected outcome:** Results show a numbered list of up to 5 triggers (name + description) and a checkmarked mitigation list, along with the timeline impact in average days.
**CC confidence:** high
**Status:** PENDING REVIEW

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
