## SUGGESTED SCENARIO: Orphan inspection rate DQ check
**Source:** web/data_quality.py _check_orphan_inspections
**User:** admin
**Starting state:** Admin viewing Data Quality dashboard with inspections and permits tables populated
**Goal:** Verify that orphan inspection rate is calculated correctly and displayed with appropriate severity
**Expected outcome:** Orphan rate shown as percentage with green (<5%), yellow (5-15%), or red (>15%) status; only permit-type inspections counted (complaint inspections excluded)
**Edge cases seen in code:** 68K complaint inspections use complaint numbers as reference_number (not permit numbers) — must be filtered out to avoid inflated orphan rate
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Trade permit pipeline health check
**Source:** web/data_quality.py _check_trade_permit_counts
**User:** admin
**Starting state:** Admin viewing Data Quality dashboard with trade permit tables present
**Goal:** Verify that boiler and fire permit pipeline health is monitored
**Expected outcome:** Green status when both tables have data; red status flagging which specific table(s) are empty if pipeline is broken
**Edge cases seen in code:** Both tables could be empty simultaneously; fire_permits has no block/lot columns so can't join to parcel graph
**CC confidence:** high
**Status:** PENDING REVIEW
