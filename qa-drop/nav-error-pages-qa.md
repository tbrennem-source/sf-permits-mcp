# QA Script: Nav Fragment + Error Pages Migration

**Feature:** Migrate nav fragment to token classes; build obsidian error pages (404/500); migrate login_prompt.

**Files changed:**
- `web/templates/fragments/nav.html`
- `web/templates/error.html`
- `web/templates/fragments/login_prompt.html`

---

## 1. Design Token Compliance

- [ ] Run: `python scripts/design_lint.py --files web/templates/fragments/nav.html web/templates/error.html web/templates/fragments/login_prompt.html --quiet`
- **PASS criterion:** Score 5/5, 0 violations
- **Result:** 5/5 (0 violations) ✓

## 2. Nav Fragment — Desktop

1. Visit any authenticated interior page (e.g. `/account`)
2. Verify nav bar is visible and sticky at top of page
3. Verify wordmark "sfpermits.ai" is rendered (mono font, ghost color)
4. Verify nav items (Search, Brief, Portfolio, Projects, More ▾) appear as pill badges
5. Verify "More ▾" dropdown opens on hover, shows: My Analyses, Permit Prep, Consultants, Bottlenecks
6. Verify active page badge has teal accent style
7. Verify Sign in / account / Logout links appear in right section

**PASS:** Nav renders without JS errors, all links present, active state visible

## 3. Nav Fragment — Mobile (375px viewport)

1. Set viewport to 375px wide
2. Verify desktop nav items are hidden
3. Verify hamburger button appears (3-bar icon)
4. Click hamburger — verify mobile panel slides open with all links
5. Click outside nav — verify panel closes
6. Verify wordmark still visible on mobile

**PASS:** Hamburger toggles panel, all mobile links accessible, no layout overflow

## 4. Nav Fragment — Anonymous User

1. Visit landing page or any public page while logged out
2. Verify "Sign in" button appears in nav right section
3. Verify gated items (Brief, Portfolio, Projects) show "Sign up" chip badges
4. Verify "My Analyses" in More dropdown shows "Sign up" chip

**PASS:** Anonymous users see sign-in prompt and upgrade chips on gated nav items

## 5. Error Page — 404

1. Navigate to a non-existent URL (e.g. `/this-does-not-exist`)
2. Verify page has obsidian background (dark)
3. Verify large "404" displayed in mono font, ghost/dim color
4. Verify "Page not found" label in small uppercase mono, teal accent
5. Verify message: "Page not found. Try searching for what you need." in sans body
6. Verify search input is present and functional (searching navigates to search results)
7. Verify "Back to home →" ghost CTA link present, navigates to `/`

**PASS:** 404 page shows all required elements with correct styling

## 6. Error Page — 500

1. Trigger a 500 error (or temporarily render `error.html` with `error_type=None`, `status_code=500`)
2. Verify page shows "500" in large mono font
3. Verify message: "Something went wrong. We're looking into it."
4. Verify search bar and ghost CTA present

**PASS:** 500 page shows generic error state with recovery path

## 7. Error Page — Rate Limit (429)

1. Render error page with `error_type="rate_limit"`
2. Verify "429" code shown
3. Verify "Rate limit reached" label
4. Verify friendly message about waiting
5. Verify search bar present

**PASS:** 429 page variant renders correctly

## 8. login_prompt.html

1. Visit a page that includes the login_prompt fragment (any page with watch button for anonymous user)
2. Verify "Sign in to watch →" renders as a ghost CTA link (underline hover, teal on hover)
3. Verify link navigates to `/auth/login`
4. Verify no surrounding `<span class="login-prompt">` wrapper styling creates visual artifacts

**PASS:** Login prompt renders as clean ghost CTA without legacy span styling

---

## DESIGN TOKEN COMPLIANCE

- [ ] Run: `python scripts/design_lint.py --changed --quiet`
- [ ] Score: 5/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: `--mono` for wordmark/codes/buttons, `--sans` for nav items/body text
- [ ] Nav uses `nav-float`, `nav-float__wordmark`, `nav-float__link` token classes
- [ ] Error page uses `glass-card`, `search-input`, `ghost-cta` token classes
- [ ] login_prompt uses `ghost-cta` token class
- [ ] Interactive text uses `--text-secondary` (not `--text-tertiary`)
