# QA Script: Session 38f — Admin Ops Tab Reliability + Severity Hold Fix

**Test site**: https://sfpermits-ai-production.up.railway.app
**Requires**: Admin login
**Estimated time**: 8 minutes

---

## 1. Admin Ops — All 6 Tabs Load (P0 fix)

1. Go to `/admin/ops`
2. Data Quality tab loads by default with colored status cards
   - [ ] PASS: Cards visible, red cards sort before yellow before green
   - [ ] FAIL: Infinite spinner or blank content

3. Click **Pipeline Health** tab
   - [ ] PASS: Data loads OR shows "Pipeline Health is loading slowly" fallback within 30s
   - [ ] FAIL: Infinite spinner beyond 30s

4. Click **User Activity** tab
   - [ ] PASS: Activity log loads within 30s
   - [ ] FAIL: Infinite spinner beyond 30s

5. Click **Feedback** tab
   - [ ] PASS: Feedback queue loads within 30s
   - [ ] FAIL: Infinite spinner beyond 30s

6. Click **LUCK Sources** tab
   - [ ] PASS: Knowledge source inventory loads within 30s
   - [ ] FAIL: Infinite spinner beyond 30s

7. Click **Regulatory Watch** tab
   - [ ] PASS: 3 seeded items visible with severity badges
   - [ ] FAIL: Spinner or empty

## 2. Timeout & Error Recovery

8. Click between 3-4 tabs rapidly within 2 seconds
   - [ ] PASS: No tab gets permanently stuck. Failed tabs show error message with "Reload page" link
   - [ ] FAIL: Any tab shows infinite spinner after 30s

9. If any tab times out, verify the error message says one of:
   - "Request timed out (30s)."
   - "Request failed — server may be busy."
   - "Tab returned an error."
   - [ ] PASS: Clear error message shown
   - [ ] FAIL: Spinner or generic/no message

## 3. Hash Routing (P1 fix)

10. Navigate to `/admin/ops#luck`
    - [ ] PASS: LUCK Sources tab selected and loads
    - [ ] FAIL: Wrong tab selected

11. Navigate to `/admin/ops#pipeline`
    - [ ] PASS: Pipeline Health tab selected and loads
    - [ ] FAIL: Wrong tab selected

12. Navigate to `/admin/ops#dq`
    - [ ] PASS: Data Quality tab selected and loads
    - [ ] FAIL: Wrong tab selected

13. Navigate to `/admin/ops#watch`
    - [ ] PASS: Regulatory Watch tab selected and loads
    - [ ] FAIL: Wrong tab selected

14. Navigate to `/admin/ops` (no hash)
    - [ ] PASS: Data Quality is default
    - [ ] FAIL: Different tab is default

## 4. Severity — Hold Bug Fix (P2)

15. Go to `/brief`, select **Last 90 days**
16. Find **532 Sutter** property card
    - [ ] PASS: Shows AT RISK (red) with reason mentioning "Hold at PPC"
    - [ ] FAIL: Shows ON TRACK (green) or BEHIND (yellow)

17. Find **505 Mission Rock** property card
    - [ ] PASS: Shows AT RISK with hold-related reason
    - [ ] FAIL: Shows ON TRACK or wrong reason

18. Scan all property cards: no property with "Hold at..." or "Open enforcement" in its reason should be ON TRACK
    - [ ] PASS: All held/enforcement properties show AT RISK
    - [ ] FAIL: Any held property shows ON TRACK

## 5. What Changed — Transition Dates (P2)

19. Still on `/brief`, look at "What Changed" entries with status transitions (e.g. FILED → ISSUED)
    - [ ] PASS: Each transition shows a date alongside the status badges
    - [ ] FAIL: No date visible on transition entries

## Results Summary

| Test | Result |
|------|--------|
| 1. DQ default tab | |
| 2. Pipeline Health | |
| 3. User Activity | |
| 4. Feedback | |
| 5. LUCK Sources | |
| 6. Regulatory Watch | |
| 7. Rapid switching | |
| 8. Timeout messages | |
| 9. #luck hash | |
| 10. #pipeline hash | |
| 11. #dq hash | |
| 12. #watch hash | |
| 13. No-hash default | |
| 14. 532 Sutter severity | |
| 15. 505 Mission Rock | |
| 16. No held=ON TRACK | |
| 17. Transition dates | |
