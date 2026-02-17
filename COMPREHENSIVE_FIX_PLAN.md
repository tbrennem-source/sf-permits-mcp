# Comprehensive Fix Plan - All 9 Issues

## Current Status: BROKEN IN PRODUCTION

Railway deployment is live but completely non-functional due to 9 critical issues found in audit.

---

## Issues to Fix

### Issue #1: Missing `import json` ✅ FIXED in commit `abfdfba`
- Added `import json` to top-level imports

### Issue #2: Undefined `logger` variable ✅ PARTIALLY FIXED in commit `abfdfba`
- Fixed line 846: `logger.warning()` → `logging.warning()`
- **STILL BROKEN:** Line 954 in email route still uses `logger.error()`
- **FIX:** Change line 954 to `logging.error()`

### Issue #3: URL path mismatch (CRITICAL - ALL IMAGES FAIL)
**Problem:** Template uses `/plan-images/{id}/page/{num}` but route is `/plan-images/{id}/{num}`
- Template line 556: `/plan-images/{{ session_id }}/page/{{ loop.index0 }}`
- Template line 689: `/plan-images/${sessionId}/page/${pageNum}`
- Template line 730: `/plan-images/${sessionId}/page/${currentPage}`
- Template line 794: `/plan-images/${sessionId}/page/${pageNum}`
- Route line 860: `@app.route("/plan-images/<session_id>/<int:page_number>")`

**FIX:** Remove `/page/` from ALL template URLs
- Change `/plan-images/${sessionId}/page/${pageNum}` → `/plan-images/${sessionId}/${pageNum}`

### Issue #4: Download ZIP path mismatch
- Template line 809: `/plan-images/${sessionId}/download-zip`
- Route line 895: `/plan-images/<session_id>/download-all`

**FIX:** Change template to `/plan-images/${sessionId}/download-all`

### Issue #5: Missing download-pdf route
- Template line 826 calls `/plan-images/${sessionId}/download-pdf`
- No route exists

**FIX:** Comment out or remove PDF download button (Phase 4.6 feature)
- Already done in earlier hotfix (line 538-542 commented out)
- But JavaScript function still exists and could be called
- Also remove/comment the downloadReport() function

### Issue #6: Email route parameter mismatch
- Route: `@app.route("/plan-images/email", methods=["POST"])`
- Function: `def email_analysis():` (no session_id parameter)
- Route gets session_id from JSON body, not URL

**FIX:** This is actually OK as-is (session_id comes from JSON). No change needed.

### Issue #7: Template variable `extractions` not passed ✅ FIXED in commit `9f118ea`
- Fixed: Now passes `extractions=extractions_list`

### Issue #8: Inline imports (minor)
- Not critical, leave as-is for now

### Issue #9: Inconsistent logging
- Line 954 still uses `logger.error()` - covered by Issue #2

---

## Files to Modify

### 1. web/app.py
- [ ] Line 954: Change `logger.error()` → `logging.error()`

### 2. web/templates/analyze_plans_results.html
- [ ] Line 556: Remove `/page/` from URL
- [ ] Line 689: Remove `/page/` from URL
- [ ] Line 730: Remove `/page/` from URL
- [ ] Line 794: Remove `/page/` from URL
- [ ] Line 805: Remove `/page/` and `?download=1` from URL
- [ ] Line 809: Change `/download-zip` → `/download-all`
- [ ] Line 817-821: Remove `/page/` from comparison download URLs
- [ ] Line 833: Remove `/page/` from print window src

---

## Complete Fix

### File: web/app.py

**Line 954 change:**
```python
# FROM:
logger.error(f"Email send failed: {e}")

# TO:
logging.error(f"Email send failed: {e}")
```

### File: web/templates/analyze_plans_results.html

**All URL changes (8 locations):**

