# QA Results: Session 45 — Permit Lookup Search Accuracy
**Date**: 2026-02-22 (initial), 2026-02-23 (retest)
**Tester**: Claude Code (browser automation)
**Target**: https://sfpermits-ai-production.up.railway.app

---

## Step 1: Exact Match — No Substring Bleed
**Result**: PASS
- Searched "146 Lake" — results showed only LAKE ST permits
- Confirmed via JS: `hasBlake: false` — no BLAKE on page
- "Found 11 permits at 146 Lake" — all correct addresses

## Step 2: Parcel Merge — Comprehensive Results + Badge Match
**Result**: PASS
- 11 permits displayed in the table (up from 5 before the fix)
- PERMITS badge shows "11 total" — matches table count exactly
- Permits span from 1992 to 2026, covering both lot 069 and historical lots

## Step 3: Property Report Loads
**Result**: PASS
- "View Property Report" link resolves to `/report/1355/017`
- Property report loads with: Risk Assessment, Complaints & Violations, Permit History
- Note: Report shows "144 Lake St" (lot 017, old unit) — pre-existing behavior, not a regression

## Step 4: "Did You Mean?" Suggestions
**Result**: PASS
- Searched "100 Lak" (no exact match)
- Displayed: "No exact match for **100 Lak**. Did you mean:"
  - **Lake** (11 permits)
  - **Lake Merced Hill So** (3 permits)
  - **Lake Merced Hill St South** (2 permits)
  - **Lakeview** (1 permits)

## Step 5: Permit Lookup by Number
**Result**: PASS
- Searched permit 202601133701
- Full details: type, status, description, dates, cost, address, neighborhood, parcel
- Project Team: Contractor + Agent listed
- Inspection History: 2 inspections with dates and results
- Plan Review Routing: 4 steps across 4 stations

## Step 6: Feedback Screenshot — Large Page Capture
**Result**: PASS (retest 2026-02-23)
- html2canvas loaded from CDN successfully
- Screenshot captured: 460KB JPEG (well under 5MB limit)
- Preview thumbnail displayed in feedback modal
- Status text: "Page captured!"

## Step 7: Feedback Submit with Screenshot
**Result**: PASS (retest 2026-02-23)
- Submitted feedback with screenshot attached
- Feedback #4 confirmed in production feedback queue
- Type: bug, message present, screenshot icon (📷) confirmed

## Step 8: Badge vs Table Count Discrepancy — FIXED (two rounds)
**Result**: BUG FOUND AND FIXED
- **Round 1** (2026-02-22): Badge showed "13 total" vs table "11 permits"
  - Root cause: 5 queries in `web/app.py` used `LIKE '%name%'` substring matching
  - Fix: All 5 queries converted to exact `=` matching with space-variant support
- **Round 2** (2026-02-23): Badge showed "5 total" vs table "11 permits"
  - Root cause: `_get_address_intel` used address-only query (returns 5) while MCP tool uses parcel merge + historical lot discovery (returns 11)
  - Fix: Badge now syncs with MCP tool's actual count by parsing `Found **N** permits` from result markdown
- Final state: Badge and table both show 11 — verified on production

---

## Summary
| Step | Result |
|------|--------|
| 1. Exact match | PASS |
| 2. Parcel merge + badge | PASS |
| 3. Property report | PASS |
| 4. Did you mean? | PASS |
| 5. Permit by number | PASS |
| 6. Screenshot capture | PASS |
| 7. Screenshot submit | PASS |
| 8. Count discrepancy | FIXED (2 rounds) |

**8 PASS, 0 BLOCKED, 1 BUG FOUND + FIXED (2 rounds)**
