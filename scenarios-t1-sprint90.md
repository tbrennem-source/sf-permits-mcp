## SUGGESTED SCENARIO: Landing page showcase converts via gantt CTA
**Source:** web/templates/components/showcase_gantt.html
**User:** expediter
**Starting state:** User is on landing page, scrolls to intelligence showcase section
**Goal:** Understand permit routing timeline, then try the tool with a real permit
**Expected outcome:** User sees the gantt chart animate in, reads station names and reviewer assignments, clicks "Try it yourself →" and arrives at station-predictor tool pre-filled with permit 202509155257
**Edge cases seen in code:** Bars animate from left via scaleX — if IntersectionObserver fires before JS loads, bars remain at scaleX(0). JS initializes on DOMContentLoaded, so this is safe.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Stuck permit diagnosis surfaces actionable intervention steps
**Source:** web/templates/components/showcase_stuck.html
**User:** expediter
**Starting state:** User sees the stuck permit showcase card with 4 simultaneous blocks
**Goal:** Understand what to do when a permit is stuck at multiple stations
**Expected outcome:** User sees severity badge, reviewer names, round counts, and the 3-step playbook. Clicks "Try it yourself →" and arrives at stuck-permit tool with permit 202412237330 pre-filled
**Edge cases seen in code:** Block cards show different border colors for "comments" vs "waiting" status — this semantic distinction should be preserved if status values change
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: What-if comparison reveals scope change consequences before submittal
**Source:** web/templates/components/showcase_whatif.html
**User:** homeowner
**Starting state:** User is considering adding bathroom scope to a kitchen permit
**Goal:** See the cost/timeline difference between the two scenarios side by side
**Expected outcome:** User reads the comparison table, sees OTC vs in-house, 1 agency vs 7, 2-week vs 70-day timelines, and the strategy callout about splitting permits. Clicks CTA to try the tool.
**Edge cases seen in code:** ADA row shows "Yes/No" — for scenario_b, ADA is required. Template uses ada_required boolean correctly.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Cost of delay calculator warns about slow station before user commits to timeline
**Source:** web/templates/components/showcase_delay.html
**User:** expediter
**Starting state:** User is budgeting a restaurant project with $15k/month carrying cost
**Goal:** Understand the financial exposure across permit timeline scenarios
**Expected outcome:** User sees SFFD-HQ warning badge, probability-weighted expected cost of $41,375, and the p75 recommendation. The warning about 86% slower-than-baseline station increases urgency. User clicks CTA to run their own numbers.
**Edge cases seen in code:** Warning badge uses --dot-red + --signal-red; if station velocity data is unavailable, the warning section should gracefully degrade.
**CC confidence:** medium
**Status:** PENDING REVIEW
