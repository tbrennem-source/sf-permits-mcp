# QA Checklist: Phase 4.5 Visual Plan Analysis UI

## Pre-Deployment Verification

### ✅ Code Review
- [x] All backend routes implemented (Waves 1-3, 6)
- [x] Frontend template rewritten (11 → 931 lines)
- [x] Database migrations added (PostgreSQL + DuckDB)
- [x] Nightly cleanup integrated
- [x] Test files created (21 new tests)

### ✅ File Checklist
- [x] `web/plan_images.py` — Storage module (171 lines)
- [x] `src/tools/analyze_plans.py` — return_structured parameter added
- [x] `web/app.py` — Routes + migrations + enhanced analyze_plans_route
- [x] `src/db.py` — DuckDB schema added
- [x] `web/templates/analyze_plans_results.html` — Full visual UI
- [x] `tests/test_plan_images.py` — Unit tests
- [x] `tests/test_plan_ui.py` — Integration tests
- [x] `CHANGELOG.md` — Session 20 entry added

---

## Local Testing (Pre-Deploy)

### Database Schema
- [ ] DuckDB tables created: `plan_analysis_sessions`, `plan_analysis_images`
- [ ] PostgreSQL migration runs without errors
- [ ] Indexes created: `idx_plan_sessions_created`
- [ ] CASCADE delete works (delete session → images deleted)

### Backend Routes
- [ ] `/plan-images/<session_id>/<page>` returns PNG image
- [ ] `/plan-session/<session_id>` returns JSON metadata
- [ ] `/plan-images/<session_id>/download-all` returns ZIP file
- [ ] `/plan-analysis/email` sends email successfully
- [ ] Invalid session_id returns 404

### analyze_plans Tool
- [ ] `return_structured=False` returns markdown string (backward compatible)
- [ ] `return_structured=True` returns tuple (markdown, page_extractions)
- [ ] MCP tool still works (no regression)
- [ ] Page extractions format matches template expectations

### Image Rendering
- [ ] `pdf_pages_to_base64()` renders pages correctly
- [ ] Base64 encoding/decoding works
- [ ] Image size reasonable (~50-150 KB per page)
- [ ] 50-page cap enforced
- [ ] Graceful degradation when rendering fails

---

## Production Testing (Post-Deploy)

### Deployment
- [ ] Railway deployment succeeds
- [ ] Database migration runs automatically on startup
- [ ] No errors in Railway logs
- [ ] Tables created in PostgreSQL production DB

### Upload & Analysis
**Test file:** `~/Downloads/sample-permit-plans/permit-plan-set.pdf` (or any architectural PDF)

- [ ] Upload PDF to `/analyze-plans`
- [ ] Analysis completes successfully
- [ ] Markdown report displayed
- [ ] Session ID generated
- [ ] Page count correct

### Thumbnail Gallery
- [ ] Thumbnail grid renders
- [ ] Lazy loading works (only visible images load)
- [ ] Page numbers displayed correctly
- [ ] Sheet IDs displayed (if extracted)
- [ ] Grid responsive on mobile (2 columns)
- [ ] Click thumbnail opens detail card

### Detail Card
- [ ] Card appears when thumbnail clicked
- [ ] Image displays correctly
- [ ] Sheet metadata populated (or "—" placeholders)
- [ ] Metadata fields: Sheet #, Address, Firm, Stamp
- [ ] Action buttons present: Download, Full Screen, Compare

### Lightbox Viewer
- [ ] Click "Full Screen" opens lightbox
- [ ] Image displays at full resolution
- [ ] Page info displays: "Page X of Y"
- [ ] Sheet info displays (if metadata exists)
- [ ] Keyboard navigation works:
  - [ ] Left arrow → previous page
  - [ ] Right arrow → next page
  - [ ] Escape → close lightbox
- [ ] Click backdrop → close lightbox
- [ ] Navigation wraps (page 1 ← from page N)

### Side-by-Side Comparison
- [ ] Click "Compare" opens comparison view
- [ ] Dropdowns populated with page list
- [ ] Sheet metadata shown in dropdown options
- [ ] Left/right panels display different pages
- [ ] Changing dropdown updates panel image
- [ ] Panels equal width
- [ ] "Download Both Pages" triggers 2 downloads
- [ ] "Email Comparison" opens email modal

### Download Functions
- [ ] Download single page → PNG file downloads
- [ ] Download all pages → ZIP file downloads
- [ ] ZIP contains all pages (up to 50)
- [ ] ZIP filename: `{original-filename}-pages.zip`
- [ ] File sizes reasonable

### Email Functions
- [ ] Click "Email Full Analysis" opens modal
- [ ] Recipient field works
- [ ] Message field works
- [ ] Submit sends email
- [ ] Email received (check Mailgun logs)
- [ ] Email body contains: filename, page count, view link
- [ ] Comparison email context correct

### Print Functions
- [ ] Click "Print Report" triggers browser print
- [ ] Print preview shows full analysis report
- [ ] Single page print works (opens new window)

