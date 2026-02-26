# DeskRelay UX Design Review — 2026-02-25

**Sprint:** 59
**Production URL:** https://sfpermits-ai-production.up.railway.app
**Reviewer:** DeskRelay Agent (code + HTTP analysis — Playwright blocked by hook)
**Method:** CSS analysis, HTML structure inspection, WCAG contrast ratio calculation, HTTP verification

---

## Scores

| Page | Layout | Readability | Navigation | Responsiveness | Avg |
|------|--------|-------------|------------|----------------|-----|
| `/` Landing | 4 | 3 | 4 | 4 | 3.75 |
| `/search?q=614+6th+Ave` Results | 3 | 3 | 3 | 3 | 3.0 |
| `/search?q=xyznotreal12345` No-Results | 2 | 3 | 2 | 3 | 2.5 |
| `/auth/login` Login | 4 | 4 | 3 | 4 | 3.75 |
| `/health` Health endpoint | N/A | N/A | N/A | N/A | N/A |

**Overall average (scored pages):** 3.25 / 5.0

---

## Pages Requiring Fix (Score <= 2.0)

### No-Results State — Navigation (Score: 2) and Layout (Score: 2)

**Problem 1 — Contradictory page header:**
`/search?q=xyznotreal12345` renders the heading `"Showing permits for 'xyznotreal12345'"` while simultaneously displaying the message `"Please provide a permit number, address (street number + street name), or parcel (block + lot)."` These two messages directly contradict each other. The heading says results are shown; the body says nothing was understood. A first-time user landing here has no clear path forward.

**Problem 2 — Guidance card does not appear for invalid-format queries:**
The `no_results` template variable is `False` for backend validation errors (queries that fail input parsing), so the search guidance card with example addresses never appears. It only triggers for `"No permits found"` prefix responses. For the most common confused-user scenario (typing a keyword like `"plumbing"` or `"xyznotreal12345"`), the user sees no guidance.

**Problem 3 — Three upsell locked-cards shown for a failed/invalid query:**
Showing "Property Report," "Watch & Get Alerts," and "AI Project Analysis" upsells when the search itself failed adds noise and confusion. These should only appear when the query succeeded and actual permit data was found.

**Action:**
File: `web/app.py` — the `/search` route, and `web/templates/search_results_public.html`
1. Change the results heading for invalid-format queries to "No results" or "Search tips" rather than "Showing permits for..."
2. Extend `no_results` detection to cover backend validation messages: if `result_html` contains `"Please provide"` set `no_results=True` so the guidance card renders
3. Conditionally hide locked-cards when `no_results=True`

---

## Improvement Recommendations (Score 3)

### Landing Page — Readability (3)

**Issue 1 — Hero subtitle line length too short:**
`.hero p` has `max-width: 560px` at `font-size: 1.15rem` (18.4px). At that size, 560px yields approximately 46–54 characters per line — noticeably below the 60–80 character recommended range. The text wraps too frequently, creating a choppy reading rhythm.

**Action:** Increase `.hero p` `max-width` to `680px` to reach approximately 60–65 chars/line.
File: `web/templates/index.html` — `.hero p` CSS rule

**Issue 2 — Sub-12px badge text:**
`.feature-badge` uses `font-size: 0.65rem` (~10.4px). The `.locked-badge` in search results also uses `0.65rem`. At this size on a dark background, these badges are essentially decorative — many users will not be able to read them, particularly on non-retina screens. WCAG 2.1 minimum is 12px for any meaningful text.

**Action:** Increase `.feature-badge` and `.locked-badge` to minimum `0.75rem` (12px).
Files: `web/templates/index.html` and `web/templates/search_results_public.html`

**Issue 3 — White-on-accent CTA button fails WCAG AA for normal text:**
`.header-btn-primary` and all accent-background buttons render white text (`#ffffff`) on `#4f8ff7`. Calculated contrast ratio: **3.18:1**. WCAG AA requires 4.5:1 for normal-weight text at button sizes (~13–16px). This fails. The hover state (`#3a7ae0`) improves to 4.17:1 but still fails AA for normal text.

