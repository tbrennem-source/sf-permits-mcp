# Phase 4.5 Timeout Fix - Session 21.2

**Date:** 2026-02-16
**Commit:** `7e6359f`
**Status:** DEPLOYED TO PRODUCTION

---

## Problem

Phase 4.5 visual UI worked for small PDFs (17 pages) but **files with 40+ pages timed out** and showed no gallery.

### User Symptoms
- File under 50 pages (within cap)
- Request timed out after 120 seconds
- No gallery section appeared
- Endless spinning loader with no feedback

### Root Cause
Sequential image rendering took **2-4 seconds per page**, causing total render time to exceed gunicorn's **120-second timeout** for 40+ page files.

**Timing breakdown for 40-page PDF:**
- Vision analysis: 10-30s ✅
- Image rendering: 40 × 3s = **120+ seconds** ❌ (BOTTLENECK)
- Database inserts: 6s ✅
- **Total: ~135-140s > 120s limit** → Timeout kills worker

---

## Solution

**User preference:** "I'm ok with longer timeouts as long as there's an indicator to the user something is still happening."

**Approach:** Keep 50-page cap, increase timeout to 300 seconds, add progress indicator.

### Changes Made

**1. Increased Gunicorn Timeout (120s → 300s)**
- File: `web/railway.toml` line 5
- Change: `--timeout 120` → `--timeout 300`
- Rationale: 300 seconds (5 minutes) allows:
  - 50 pages × 3s = 150s rendering
  - 30s Vision analysis
  - 10s database + response
  - **Total: 190s with 110s safety margin**

**2. Enhanced Progress Indicator**
- File: `web/templates/index.html`
- Replaced simple "Analyzing..." text with:
  - Animated hourglass spinner (⏳) that rotates continuously
  - Clear messaging: "Analyzing plan set... Large files may take 2-3 minutes to process."
  - Pulsing progress dots for visual feedback
  - Users know something is happening, not hung

### CSS Animations Added
```css
.hourglass-spinner {
    font-size: 48px;
    animation: spin 2s linear infinite;
}

.progress-dots .dot {
    animation: dot-pulse 1.4s ease-in-out infinite;
}
```

---

## Expected Outcomes

### Before Fix
- **10-page PDF:** ✅ Works (completes in ~40s)
- **17-page PDF:** ✅ Works (completes in ~60s)
- **40-page PDF:** ❌ Timeout at 120s, no gallery, frustrated user
- **50-page PDF:** ❌ Timeout at 120s, no gallery, no error message

### After Fix
- **10-page PDF:** ✅ Completes in ~40s, hourglass visible during processing
- **17-page PDF:** ✅ Completes in ~60s, hourglass visible during processing
- **40-page PDF:** ✅ Completes in ~140s, hourglass visible throughout, gallery appears
- **50-page PDF:** ✅ Completes in ~190s, hourglass visible throughout, gallery appears

---

## Deployment

**Git History:**
```
7e6359f hotfix: Increase timeout and add progress indicator for large PDFs
986c4b6 Merge claude/clever-snyder: Timeout fix for large PDFs
```

**Files Changed:**
- `web/railway.toml` — 1 line changed (timeout)
- `web/templates/index.html` — 45 lines added (spinner, CSS, messaging)

**Deployment Timeline:**
1. ✅ Committed to `claude/clever-snyder` branch
2. ✅ Merged to `main`
3. ✅ Pushed to GitHub
4. ✅ Deployed to Railway via `railway up --service sfpermits-ai`

**Status:** Active in production

---

## Testing Checklist

### Test Case 1: Small File (10-15 pages)
- [ ] Upload small PDF
- [ ] Hourglass spinner appears immediately
- [ ] Message shows: "Large files may take 2-3 minutes to process"
- [ ] Analysis completes in <60 seconds
- [ ] Gallery appears with all pages

