# QA Script: Session 45 — Permit Lookup Search Accuracy

**Target**: https://sfpermits-ai-production.up.railway.app
**Features**: Exact street matching, historical lot discovery, parcel merge, screenshot limit

---

## 1. Exact Match — No Substring Bleed
1. Navigate to the permit lookup page
2. Search for "146 Lake"
3. **PASS**: Results show permits at 146 LAKE ST only — NO results for BLAKE, LAKE MERCED HILL, or other substring matches
4. **FAIL**: Any result contains BLAKE or another street that is not LAKE

## 2. Comprehensive Results — Parcel Merge
1. From the same "146 Lake" results
2. Count the total permits returned
3. **PASS**: At least 10 permits are shown (parcel merge pulls in permits from 144 Lake + historical lots)
4. **FAIL**: Only 5 or fewer permits appear (parcel merge not working)

## 3. Property Report Loads
1. From the "146 Lake" results, click the property report link (or verify a property report section exists)
2. **PASS**: Property report section loads with assessed value, zoning, or parcel info
3. **FAIL**: Property report link is missing or errors out

## 4. "Did You Mean?" on Nonexistent Address
1. Search for an address that won't match exactly, e.g., "100 Lak"
2. **PASS**: A "Did you mean?" message appears with street name suggestions
3. **FAIL**: Blank results with no suggestions

## 5. Permit Lookup by Permit Number
1. Search by a known permit number (find one from step 1 results)
2. **PASS**: Single permit detail view loads with permit info, project team, routing
3. **FAIL**: Error or no results

## 6. Feedback Screenshot — Large Page
1. Navigate to a page with substantial content (e.g., a permit results page)
2. Click the feedback/help button (floating button or "?" icon)
3. Capture a screenshot (the widget should offer screenshot capture)
4. **PASS**: Screenshot captures and displays in the feedback form (even for full-page content ~2-5MB)
5. **FAIL**: Screenshot fails to save or shows "too large" error for pages under 5MB

## 7. Feedback Screenshot — Submit
1. With a screenshot captured, type a short feedback message
2. Submit the feedback
3. **PASS**: Feedback submits successfully with the screenshot attached
4. **FAIL**: Submission fails or screenshot is dropped
