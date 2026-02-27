# QA Script — Sprint 75-1: Dashboard + Nav Redesign

**Target:** sfpermits.ai dashboard (authenticated /) and navigation
**Playwright required:** Yes (steps 4-10 involve page rendering)

---

## Setup

- App running at http://localhost:5001 (or staging URL)
- Auth: Sign in with a test account (or admin account)

---

## Steps

### 1. Nav structure — PASS/FAIL
**Check:** HTML source of any authenticated page contains `obs-nav`, `obs-container`, `nav-hamburger`, `nav-mobile-panel`
**Pass:** All 4 classes present in HTML
**Fail:** Any class missing

### 2. Nav desktop badge count — PASS/FAIL
**Check:** At viewport 1440px wide, count visible nav badges in the header row (NOT inside dropdown menus). Should be Search + Brief + Portfolio + Projects + More = 5 badges max.
**Pass:** Visible badges in header row ≤ 6, no wrapping to second line
**Fail:** More than 6 visible badges or badges wrap to second line

### 3. Nav sticky on scroll — PASS/FAIL
**Check:** At 1440px viewport, scroll page down 500px. Nav header stays at top of viewport.
**Pass:** Nav remains visible at top, stuck to viewport
**Fail:** Nav scrolls away with page content

### 4. Nav backdrop blur visible — PASS/FAIL
**Check:** Scroll partially over page content. Nav background should be semi-transparent with blur.
**Pass:** Nav shows blur/frosted glass effect over scrolled content
**Fail:** Nav is solid opaque or invisible

### 5. Mobile hamburger appears at 375px — PASS/FAIL
**Check:** Set viewport to 375px wide. Nav should show logo + hamburger icon only. Badge row hidden.
**Pass:** Hamburger (3 lines) visible, badge row hidden
**Fail:** Hamburger missing or badge row still visible

### 6. Mobile menu slide-down — PASS/FAIL
**Check:** At 375px viewport, tap/click hamburger. A panel should slide down with all nav items stacked vertically.
**Pass:** Panel appears with: Search, Brief, Portfolio, Projects, My Analyses, Permit Prep, Consultants, Bottlenecks, Account, Logout
**Fail:** Panel doesn't appear, or items are missing

### 7. Mobile menu close on tap outside — PASS/FAIL
**Check:** With mobile panel open (step 6), click/tap outside the nav area.
**Pass:** Panel closes
**Fail:** Panel stays open

### 8. Dashboard search card present — PASS/FAIL
**Check:** Authenticated dashboard (/) shows a glass-card containing the search heading and input.
**Pass:** Heading "What do you need to know about SF permits?" visible, search input styled with dark background and cyan focus, Go button present
**Fail:** Search area not in a card or missing styling

### 9. Dashboard quick actions present — PASS/FAIL
**Check:** Below search card, a "Quick Actions" label and buttons: "Analyze a project", "Look up a permit", "Upload plans", "Draft a reply"
**Pass:** All 4 buttons visible in outline-style button row/grid
**Fail:** Any button missing or buttons displayed as plain links

### 10. Dashboard recent searches card — PASS/FAIL
**Check:** A "Recent Searches" card is visible. If no searches: shows placeholder text. If searches exist: shows address + date chips in grid layout.
**Pass:** Card renders with correct content (placeholder or chips)
**Fail:** Card missing or crashes

### 11. Dashboard stats row — PASS/FAIL
**Check:** A stats card at the bottom shows "Permits Watched", "Changes This Week", "1.1M+ SF Permits Indexed", "30 Analysis Tools" with large cyan numbers.
**Pass:** All 4 stat blocks visible with stat-number class
**Fail:** Stats card missing or numbers not styled

### 12. No horizontal overflow at any viewport — PASS/FAIL
**Check:** At 1440px, 768px, and 375px viewports: `document.body.scrollWidth <= window.innerWidth`
**Pass:** True at all 3 viewports (no horizontal scroll)
**Fail:** scrollWidth > innerWidth at any viewport

### 13. Landing page unaffected — PASS/FAIL
**Check:** Visit /logout, then GET / — should see the public landing page with its own header (not nav.html fragment).
**Pass:** Public landing page loads with 200, shows hero section with inline header (no obs-nav class in landing header)
**Fail:** Landing page broken, nav fragment injected, or 500 error

---

## PASS Criteria
Steps 1-13 all PASS

## FAIL escalation
Any FAIL → fix in code, re-run, do not defer
Horizontal overflow → BLOCKED-FIXABLE (must be fixed)
Landing page broken → BLOCKED-FIXABLE (must be fixed)
