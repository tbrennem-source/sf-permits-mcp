# QA Results: index.html Dashboard Rebuild
# Session: agent-a1dbe24e
# Date: 2026-02-27

## Summary
PASS: 8/8 checks
FAIL: 0
BLOCKED: 1 (pre-existing, not introduced)

---

## Results

### 1. Unauthenticated landing returns 200
PASS — curl confirms 200; Playwright screenshot 01-landing-desktop.png captured

### 2. New user (no watches) sees onboarding card
PASS — Template has `{% if watch_count and watch_count > 0 %}` branch; new users fall into `{% else %}` which renders `.onboard-card` with "Watch your first property." heading; no zero-stats rendered

### 3. User with watches sees brief summary card
PASS — `watch_count > 0` branch renders `.brief-card` with watch count, changes count, urgent count; route now queries `watch_items` and `permit_changes` to populate these values

### 4. Search bar HTMX — confirmed in template
PASS — `hx-post="/ask"`, `hx-target="#search-results"`, `hx-indicator="#search-loading"` present in template; search-btn class on submit button

### 5. Primary address quick-chip
PASS — Template renders `.recent-chip` button when `g.user.primary_street_number` and `g.user.primary_street_name` are set; chip absent when fields not set

### 6. Design token compliance
PASS — `python scripts/design_lint.py --files web/templates/index.html --quiet` → **5/5 (0 violations)**

### 7. Ghost CTAs only (no filled buttons on content area)
PASS — All content-area action links use `.ghost-cta`; `.obsidian-btn-primary` removed from dashboard; `.search-btn` is the sole submit element

### 8. Playwright screenshots captured
PASS — 3 screenshots captured:
- `qa-results/screenshots/index-dashboard-rebuild/01-landing-desktop.png` (48 KB)
- `qa-results/screenshots/index-dashboard-rebuild/02-dashboard-authenticated-desktop.png` (100 KB)
- `qa-results/screenshots/index-dashboard-rebuild/03-landing-mobile.png` (30 KB)

---

## Blocked Items

### BLOCKED-EXTERNAL: test_nav_has_obs_nav_logo failure
- **What failed:** `tests/test_sprint_75_1.py::test_nav_has_obs_nav_logo` — asserts `obs-nav-logo` class in nav.html
- **Classification:** BLOCKED-EXTERNAL — pre-existing issue; `obs-nav-logo` was never added to nav.html
- **Not introduced by this session:** Confirmed via git blame that nav.html was not modified
- **Recommended next step:** Sprint that touches nav.html should add `obs-nav-logo` class or update the test

---

## pytest output (targeted)
```
tests/test_sprint_75_1.py: 21 passed, 1 failed (test_nav_has_obs_nav_logo — pre-existing)
```

---

## Design Token Compliance
- Score: 5/5 (0 violations)
- No inline colors outside DESIGN_TOKENS.md palette
- Font families: --mono for data, --sans for prose
- Components use token classes (glass-card, ghost-cta, obsidian-input)
- No hardcoded hex values
- New components: `.brief-card`, `.onboard-card`, `.search-btn`, `.recent-chip` logged to DESIGN_COMPONENT_LOG.md

---

## Visual QA Checklist (for human spot-check in DeskRelay)
- [ ] 02-dashboard-authenticated-desktop.png: search bar prominent at top, onboarding card below (no zeros)
- [ ] 02-dashboard-authenticated-desktop.png: no filled/primary buttons visible in content area
- [ ] 03-landing-mobile.png: no horizontal overflow at 375px
- [ ] Token compliance: PASS — 5/5 (0 ad-hoc styles)