Note: These are large/bold text scenarios (~13.6px bold) so they pass AA for large text (3:1). However professional-quality standards aim for 4.5:1 on all interactive elements.

**Action:** Either darken the accent color to approximately `#3570d4` (contrast ~5.1:1) or use a darker blue for buttons specifically. Alternatively, use dark text (`#0f1117`) on a lighter accent.
Files: `:root --accent` in each template (no shared global CSS file)

**Issue 4 — Inconsistent 8px spacing grid:**
5 of 17 measured spacing values fall off the 8px grid: header padding (20px), homeowner card `p` margin-bottom (20px), feature section padding (60px), feature card padding (28px), feature card gap (20px). This creates subtle visual rhythm misalignment. 20px is a common alternative grid (4px or 4/8/12/16/20) — if intentional, it should be consistent throughout.

**Action:** Decide on one grid system (8px or 4px) and apply consistently. Convert 60px to 64px, 28px to 24px or 32px.

---

### Search Results — Layout (3) and Navigation (3) and Readability (3)

**Issue 1 — Locked card text lines are extremely wide:**
`.locked-preview p` inside `.locked-card` has no `max-width`. At 1100px container with 24px padding, content spans approximately 1052px. At `font-size: 0.88rem` (14px), this yields ~120–130 characters per line — more than double the recommended maximum of 80. This makes the preview text fatiguing to scan.

**Action:** Add `max-width: 640px` to `.locked-preview` or limit card content width.
File: `web/templates/search_results_public.html`

**Issue 2 — Results heading (0.85rem, muted) is smaller than card H3 (1rem):**
The page-level context label "Showing permits for..." renders at `0.85rem` in muted color, while the individual permit section headers inside cards render at `1rem`. The page label should be at minimum equal to or larger than the items below it. Currently the hierarchy reads backwards.

**Action:** Increase `.results-heading` to `1rem` with `color: var(--text)` (or keep muted but increase size to `0.95rem`).
File: `web/templates/search_results_public.html`

**Issue 3 — Three identical locked-card upsell blocks create visual monotony:**
All three locked cards have the same layout, same badge, same "Sign up free to unlock" CTA. A user skimming the page sees these as visual noise and skips them. The hierarchy between the free result card and the upsell cards is not clear — they use identical `background`, `border`, and `border-radius`.

**Action:** Differentiate locked cards from the free result card visually. Options: use a subtle gradient border for locked cards, or group all three upsells under one section header rather than three separate cards.

**Issue 4 — Result card table has no mobile overflow protection:**
`.result-card table` in `search_results_public.html` has no `overflow-x: auto` wrapper. `mobile.css` has `.search-result-card` overflow rules, but the template uses class `.result-card` — the mobile CSS rule does not apply. On 375px viewports, the label column (140px fixed) plus content column will overflow.

**Action:** Add `overflow-x: auto; -webkit-overflow-scrolling: touch;` to `.result-card` in `search_results_public.html` mobile breakpoint, or rename to `.search-result-card` to match the existing `mobile.css` rule.
File: `web/templates/search_results_public.html` (add mobile breakpoint) or `web/static/mobile.css` (extend rule to `.result-card`)

---

### Login Page — Navigation (3)

**Issue 1 — "Back to search" link is easy to miss:**
The back link (`← Back to search`) is `0.85rem`, `color: var(--text-muted)` — small and low-contrast relative to other elements on the page. For a user who lands here accidentally (e.g., from a search result upsell click), the escape path is not visually obvious.

**Action:** Either place a minimal header with the logo linking home (same as other pages), or increase the back-link prominence: `font-size: 0.9rem` and `color: var(--accent)`.
File: `web/templates/auth_login.html`

**Issue 2 — Logo (1.4rem) and H2 "Sign in" (1.2rem) too close in size:**
The logo at `1.4rem` and the `h2` at `1.2rem` are only 2px apart in rendered size. On the compact login card these compete visually. The logo reads as an H1-level element but the H2 immediately below it is nearly the same size.

**Action:** Either reduce H2 to `1rem` (keeping it clearly subordinate) or increase the logo to `1.6rem` to create clear separation.
File: `web/templates/auth_login.html`