1. **Line 556 (HTML thumbnail src):**
```html
<!-- FROM: -->
<img src="/plan-images/{{ session_id }}/page/{{ loop.index0 }}"

<!-- TO: -->
<img src="/plan-images/{{ session_id }}/{{ loop.index0 }}"
```

2. **Line 689 (JavaScript detail card):**
```javascript
// FROM:
document.getElementById('detail-img').src = `/plan-images/${sessionId}/page/${pageNum}`;

// TO:
document.getElementById('detail-img').src = `/plan-images/${sessionId}/${pageNum}`;
```

3. **Line 730 (JavaScript lightbox):**
```javascript
// FROM:
document.getElementById('lightbox-img').src = `/plan-images/${sessionId}/page/${currentPage}`;

// TO:
document.getElementById('lightbox-img').src = `/plan-images/${sessionId}/${currentPage}`;
```

4. **Line 794 (JavaScript comparison panel):**
```javascript
// FROM:
img.src = `/plan-images/${sessionId}/page/${pageNum}`;

// TO:
img.src = `/plan-images/${sessionId}/${pageNum}`;
```

5. **Line 805 (JavaScript downloadPage):**
```javascript
// FROM:
window.location.href = `/plan-images/${sessionId}/page/${currentPage}?download=1`;

// TO:
window.location.href = `/plan-images/${sessionId}/${currentPage}`;
```
(Remove `?download=1` - not needed, browser will download PNG anyway)

6. **Line 809 (JavaScript downloadAllPages):**
```javascript
// FROM:
window.location.href = `/plan-images/${sessionId}/download-zip`;

// TO:
window.location.href = `/plan-images/${sessionId}/download-all`;
```

7. **Lines 817-821 (JavaScript downloadComparison):**
```javascript
// FROM:
window.location.href = `/plan-images/${sessionId}/page/${leftPage}?download=1`;
// ... and ...
window.location.href = `/plan-images/${sessionId}/page/${rightPage}?download=1`;

// TO:
window.location.href = `/plan-images/${sessionId}/${leftPage}`;
// ... and ...
window.location.href = `/plan-images/${sessionId}/${rightPage}`;
```

8. **Line 833 (JavaScript print window):**
```javascript
// FROM:
const imgSrc = `/plan-images/${sessionId}/page/${currentPage}`;

// TO:
const imgSrc = `/plan-images/${sessionId}/${currentPage}`;
```

---

## Testing Checklist (After Fix)

- [ ] Upload PDF to /analyze-plans
- [ ] Analysis completes (no 500 error)
- [ ] Thumbnail gallery appears
- [ ] **Images load (200 OK, not 404)**
- [ ] Click thumbnail → detail card shows image
- [ ] Lightbox opens with image
- [ ] ZIP download works
- [ ] Email works
- [ ] No console errors

---

## Deployment Steps

1. Make all changes above
2. Test locally if possible
3. Commit: "hotfix: Fix all remaining URL paths and logger references"
4. Deploy via `railway up --service sfpermits-ai`
5. Wait for Railway "Active" status
6. Run full testing checklist
7. If still broken: ROLLBACK and regroup

---

## Summary

**9 issues found, 8 need fixing:**
- ✅ Issue #1: Fixed (json import)
- ⚠️ Issue #2: Partially fixed (1 logger.error remains)
- ❌ Issue #3: NOT FIXED (8 URL paths wrong)
- ❌ Issue #4: NOT FIXED (download-zip → download-all)
- ✅ Issue #5: Already handled (PDF button commented out)
- ✅ Issue #6: OK as-is (session_id from JSON)
- ✅ Issue #7: Fixed (extractions variable)
- ➖ Issue #8: Minor, skip
- ⚠️ Issue #9: Same as #2

**Critical fixes needed:**
1. Remove `/page/` from 8 URL locations in template
2. Change `/download-zip` to `/download-all` in template
3. Change `logger.error()` to `logging.error()` in app.py line 954

**Total changes:** 2 files, 9 lines
