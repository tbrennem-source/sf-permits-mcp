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

## SUGGESTED SCENARIO: revision risk triggers list with mitigation
**Source:** web/templates/tools/revision_risk.html — triggers and mitigation sections
**User:** architect
**Starting state:** User has submitted a permit type and neighborhood for a commercial tenant improvement.
**Goal:** Identify the top correction triggers so they can be addressed in drawings before submittal.
**Expected outcome:** Results show a numbered list of up to 5 triggers (name + description) and a checkmarked mitigation list, along with the timeline impact in average days.
**CC confidence:** high
**Status:** PENDING REVIEW