### Performance
- [ ] Upload + analysis completes in <30 seconds
- [ ] Image rendering non-blocking (analysis shows first)
- [ ] Thumbnails load progressively (lazy)
- [ ] No browser freezing/lag
- [ ] Page navigation smooth

### Caching
- [ ] Image URLs include Cache-Control header
- [ ] Browser caches images (check Network tab)
- [ ] Re-opening detail card uses cached image

### Cleanup (24h Expiry)
- [ ] Wait 24+ hours or manually trigger `/cron/nightly`
- [ ] Old sessions deleted from database
- [ ] Images CASCADE deleted
- [ ] Cleanup count reported in cron response JSON

---

## Edge Cases

### Large PDFs
- [ ] 100+ page PDF → only renders first 50
- [ ] No timeout errors
- [ ] Graceful message if >50 pages

### Invalid Inputs
- [ ] Invalid session_id → 404 error
- [ ] Expired session → 404 error (after cleanup)
- [ ] Non-PDF file → error message
- [ ] Corrupt PDF → error message

### Missing Metadata
- [ ] PDF with no title blocks → detail cards show "—"
- [ ] No Vision API key → falls back to metadata-only
- [ ] Vision API failure → graceful degradation

### Mobile/Responsive
- [ ] Thumbnail grid collapses to 2 columns on mobile
- [ ] Detail card stacks vertically on mobile
- [ ] Lightbox works on mobile (touch gestures)
- [ ] Comparison panels stack on mobile

### Graceful Degradation
- [ ] Image rendering failure → text report still works
- [ ] No session_id → thumbnail gallery hidden
- [ ] Gallery section only shows if session exists

---

## Security Checks

### Session IDs
- [ ] Generated via `secrets.token_urlsafe(16)` (cryptographically secure)
- [ ] No sequential IDs
- [ ] No predictable patterns
- [ ] Acts as capability token (no separate auth needed)

### Input Validation
- [ ] File type validation (PDF only)
- [ ] File size limit enforced
- [ ] Email recipient validated
- [ ] No XSS in user inputs

### Database
- [ ] No SQL injection vectors
- [ ] CASCADE delete prevents orphaned images
- [ ] FOREIGN KEY constraints enforced

---

## Regression Testing

### Existing Features (Should Still Work)
- [ ] `/analyze-plans` text report (without images) works
- [ ] MCP `analyze_plans` tool works
- [ ] Other tools unaffected: `predict_permits`, `estimate_fees`, etc.
- [ ] Admin feedback queue works
- [ ] Morning briefs send successfully
- [ ] Nightly cron works (including new cleanup)

### Test Suite
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] All 833 tests pass
- [ ] No new failures introduced
- [ ] No test warnings

---

## Monitoring (Post-Deploy)

### Railway Metrics
- [ ] Database size reasonable (<100 MB with cleanup)
- [ ] Memory usage stable
- [ ] No memory leaks
- [ ] Response times acceptable

### Logs
- [ ] No errors in application logs
- [ ] Image rendering logged: "Created plan session {id}: {filename}"
- [ ] Cleanup logged: "Cleaned up N expired plan sessions"

### User Feedback
- [ ] Monitor `/admin/feedback` for issues
- [ ] No complaints about slow loading
- [ ] No complaints about missing features

---

## Rollback Plan

If critical issues found in production:

1. **Revert deployment:**
   ```bash
   git revert HEAD
   git push origin claude/clever-snyder
   ```

2. **Database cleanup (if needed):**
   ```sql
   DROP TABLE IF EXISTS plan_analysis_images CASCADE;
   DROP TABLE IF EXISTS plan_analysis_sessions CASCADE;
   ```

3. **Restore old template:**
   - Template will fall back to text-only report
   - No session_id passed → gallery hidden

4. **Monitor:**
   - Existing analysis still works (metadata-only)
   - No data loss (sessions are ephemeral)

---

## Sign-Off

### Pre-Deployment
- [ ] Code review complete
- [ ] Local testing complete
- [ ] Documentation updated
- [ ] CHANGELOG updated

### Post-Deployment
- [ ] Production smoke test passed
- [ ] No critical errors in logs
- [ ] Feature working as expected
- [ ] Monitoring dashboard green

**Deployed by:** _____________
**Deployment date:** 2026-02-16
**Railway deployment ID:** _____________
**Sign-off:** _____________ (after QA complete)

---

## Notes

**Known limitations (Phase 4.5):**
- 50-page cap (configurable via future env var)
- No PDF report generation (requires weasyprint dependency)
- No annotation/markup tools (Phase 4.6)
- No measurement tools (Phase 4.6)
- No version comparison/diff (Phase 4.6)

**Future enhancements (Phase 4.6):**
- Canvas overlay for annotations (pen, highlight, shapes)
- Measurement tools (distance, area, angle)
- Visual diff between plan versions (red/green overlay)
- Scale calibration for accurate measurements
