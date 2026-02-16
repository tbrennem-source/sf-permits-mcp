# Visual Plan Analysis UI — User Guide

## Quick Start

1. **Upload PDF:** Go to `/analyze-plans` and upload a plan set PDF
2. **View Analysis:** Scroll down to see the full text analysis report
3. **Browse Thumbnails:** Thumbnail gallery appears below the report
4. **Click Thumbnail:** Opens detail card with metadata
5. **Full Screen:** Click 🔍 button to open lightbox viewer
6. **Compare:** Click ⇄ button to view two pages side-by-side
7. **Download:** Click 📥 to download single page or all pages (ZIP)
8. **Email:** Click 📧 to share analysis with recipient

---

## Features

### 📸 Thumbnail Gallery
**What:** Grid view of all plan pages (up to 50)

**Features:**
- Lazy loading (images load as you scroll)
- Page numbers displayed
- Sheet IDs shown (if extracted by Vision API)
- Click any thumbnail to see details

**Layout:**
- Desktop: 4-6 thumbnails per row
- Mobile: 2 thumbnails per row

---

### 📋 Detail Card
**What:** Rich card showing extracted metadata for selected page

**Displays:**
- High-res page image
- Sheet number (e.g., "A1.0")
- Sheet name (e.g., "FLOOR PLAN")
- Project address
- Firm name
- Professional stamp status

**Actions:**
- 📥 Download Page — Save as PNG
- 🔍 Full Screen — Open lightbox viewer
- ⇄ Compare — Open side-by-side view

---

### 🔍 Lightbox Viewer
**What:** Full-screen overlay for viewing pages at full resolution

**Navigation:**
- **Left arrow** (←) — Previous page
- **Right arrow** (→) — Next page
- **Escape** (Esc) — Close lightbox
- **Click backdrop** — Close lightbox

**Displays:**
- Page number: "Page 5 of 12"
- Sheet info: "A1.0 - FLOOR PLAN"

**Actions:**
- 📥 Download — Save current page
- 🖨️ Print — Print current page

**Keyboard shortcuts:**
```
←     Previous page
→     Next page
Esc   Close lightbox
```

---

### ⇄ Side-by-Side Comparison
**What:** Compare any two pages simultaneously

**Features:**
- Dropdown selectors for left/right pages
- Equal-width panels
- Synchronized scrolling (optional)
- Sheet metadata in dropdowns

**Actions:**
- 📥 Download Both Pages — Downloads left + right
- 📧 Email Comparison — Share comparison via email

**Use cases:**
- Compare revisions
- Check consistency across sheets
- Review details side-by-side

---

### 📥 Download Functions

**Single Page:**
- Click 📥 in detail card or lightbox
- Downloads as: `page-5.png`

**All Pages (ZIP):**
- Click "📥 Download All Pages (ZIP)"
- Downloads as: `{filename}-pages.zip`
- Contains all pages up to 50

**File format:** PNG images (150 DPI, max 1568px width)

---

### 📧 Email Sharing

**Full Analysis:**
1. Click "📧 Email Full Analysis"
2. Enter recipient email
3. Add optional message
4. Click "Send"

**Email includes:**
- Filename and page count
- Your message
- Link to view session online (valid 24h)

**Comparison:**
1. Select two pages in comparison view
2. Click "📧 Email Comparison"
3. Email includes both page numbers

**Delivery:** Via Mailgun (instant)

---

### 🖨️ Print Functions

**Print Report:**
- Click "🖨️ Print Report"
- Prints full analysis (text + metadata tables)

**Print Page:**
- Open lightbox
- Click "🖨️ Print"
- Opens new window with single page
- Triggers browser print dialog

---

## Technical Details

### Session Expiry
- **Duration:** 24 hours
- **Cleanup:** Automatic (runs nightly at 3am PT)
- **What happens:** Images deleted, session expires
- **Effect:** Thumbnail links return 404 after expiry

### Performance
- **Upload:** <5 seconds (typical PDF)
- **Analysis:** 10-30 seconds (includes Vision API)
- **Image rendering:** 1-3 seconds per page
- **Total time:** Usually <30 seconds

### Limits
- **Max pages rendered:** 50 (larger PDFs only show first 50)
- **File size:** Up to 100 MB
- **Session storage:** 24 hours
- **Cache:** Images cached in browser for 24 hours

---

## Troubleshooting

### "No thumbnail gallery appears"
**Causes:**
- Image rendering failed (non-fatal)
- PDF has encryption
- Very large PDF (>100 pages may timeout)

**Solution:**
- Text analysis still works
- Check error message in logs
- Try smaller PDF

### "Thumbnail shows broken image"
**Causes:**
- Session expired (>24 hours old)
- Image failed to render
- Network error

**Solution:**
- Re-upload PDF to create new session
- Check browser console for errors

### "Keyboard navigation doesn't work"
**Causes:**
- Lightbox not in focus
- Browser security blocked keyboard events

**Solution:**
- Click inside lightbox area first
- Use on-screen arrow buttons

### "Download ZIP is slow"
**Causes:**
- Large plan set (50 pages = ~5 MB)
- Server generating ZIP on-demand

**Expected:**
- 2-5 seconds for 20-page plan
- 5-10 seconds for 50-page plan

---

## Browser Support

**Tested:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Features used:**
- CSS Grid
- Lazy loading (`loading="lazy"`)
- Keyboard events
- Fetch API

**Mobile:**
- iOS Safari 14+
- Chrome Mobile 90+
- Responsive grid layout

---

## Privacy & Security

**Session IDs:**
- Cryptographically secure (secrets.token_urlsafe)
- Non-sequential, non-predictable
- Act as capability tokens (no login needed)

**Data retention:**
- 24 hours maximum
- Auto-deleted by nightly cron
- No long-term storage

**Image data:**
- Stored as base64 TEXT in database
- Not served to unauthorized users
- Session ID required for access

---

## Keyboard Shortcuts Reference

| Key | Action | Context |
|-----|--------|---------|
| ← | Previous page | Lightbox |
| → | Next page | Lightbox |
| Esc | Close | Lightbox |

---

## FAQs

**Q: Can I annotate or markup pages?**
A: Not yet — Phase 4.6 will add annotation tools (pen, highlight, shapes)

**Q: Can I measure distances on plans?**
A: Not yet — Phase 4.6 will add measurement tools

**Q: Can I compare two versions (redline)?**
A: Not yet — Phase 4.6 will add visual diff (red/green overlay)

**Q: How long are sessions saved?**
A: 24 hours, then auto-deleted

**Q: Can I download analysis as PDF?**
A: Not yet — currently PNG images only (PDF export in Phase 4.6)

**Q: What file formats are supported?**
A: PDF only (architectural plan sets)

**Q: Is there a page limit?**
A: Renders first 50 pages (cap to avoid timeouts)

**Q: Can I share sessions with others?**
A: Yes — email includes session link (valid 24h)

---

## Future Features (Phase 4.6)

Coming soon:
- 🖊️ **Annotation tools** — Pen, highlight, shapes, text
- 📏 **Measurement tools** — Distance, area, angle
- 🔄 **Version comparison** — Visual diff (red/green)
- 📄 **PDF export** — Download analysis as PDF report
- ⚙️ **Scale calibration** — Accurate measurements from plans

---

## Support

**Report issues:** `/admin/feedback` (feedback widget in app)

**Questions:** Email support or check documentation

**Logs:** Railway dashboard for admins
