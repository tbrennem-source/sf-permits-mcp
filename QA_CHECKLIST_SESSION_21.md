# QA Checklist - Sessions 21.2–21.7

**Test on:** https://sfpermits-ai-production.up.railway.app
**Deployed:** 2026-02-16
**Sessions:** 21.2 (Timeout), 21.3 (Action Buttons), 21.4 (External Links), 21.5 (Analyze Plans Loading), 21.6 (Error Logging), 21.7 (NameError Fix)

---

## Session 21.2: Timeout Fix for Large PDFs

### ✅ Test 1: Small PDF Upload (10-15 pages)
- [ ] Navigate to `/analyze-plans` section
- [ ] Upload a 10-15 page PDF
- [ ] **Verify:** Hourglass spinner (⏳) appears with pulsing dots
- [ ] **Verify:** Message shows "Large files may take 2-3 minutes to process"
- [ ] **Verify:** Analysis completes in <60 seconds
- [ ] **Verify:** Gallery appears with all pages rendered

### ✅ Test 2: Large PDF Upload (40-50 pages)
- [ ] Upload a 40-50 page PDF
- [ ] **Verify:** Hourglass spinner appears throughout
- [ ] **Verify:** Does NOT timeout (was timing out at 120s before fix)
- [ ] **Verify:** Completes in 2-3 minutes
- [ ] **Verify:** Gallery appears with up to 50 pages
- [ ] **Expected result:** No timeout error, full gallery displayed

---

## Session 21.3: Action Buttons & Critical Fixes

### ✅ Test 3: Action Buttons Appear at Top
- [ ] Search for "1234 market" in main search box
- [ ] **Verify:** "Quick Actions" blue box appears at TOP of results (not bottom)
- [ ] **Verify:** Box has blue background `rgba(79, 143, 247, 0.06)`
- [ ] **Verify:** All 4 buttons visible:
  - [ ] 📊 View Property Report (blue button)
  - [ ] 💬 Ask AI (white with blue border)
  - [ ] 🔍 Analyze Project (white with gray border)
  - [ ] ⚠️ Check Violations (white with gray border)

### ✅ Test 4: Property Report Button Works (Critical Fix)
**Before:** Property report button was missing for most searches (due to `_ph()` bug)

- [ ] Search for "75 robinhood dr"
- [ ] **Verify:** "📊 View Property Report" button appears in Quick Actions
- [ ] Click the button
- [ ] **Verify:** Navigates to `/report/{block}/{lot}`
- [ ] **Verify:** Property report page loads successfully

### ✅ Test 5: Ask AI Button
- [ ] From search results for "75 robinhood dr"
- [ ] Click "💬 Ask AI" button
- [ ] **Verify:** Submits search with query "What permits are needed for work at 75 robinhood dr?"
- [ ] **Verify:** Results appear with AI-powered guidance

### ✅ Test 6: Analyze Project Button (Fixed)
**Before:** Clicking did nothing (broken link to `/?experience=expert&address=...`)

- [ ] Click "🔍 Analyze Project" button
- [ ] **Verify:** Submits to `/ask` with query "I want to analyze a project at 75 robinhood dr"
- [ ] **Verify:** Response guides user or opens analyze section

### ✅ Test 7: Check Violations Button
- [ ] Click "⚠️ Check Violations" button
- [ ] **Verify:** Submits to `/ask` with query "Are there any violations at 75 robinhood dr?"
- [ ] **Verify:** Shows complaints/violations section with results

### ✅ Test 8: Hourglass Spinner on Permit Lookup
- [ ] Click "Look up a permit" to reveal lookup form
- [ ] Enter address: "1234 market"
- [ ] Click submit
- [ ] **Verify:** Hourglass spinner (⏳) appears while searching
- [ ] **Verify:** Message shows "Searching 1.1M permits across 22 datasets"
- [ ] **Verify:** Progress dots pulse in sequence

### ✅ Test 9: Block/Lot Resolution Fallback
**Before:** Only exact matches worked, "1234 market" would fail

- [ ] Search for "1234 market" (fuzzy address)
- [ ] **Verify:** Block/lot is resolved via fallback query
- [ ] **Verify:** Property Report button appears
- [ ] Click Property Report button
- [ ] **Verify:** Report loads for correct block/lot

---

## Session 21.4: External Link Fix

### ✅ Test 10: Permit Number Links (Internal Search)
**Before:** Clicking permit numbers redirected to dbiweb02.sfgov.org (broken external site)

