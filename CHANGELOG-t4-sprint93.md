# CHANGELOG — T4 Sprint 93 (QS11): Onboarding Wizard Polish

## [Sprint 93] — 2026-02-28

### Added

- `web/routes_auth.py`: `onboarding_skip` route — skips entire wizard, flashes "Welcome to sfpermits.ai!", redirects to dashboard
- `web/routes_auth.py`: `flash` added to Flask imports
- `web/routes_auth.py`: `onboarding_complete` now emits flash message "Welcome to sfpermits.ai!" on completion
- `web/templates/onboarding_step1.html`: Personalized welcome heading that uses user's first name from `user.get('name')`
- `web/templates/onboarding_step1.html`: Visual progress dots (1/3) with `step--active` and `step--done` CSS states
- `web/templates/onboarding_step1.html`: CSS checkmark indicator (`::after` pseudo-element) on selected role card
- `web/templates/onboarding_step1.html`: Icon scale animation on role card hover
- `web/templates/onboarding_step1.html`: "Skip setup →" now routes to `onboarding_skip` (dashboard) instead of step 2
- `web/templates/onboarding_step2.html`: Address text input with placeholder "e.g., 487 Noe St" and `--mono` styling matching search-input pattern
- `web/templates/onboarding_step2.html`: "This is where the magic happens." tagline in accent teal
- `web/templates/onboarding_step2.html`: Demo property (1455 Market St) repositioned as a suggestion below the input, with "Or try the demo property" label
- `web/templates/onboarding_step2.html`: CTA updated to "Find my property →"
- `web/templates/onboarding_step2.html`: Skip changed to "Use demo property →" (uses 1455 Market St demo data)
- `web/templates/onboarding_step3.html`: CSS-only ring-pulse celebration animation (no JS, no library) on step 3 load
- `web/templates/onboarding_step3.html`: Nightly update highlight banner — "This updates every night with new city data — no action needed on your part."
- `web/templates/onboarding_step3.html`: Fade-in animation on hero and brief card content
- `tests/test_onboarding_polish.py`: 21 tests (19 passing, 2 skipped integration) covering all 3 templates + routes

### Design Compliance

- Design lint score: **5/5** on all 3 onboarding templates (0 violations)
- All colors from `--obsidian`, `--accent`, `--signal-green`, `--dot-green`, `--text-*` token palette
- Fonts: `--mono` for data/CTAs/inputs, `--sans` for prose/headings per role assignment table
- No inline non-token hex values
