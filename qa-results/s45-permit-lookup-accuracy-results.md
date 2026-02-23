# QA Results: Session 45 — Permit Lookup Search Accuracy
**Date**: 2026-02-22
**Tester**: Claude Code (browser automation)
**Target**: https://sfpermits-ai-production.up.railway.app

---

## Step 1: Exact Match — No Substring Bleed
**Result**: PASS
- Searched "146 Lake" — results showed only LAKE ST permits
- Confirmed via JS: `hasBlake: false` — no BLAKE on page
- "Found 11 permits at 146 Lake" — all correct addresses

## Step 2: Parcel Merge — Comprehensive Results
**Result**: PASS
- 11 permits displayed in the table (up from 5 before the fix)
- PERMITS badge shows "13 total" (badge uses broader count, see Step 8)
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
**Result**: BLOCKED (browser automation conflict)
- Feedback modal opens correctly via JS click on `#feedback-fab`
- "Capture Page" button present, html2canvas library lazy-loads from CDN
- On second attempt, html2canvas loaded successfully (`_html2canvasLoaded: true`)
- Capture process started (button disabled) but tab got hijacked by extension
- Root cause: Two Claude in Chrome sessions running simultaneously
- Code-level verification: 5MB limit correctly set in both client JS and server Python

## Step 7: Feedback Submit with Screenshot
**Result**: BLOCKED (same browser automation conflict as Step 6)
- Could not complete screenshot capture to test submission
- HTMX form structure verified correct, endpoint `/feedback/submit` exists

## Step 8: 11 vs 13 Permit Count Discrepancy — FIXED
**Result**: BUG FOUND AND FIXED
- The PERMITS badge (13) came from `_get_address_intel` which used `LIKE '%LAKE%'` — substring matching
- The permit table (11) came from `permit_lookup` MCP tool which uses exact matching
- **Root cause**: 5 queries in `web/app.py` still used `LIKE '%name%'` substring matching
- **Fix applied**: All 5 queries now use exact `=` matching with space-variant support
- Files fixed:
  - `_get_address_intel` permit count query (line ~2536)
  - `_get_address_intel` latest permit type query (line ~2570)
  - `_get_address_intel` routing progress query (line ~2605)
  - `_get_primary_permit_context` query (line ~2347)
  - `_resolve_block_lot` fallback query (line ~2711)
- All 1,226 tests pass after fix

---

## Summary
| Step | Result |
|------|--------|
| 1. Exact match | PASS |
| 2. Parcel merge | PASS |
| 3. Property report | PASS |
| 4. Did you mean? | PASS |
| 5. Permit by number | PASS |
| 6. Screenshot capture | BLOCKED (browser conflict) |
| 7. Screenshot submit | BLOCKED (browser conflict) |
| 8. Count discrepancy | FIXED |

**5 PASS, 2 BLOCKED (external), 1 BUG FOUND + FIXED**