- [ ] Navigate to any property report (e.g., `/report/3506/001`)
- [ ] Scroll to "Permit History" table
- [ ] Click on any permit number (e.g., `202201012345`)
- [ ] **Verify:** URL changes to `/?q=202201012345` (NOT external site)
- [ ] **Verify:** Search auto-submits via HTMX
- [ ] **Verify:** Permit details appear
- [ ] **Verify:** Quick Actions buttons appear at top
- [ ] **Verify:** No redirect to dbiweb02.sfgov.org

### ✅ Test 11: Complaint Number Links (Internal Search)
- [ ] Navigate to property report with complaints
- [ ] Scroll to "Complaints" section
- [ ] Click on complaint number (e.g., `#202429366`)
- [ ] **Verify:** URL changes to `/?q=202429366` (NOT external site)
- [ ] **Verify:** Complaint details appear from our database
- [ ] **Verify:** Quick Actions buttons appear
- [ ] **Verify:** Stays within our app (no external redirect)

### ✅ Test 12: Violation Number Links (Internal Search)
- [ ] Find property with violations (e.g., "75 robinhood dr")
- [ ] Navigate to property report
- [ ] Scroll to "Violations" section
- [ ] Click on violation/complaint number
- [ ] **Verify:** Internal search triggered (NOT external redirect)
- [ ] **Verify:** Results show within our interface

### ✅ Test 13: Nearby Permit Links (Internal Search)
- [ ] In property report, scroll to "Nearby Permit Activity"
- [ ] Click on any nearby permit number
- [ ] **Verify:** Internal search triggered
- [ ] **Verify:** Permit details appear
- [ ] **Verify:** Quick Actions available

### ✅ Test 14: Risk Assessment Card Links
- [ ] In property report, check "Risk Assessment" section
- [ ] If there are risk cards with complaint/permit links, click them
- [ ] **Verify:** Internal search triggered (NOT external redirect)

---

## Session 21.5: Analyze Plans Loading Indicator

### ✅ Test 15: Loading Indicator Shows Immediately on Upload (WITH DEBUG CONSOLE)
**Before:** No loading indicator appeared when uploading PDF to "Analyze Plan Set" - form appeared frozen
**Fix iteration 2:** Added robust IIFE-based event handling with console logging for debugging

- [ ] **IMPORTANT:** Hard refresh page first (`Cmd+Shift+R` Mac / `Ctrl+Shift+F5` Windows) to clear cache
- [ ] Open Browser DevTools → Console tab
- [ ] Navigate to homepage, click "Analyze Plan Set" to expand section
- [ ] **Verify in console:** See `[Analyze Plans] Loading indicator setup complete`
- [ ] Select any PDF file (small or large)
- [ ] Click "Analyze Plan Set" button
- [ ] **Verify in console:** See `[Analyze Plans] Form submit event fired`
- [ ] **Verify:** Hourglass spinner (⏳) appears IMMEDIATELY
- [ ] **Verify:** Message shows "Analyzing plan set..."
- [ ] **Verify:** Message shows "Large files may take 2-3 minutes to process"
- [ ] **Verify:** Progress dots pulse in sequence
- [ ] **Verify:** Submit button becomes disabled AND faded (opacity 0.6)
- [ ] **Verify:** Loading indicator remains visible throughout upload/processing
- [ ] **Verify:** Results appear after processing completes
- [ ] **Verify in console:** See `[Analyze Plans] HTMX afterRequest event fired` when done
- [ ] **Verify:** Loading indicator disappears when results show
- [ ] **Verify:** Submit button re-enabled and full opacity restored

**If indicator doesn't show:**
- [ ] Check console for JavaScript errors (red text)
- [ ] Check if setup message appeared
- [ ] Check if submit event fired
- [ ] Report console output for debugging

### ✅ Test 16: Large File Upload with Loading Indicator (Timeout Verification)
- [ ] Hard refresh page to clear cache
- [ ] Open DevTools console
- [ ] Select 40-50 page PDF
- [ ] Click "Analyze Plan Set"
- [ ] **Verify in console:** Form submit event fires
- [ ] **Verify:** Loading indicator appears immediately (not delayed)
- [ ] **Verify:** Indicator remains visible for entire 2-3 minute processing time
- [ ] **Verify:** Button stays disabled and faded throughout
- [ ] **Verify:** No timeout error (300s limit from Session 21.2)
- [ ] **Verify:** Gallery appears with results after processing
- [ ] **Verify in console:** HTMX afterRequest event fires when complete

---

## Session 21.6: Error Logging for Analyze Plans

### ✅ Test 29: Verify Error Logging to Railway (Admin Test)
**Before:** 500 errors with NO messages in Railway logs
**After:** Full stack traces logged, users see helpful error messages