---

### Cross-Page Accessibility — Focus States

**Issue (affects all pages):**
Button elements (`.btn`, `.header-btn`, `.search-form button`, `.locked-cta a`, `.violation-cta`) and link elements have no explicit `:focus` or `:focus-visible` CSS. Browser default outlines apply. On the dark background (`#0f1117`), the default browser focus ring (typically a 2px blue outline) may have insufficient contrast for WCAG 2.1 Success Criterion 2.4.11 (Focus Appearance, AA).

Input elements correctly override `outline: none` and substitute `border-color: var(--accent)` — but this pattern was not extended to interactive buttons and links.

**Action:** Add to each template's `<style>` block (or consolidate in `mobile.css`):
```css
:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
```
This uses the modern `:focus-visible` selector (keyboard-only focus, not mouse click), preserving visual cleanliness while restoring keyboard accessibility.
Files: `web/static/mobile.css` (global) or individual template `<style>` blocks

---

## Auth-Protected Pages (Not Reviewed)

The following pages require authentication and could not be assessed in this pass:

- `/brief` — Morning Brief
- `/portfolio` — Portfolio dashboard
- `/account` — Account settings
- `/admin/ops` — Admin operations (pipeline, quality, activity, feedback, sources, regulatory)
- `/admin/qa` — QA replays
- `/account/analyses` — My Analyses

These should be reviewed in a logged-in DeskRelay pass or via recorded session screenshots.

---

## Health Endpoint

`GET /health` returns valid JSON: `status: ok`, `backend: postgres`, 54 tables confirmed. Response is raw JSON (no HTML styling) — functional and correct for a status endpoint. No design concerns for this endpoint.

---

## Next Sprint Design Tasks

| Priority | Task | File | Impact |
|----------|------|------|--------|
| P1 | Fix no-results state: change heading + show guidance card for validation errors | `web/app.py`, `web/templates/search_results_public.html` | UX confusing |
| P1 | Hide locked-card upsells when no real search result to upsell from | `web/templates/search_results_public.html` | UX confusing |
| P2 | Add `overflow-x: auto` to `.result-card` table on mobile | `web/static/mobile.css` or `search_results_public.html` | Mobile broken |
| P2 | Add `:focus-visible` outline to all buttons and links | `web/static/mobile.css` | Accessibility |
| P2 | Increase `.feature-badge` and `.locked-badge` font-size from 0.65rem to 0.75rem | `index.html`, `search_results_public.html` | Readability |
| P3 | Increase `.hero p` max-width from 560px to 680px | `web/templates/index.html` | Typography |
| P3 | Improve "Back to search" link visibility on login page | `web/templates/auth_login.html` | Navigation |
| P3 | Differentiate locked-card upsells visually from free result card | `web/templates/search_results_public.html` | Visual hierarchy |
| P3 | Increase `.results-heading` size to 0.95rem or 1rem | `web/templates/search_results_public.html` | Hierarchy |
| P4 | Consider darkening accent color for AA compliance on CTA buttons | All templates | Accessibility |
| P4 | Standardize spacing to 8px or 4px grid consistently | All templates | Polish |

---

## Screenshots

Note: Playwright execution was blocked by the `block-playwright.sh` PreToolUse hook in this session. Screenshots could not be captured. Design analysis was performed via:
- Full HTML/CSS source extraction from production URLs
- WCAG contrast ratio calculations against the CSS color palette
- HTTP structure analysis
- Code review of all relevant templates

Screenshots directory: `qa-results/screenshots/sprint59-ux/` (empty — needs separate Playwright session with `CLAUDE_SUBAGENT=true` set in the agent's environment, not inline in the command)

---

## Issues Requiring Fix (Score <= 2)

| Page | Dimension | Score | Issue |
|------|-----------|-------|-------|
| No-Results `/search?q=xyznotreal12345` | Navigation | 2 | Contradictory heading + missing guidance card |
| No-Results `/search?q=xyznotreal12345` | Layout | 2 | Upsell cards shown for failed queries |
