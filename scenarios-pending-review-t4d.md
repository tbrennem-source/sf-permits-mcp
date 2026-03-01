# Scenarios Pending Review — T4-D (QS14)

## SUGGESTED SCENARIO: stuck-permit-diagnosis-in-analyze-results
**Source:** web/intelligence.py — diagnose_stuck_permit tool, analyze results page
**User:** expediter
**Starting state:** User submits a permit description via the analyze flow; permit has been stuck at a station for longer than the typical dwell time
**Goal:** Understand why the permit is stuck and what to do next
**Expected outcome:** Analyze results page shows stuck diagnosis with the affected station, estimated days stalled, and a recommended action; no unhandled errors if intelligence data is unavailable
**Edge cases seen in code:** Intelligence API may return empty or timeout; results page must degrade gracefully without showing a stack trace
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: delay-cost-estimate-surfaces-in-analyze
**Source:** web/intelligence.py — delay cost calculation, analyze results page
**User:** expediter
**Starting state:** User runs an analyze query for a commercial alteration permit; permit has been in review longer than median
**Goal:** See projected carrying cost of ongoing delay so they can decide whether to escalate
**Expected outcome:** Results page shows monthly delay cost estimate (e.g., "$4,200/month based on project value and hold duration"); if no cost data available, section is hidden rather than showing $0 or an error
**Edge cases seen in code:** Cost calculation requires permit_value input; must handle missing value gracefully
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: similar-projects-panel-in-analyze-results
**Source:** src/tools/similar_projects.py — similar_projects tool, analyze results
**User:** architect
**Starting state:** Architect submits a new residential ADU permit description through the analyze flow
**Goal:** Find recently approved permits with similar scope to calibrate expectations on timeline and outcome
**Expected outcome:** Results page shows 3-5 similar approved permits with their timelines, station routing, and final disposition; if no similar permits found, section is hidden with a brief note
**Edge cases seen in code:** Similarity threshold may return 0 results for unusual permit types; should not surface permits from unrelated project types
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: intelligence-section-in-property-report
**Source:** web/routes_property.py — property report intelligence section
**User:** expediter
**Starting state:** Expediter views a property report for an address with 2 active permits in review
**Goal:** Get a quick health summary of those active permits without running a separate analyze query
**Expected outcome:** Property report includes an intelligence section showing each active permit's station, dwell time relative to typical, and a signal (on-track / stalled / stuck); clicking through goes to full permit detail
**Edge cases seen in code:** Intelligence section must be absent (not blank) if no active permits exist; report still loads without error
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: morning-brief-stuck-permits-section
**Source:** web/brief.py — morning brief stuck permit alerts
**User:** expediter
**Starting state:** Expediter has 3 watched permits; 1 has been at Planning for 60+ days (above median)
**Goal:** Start the day with an immediate signal about which permits need attention
**Expected outcome:** Morning brief shows a "Stuck Permits" section listing the stalled permit with station name, days at station, and comparison to median; permits on-track are not listed in this section
**Edge cases seen in code:** If no permits are stuck, section is hidden entirely (not shown as empty); brief still loads if intelligence data is stale
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: morning-brief-delay-cost-alert
**Source:** web/brief.py — delay cost integration in morning brief
**User:** expediter
**Starting state:** Expediter has a watched commercial renovation permit that has been stuck at DBI for 45 days with a project value on record
**Goal:** Understand the financial cost of the delay before deciding whether to schedule a pre-application meeting
**Expected outcome:** Morning brief shows a "Delay Cost" entry for the stuck permit: estimated carrying cost per month and total accumulated cost; figures are clearly labeled as estimates
**Edge cases seen in code:** If project value is not on record, delay cost section is omitted; never shows $0 as a cost
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: branded-404-on-nonexistent-route
**Source:** web/app.py — @app.errorhandler(404) added QS14-T4D
**User:** homeowner
**Starting state:** User follows a stale link or types a mistyped URL
**Goal:** Understand that the page doesn't exist and easily return to the site
**Expected outcome:** A branded error page appears (matching site visual style), clearly stating "Page not found", with a search bar or link back to the homepage; no raw Flask default white error page; no stack trace visible
**Edge cases seen in code:** Handler must also fire for routes that call abort(404) internally, not just unknown paths
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: login-page-beta-explanation
**Source:** web/templates/auth_login.html — invite_required conditional block
**User:** homeowner
**Starting state:** New user lands on the sign-in page after clicking a link that requires authentication; site is in invite-only mode
**Goal:** Understand why they need an invite code and how to get one
**Expected outcome:** Login page displays a short explanation: "SF Permits AI is currently in private beta. If you have an invite code, enter it below." with a contact link; user is not left confused by a blank invite code field with no context
**Edge cases seen in code:** Beta message only appears when invite_required is true; it does not appear for existing users who already have access
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: neighborhood-name-search-hint
**Source:** web/routes_public.py — public search route; neighborhood detection heuristic
**User:** homeowner
**Starting state:** Homeowner types "Mission" or "Castro" into the search bar, expecting neighborhood-level results
**Goal:** Find permits in their neighborhood
**Expected outcome:** Search returns results if any exist; a helper message appears explaining that address-based searches (e.g., "123 Mission St") return more precise results; search behavior is unchanged — only a hint is added
**Edge cases seen in code:** Hint should only appear for 1-3 word queries with no numbers; must not appear for valid address queries that happen to include a neighborhood name
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: admin-dashboard-site-stats
**Source:** web/routes_admin.py — admin home dashboard
**User:** admin
**Starting state:** Admin signs in and navigates to the admin dashboard
**Goal:** Get a quick overview of site health — active users, recent searches, permit data freshness
**Expected outcome:** Admin dashboard loads and shows key stats (total users, recent activity count, last ingest timestamp); no 500 errors; stats display even if some are zero
**Edge cases seen in code:** Dashboard must not expose raw DB errors to the browser; degrade gracefully if a stat query fails
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: landing-showcase-numbers-credible
**Source:** web/routes_public.py — landing page showcase data; web/static/mockups/landing-v6.html
**User:** expediter (first visit)
**Starting state:** Experienced expediter lands on sfpermits.ai for the first time via a referral link
**Goal:** Quickly assess whether the site's data is real and current enough to trust for professional work
**Expected outcome:** Showcase section displays permit counts, processing time medians, and data freshness date pulled from actual DB data; numbers look plausible for SF (e.g., not "99% approval rate"); timestamp shows data was updated within the last 48 hours
**Edge cases seen in code:** If showcase data query fails, section must degrade gracefully (hide or show a "data loading" state) rather than showing 0s or raw errors
**CC confidence:** high
**Status:** PENDING REVIEW