- [ ] Hard refresh page
- [ ] Upload valid small PDF (should work now or show clear error)
- [ ] **SSH to Railway OR check logs:** `railway logs --service sfpermits-ai --tail 50`
- [ ] **Verify in logs:** See `INFO [analyze-plans] Processing PDF: filename.pdf (X.XX MB)`
- [ ] **If upload fails:**
  - [ ] Check logs for full Python stack trace
  - [ ] Error should show which component failed (database, poppler, Vision API, etc.)
  - [ ] User should see styled error box (not generic 500)

### ✅ Test 30: User-Visible Error Details
**Feature:** Users can now see technical details when analysis fails

- [ ] If analyze fails, verify error display shows:
  - [ ] Red X icon with "❌ Analysis Error" header
  - [ ] Clear error message describing what went wrong
  - [ ] Expandable "📋 Technical Details" section (collapsed by default)
  - [ ] Click to expand - shows full Python traceback
  - [ ] "This error has been logged" message at bottom
- [ ] Error box is styled (not plain text)
- [ ] Traceback is readable (monospace font, scrollable)

### ✅ Test 31: File Size Validation
**New:** 400 MB file size limit with proper HTTP 413 status

- [ ] Try uploading file > 400 MB
- [ ] **Verify:** Error message shows: "❌ File too large: X.X MB / Maximum file size is 400 MB"
- [ ] **Verify:** Returns HTTP 413 status (not 500)
- [ ] Upload file < 400 MB
- [ ] **Verify:** Processes normally (or shows different error if analysis fails)

### ✅ Test 32: Poppler Dependency Detection
**Feature:** Clear error if poppler-utils not installed

- [ ] If PDF rendering fails with poppler error:
  - [ ] Error message should say: "PDF rendering failed. This usually means 'poppler-utils' is not installed"
  - [ ] Railway logs show: `[pdf_to_images] Poppler error converting page X`
  - [ ] Admin knows to install poppler-utils
- [ ] **Note:** This test requires poppler to be missing (likely not the case on production)

---

## Session 21.7: NameError Fix (Analyze Plans Now Works End-to-End)

### ✅ Test 33: Full Analyze Plans End-to-End (CRITICAL)
**Before:** Analysis succeeded but results never rendered (two NameErrors crashed serialization)
**After:** `import json` added, `logger` → `logging` fixed

- [ ] Hard refresh page (`Cmd+Shift+R`)
- [ ] Navigate to "Analyze Plan Set" section
- [ ] Upload a PDF file
- [ ] Click "Analyze Plan Set"
- [ ] **Verify:** Hourglass spinner appears immediately (Session 21.5)
- [ ] **Verify:** After 30-60 seconds, analysis results render on screen
- [ ] **Verify:** Page image gallery appears with thumbnails
- [ ] **Verify:** EPR compliance checks shown
- [ ] **Verify:** No 500 error in browser console
- [ ] **Verify in Railway logs:** No `NameError` — clean completion

### ✅ Test 34: Multi-Page PDF Analysis
- [ ] Upload PDF with 5+ pages
- [ ] Click "Analyze Plan Set"
- [ ] **Verify:** Hourglass appears, results render after processing
- [ ] **Verify:** Multiple page thumbnails in gallery
- [ ] **Verify:** Page extractions display correctly

---

## Edge Cases & Regression Tests

### ✅ Test 17: No Results Case
- [ ] Search for address with no permits (e.g., "99999 nonexistent st")
- [ ] **Verify:** "What you can do next" section appears
- [ ] **Verify:** Contains:
  - [ ] "Run Property Report" link (if block/lot resolved)
  - [ ] "Ask AI about permits for this address" button
  - [ ] "Try a different search" link
- [ ] **Verify:** Quick Actions do NOT appear (only show when results exist)

### ✅ Test 18: Block/Lot Direct Lookup
- [ ] Use lookup form with mode "Block/Lot"
- [ ] Enter Block: "3506", Lot: "001"
- [ ] Submit
- [ ] **Verify:** Quick Actions appear with all 4 buttons
- [ ] **Verify:** Property Report button shows
- [ ] **Verify:** Street address shown as "Block 3506, Lot 001"

### ✅ Test 19: Permit Number Direct Lookup
- [ ] Use lookup form with mode "Permit Number"
- [ ] Enter a valid permit number
- [ ] Submit
- [ ] **Verify:** Quick Actions appear
- [ ] **Verify:** Buttons work correctly

