# QA Script: Sprint 69 Session 1 — Design System + Landing Rewrite

## Prerequisites
- Flask dev server running on localhost:5001
- Playwright installed (`pip install playwright && playwright install chromium`)

## Steps

### 1. Start Flask test server
- `cd` to project root
- `source .venv/bin/activate && python -c "from web.app import app; app.run(host='127.0.0.1', port=5001, debug=False)" &`
- PASS: Server starts without error

### 2. Landing page loads (desktop 1440px)
- Navigate to `http://127.0.0.1:5001/`
- Viewport: 1440x900
- PASS: HTTP 200, page title contains "sfpermits.ai"
- Screenshot: `qa-results/screenshots/sprint69-s1/landing-desktop.png`

### 3. Landing page loads (tablet 768px)
- Navigate to `http://127.0.0.1:5001/`
- Viewport: 768x1024
- PASS: HTTP 200
- Screenshot: `qa-results/screenshots/sprint69-s1/landing-tablet.png`

### 4. Landing page loads (mobile 375px)
- Navigate to `http://127.0.0.1:5001/`
- Viewport: 375x812
- PASS: HTTP 200
- Screenshot: `qa-results/screenshots/sprint69-s1/landing-mobile.png`

### 5. Search bar exists and is focusable
- Locate `input[name="q"]`
- Click/focus it
- PASS: Input is visible and focusable

### 6. Stats section shows numbers (not empty or undefined)
- Locate `.pulse-stat-number` elements
- PASS: At least 4 elements found, none contain "undefined" or empty text

### 7. Capability cards render (count >= 4)
- Locate `.capability-card` elements
- PASS: At least 4 found

### 8. Google Fonts stylesheet link is present
- Check HTML source for "fonts.googleapis.com" or "design-system.css"
- PASS: Found

### 9. /api/stats returns JSON with permits key
- Navigate to `http://127.0.0.1:5001/api/stats`
- PASS: Response is JSON, contains "permits" key with integer value > 0

### 10. No horizontal scroll at 375px viewport
- At 375px viewport, check document.documentElement.scrollWidth <= window.innerWidth
- PASS: No horizontal overflow

### 11. Authenticated page still works
- Navigate to `/health`
- PASS: HTTP 200, contains "status" or "healthy"

### 12. design-system.css loads
- Navigate to `/static/design-system.css`
- PASS: HTTP 200, contains "--bg-deep"