### Test Case 2: Medium File (20-30 pages)
- [ ] Upload medium PDF
- [ ] Hourglass spinner visible throughout
- [ ] Progress dots pulsing
- [ ] Completes in 90-120 seconds
- [ ] Gallery appears with all pages

### Test Case 3: Large File (40-50 pages)
- [ ] Upload large PDF (the failing case before)
- [ ] Hourglass spinner visible for 2-3 minutes
- [ ] User sees clear "2-3 minutes" message
- [ ] **CRITICAL: Does NOT timeout**
- [ ] Completes in 140-190 seconds
- [ ] Gallery appears with all 40-50 pages

### Test Case 4: Very Large File (100 pages)
- [ ] Upload very large PDF
- [ ] Hourglass visible
- [ ] Renders first 50 pages (cap)
- [ ] Completes in ~190 seconds
- [ ] Gallery shows 50 pages

---

## User Experience Improvements

### Before
- ⏳ Endless spinning with no indication of progress
- ❓ "Is it hung? Should I refresh?"
- ❌ Timeout at 120s with no error message
- 😤 Frustrated users

### After
- ⏳ Animated hourglass shows active processing
- 💬 Clear message: "2-3 minutes to process"
- 🎯 Pulsing dots indicate ongoing activity
- ✅ Completes successfully for 40-50 page files
- 😊 Users know to wait

---

## Future Enhancements (Phase 4.6)

**Not implemented yet, but could add:**
1. **Progressive loading** — "Load Next 15 Pages" button
2. **Parallel rendering** — Use multiprocessing to render 4-8 pages simultaneously (4x speedup)
3. **Reduced quality option** — 100 DPI instead of 150 DPI (saves 40% time)
4. **Background job** — Queue large uploads, email when ready
5. **Real-time progress bar** — Show "Rendering page 23 of 50..."

**But for now:** Quick fix gets users unblocked.

---

## Technical Details

### Bottleneck Location
**File:** `src/vision/pdf_to_images.py` lines 83-104

```python
def pdf_pages_to_base64(pdf_bytes, page_numbers, dpi=150):
    results = []
    for pn in page_numbers:  # Sequential, not parallel
        b64 = pdf_page_to_base64(pdf_bytes, pn, dpi)  # 2-4s per page
        results.append((pn, b64))
    return results
```

- Renders pages one-at-a-time (no parallelization)
- Uses 150 DPI + PNG optimization (high quality but slow)
- For 40 pages: 40 × 3s = 120 seconds (just the rendering)

### Why Not Parallelize Now?

**Reasons to defer:**
- Quick fix unblocks users immediately
- Parallel rendering adds complexity (multiprocessing, shared memory)
- 300s timeout is sufficient for current needs
- Can optimize later if users want faster processing

**When to parallelize:**
- If users complain about 2-3 minute wait times
- If rendering 100+ page files (beyond current 50-page cap)
- Phase 4.6 feature when building progressive loading

---

## Rollback Procedure

If critical issues found:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git revert 986c4b6 7e6359f
git push origin main
railway up --service sfpermits-ai
```

**Graceful degradation:**
- Reverts to 120s timeout
- Reverts to simple "Analyzing..." text
- 40+ page files will timeout again
- Small files (<40 pages) still work

---

## Monitoring

**Check Railway logs for:**
- Timeout errors (should be zero for <50 page files)
- Request durations (should be 140-190s for 40-50 pages)
- User complaints about wait times

**Success metrics:**
- Zero timeout errors for files under 50 pages
- Users complete large uploads successfully
- No confusion about "is it hung?"

---

## Sign-Off

**Hotfix deployed:** 2026-02-16
**Commit:** `7e6359f`
**Railway status:** Active
**QA status:** ⏳ Pending user testing with large PDF

**Next:** User tests with 40-50 page PDF to confirm fix works

---

**Status: DEPLOYED — AWAITING CONFIRMATION** ✅