### ✅ Test 20: Navigation Between Features
- [ ] Search for "1234 market"
- [ ] Click "📊 View Property Report"
- [ ] From property report, click a permit number
- [ ] **Verify:** Returns to search results (internal navigation)
- [ ] Click "📊 View Property Report" again
- [ ] **Verify:** Smooth navigation back to report

---

## Visual & UX Verification

### ✅ Test 21: Quick Actions Styling
- [ ] **Verify:** Quick Actions box has:
  - [ ] Blue background: `rgba(79, 143, 247, 0.06)`
  - [ ] Blue border: `rgba(79, 143, 247, 0.2)`
  - [ ] Rounded corners
  - [ ] "Quick Actions" heading in bold
  - [ ] Buttons wrap on mobile/narrow screens
  - [ ] 10px gap between buttons

### ✅ Test 22: Button Hierarchy
- [ ] **Verify:** Primary button (View Property Report):
  - [ ] Blue background (`#4f8ff7`)
  - [ ] White text
  - [ ] Most prominent
- [ ] **Verify:** Secondary buttons:
  - [ ] White/transparent background
  - [ ] Colored borders
  - [ ] Clear visual hierarchy

### ✅ Test 23: Hourglass Animation
- [ ] Trigger any search/lookup
- [ ] **Verify:** Hourglass emoji rotates smoothly (2s loop)
- [ ] **Verify:** Progress dots pulse in sequence (0.2s delay between each)
- [ ] **Verify:** Animation is smooth, not janky

---

## Performance & Timeout Verification

### ✅ Test 24: Large File Doesn't Timeout
- [ ] Upload 50-page PDF to `/analyze-plans`
- [ ] **Verify:** Completes within 300 seconds (5 minutes)
- [ ] **Verify:** Does NOT show timeout error
- [ ] **Verify:** Full gallery appears

### ✅ Test 25: Server Response Time
- [ ] Search for "1234 market"
- [ ] **Verify:** Results appear in <2 seconds
- [ ] **Verify:** Quick Actions render immediately with results

---

## Database & Backend Verification

### ✅ Test 26: Block/Lot Fallback Query Works
**Technical verification of the fix for `_ph()` bug**

- [ ] Search for fuzzy address: "1234 market st"
- [ ] Check browser DevTools → Network tab
- [ ] Look for `/ask` POST request
- [ ] **Verify:** Response includes `report_url` field
- [ ] **Verify:** Property Report button appears

### ✅ Test 27: No External Redirects
- [ ] Open browser DevTools → Network tab
- [ ] Navigate to property report
- [ ] Click on permit numbers, complaint numbers
- [ ] **Verify:** NO requests to `dbiweb02.sfgov.org`
- [ ] **Verify:** All requests stay within `sfpermits-ai-production.up.railway.app`

---

## Critical Path Test (End-to-End)

### ✅ Test 28: Full User Journey
1. [ ] Start at homepage: https://sfpermits-ai-production.up.railway.app
2. [ ] Search for "75 robinhood dr"
3. [ ] **Verify:** Quick Actions appear at TOP in blue box
4. [ ] Click "📊 View Property Report"
5. [ ] **Verify:** Property report loads
6. [ ] Scroll to "Permit History" table
7. [ ] Click on a permit number
8. [ ] **Verify:** Returns to search results (internal search, not external)
9. [ ] **Verify:** Quick Actions available
10. [ ] Click "⚠️ Check Violations"
11. [ ] **Verify:** Violations/complaints results appear
12. [ ] Upload a PDF to analyze plans
13. [ ] **Verify:** Hourglass spinner appears
14. [ ] **Verify:** Analysis completes without timeout
15. [ ] **Success:** Full workflow works end-to-end

---

## Known Issues / Expected Behavior

### Expected Behaviors (Not Bugs)
- [ ] **Analyze Project button** submits generic "I want to analyze..." query (doesn't pre-fill form directly)
- [ ] **Property Report button** may not appear if block/lot cannot be resolved (rare edge case)
- [ ] **External links** to SF Planning (parcel maps) and Planning Code still open in external sites (intentional - those sites work fine)

---

## Sign-Off

**Tester:** _______________
**Date:** _______________
**Environment:** Production (Railway)
**Build:** `c47fc88` (Session 22) / `c376e80` (Session 21.4)

**Overall Status:**
- [ ] ✅ All tests passed
- [ ] ⚠️ Minor issues found (list below)
- [ ] ❌ Critical issues found (list below)

**Issues Found:**
1. _________________________________
2. _________________________________
3. _________________________________

**Notes:**
_________________________________
_________________________________
_________________________________
