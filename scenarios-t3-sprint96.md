## SUGGESTED SCENARIO: permit number click goes to AI analysis page
**Source:** Agent 3D — permit click targets (QS12 T3)
**User:** expediter | homeowner
**Starting state:** User has searched for an address or permit number and sees a results table with permit numbers
**Goal:** Click a permit number to see AI-powered analysis of that permit
**Expected outcome:** Clicking a permit number opens the station predictor (Gantt chart + station detail) page for that permit, not the DBI external portal
**Edge cases seen in code:** Address searches return multiple permits in a table; single permit lookups show detail card — both now link to station predictor
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: DBI portal link available as secondary escape hatch
**Source:** Agent 3D — permit click targets (QS12 T3)
**User:** expediter | architect
**Starting state:** User is viewing search results with permit numbers visible
**Goal:** Access raw DBI permit tracker for a permit (e.g. to check official status, download documents)
**Expected outcome:** A "View on DBI" secondary link is visible next to or below each permit number, opens in a new browser tab, does not replace the current page
**Edge cases seen in code:** Secondary link is styled subdued (--text-tertiary), smaller font — clearly subordinate to primary link
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: external links open in new tab without disrupting session
**Source:** Agent 3D — md_to_html post-processing (QS12 T3)
**User:** expediter | homeowner
**Starting state:** User is mid-session viewing search results that include links to DBI, SF Gov, or other external sites
**Goal:** Click an external link without losing their current search results context
**Expected outcome:** External links (https://) open in a new browser tab, preserving the search results page in the original tab
**CC confidence:** high
**Status:** PENDING REVIEW
