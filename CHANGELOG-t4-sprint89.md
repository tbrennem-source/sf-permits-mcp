# CHANGELOG — Sprint 89-4A (Agent 4A)

## [Sprint 89-4A] — 2026-02-28

### Added

#### web/tier_gate.py (NEW)
- `has_tier(user, required_tier)` — utility function for tier hierarchy checks (free < beta < premium)
- `requires_tier(required_tier)` decorator — gates Flask routes behind subscription tiers
  - Anonymous users → redirect to /auth/login
  - Free users (below required tier) → renders `fragments/tier_gate_teaser.html` with 403
  - Beta/Premium users (meets required tier) → renders full content (calls wrapped function)
  - Preserves function `__name__` via `functools.wraps`

#### web/routes_auth.py (APPENDED — ~60 lines)
- `GET /beta/join?code=<invite_code>` — validates invite code, upgrades tier, routes to onboarding
- `GET /beta/onboarding/welcome` — step 1 welcome page (login_required)
- `GET /beta/onboarding/add-property` — step 2 property watch form (login_required)
- `GET /beta/onboarding/severity-preview` — step 3 signal category preview (login_required)

#### web/templates/onboarding/welcome.html (NEW)
- Beta welcome page with 3-step progress indicator (step 1 active)
- Error state for invalid/expired invite codes
- Design tokens: glass-card, --sans font, ghost-cta, obsidian background

#### web/templates/onboarding/add_property.html (NEW)
- Address form to add first property watch (POST to /watch/add)
- HTMX-powered submission with redirect to severity-preview on success
- Progress indicator (step 2 active)
- Design tokens: glass-card, --mono for inputs

#### web/templates/onboarding/severity_preview.html (NEW)
- 3-card grid: Inspection History, Complaint Patterns, Permit Status
- Example data rows using obs-table-style data values
- Marks onboarding complete via existing /onboarding/dismiss endpoint
- Progress indicator (step 3 active)

#### web/templates/fragments/tier_gate_teaser.html (NEW)
- Self-contained full-page fragment returned directly from @requires_tier decorator
- Glass-card with backdrop-filter blur, beta/premium badge
- Conditional CTA: /beta/join for beta gate, /auth/login for premium gate
- Mobile-responsive at 375px: stacked layout, full-width CTA
- Shows current plan to authenticated users

### Tests Added

#### tests/test_onboarding_flow.py (NEW — 13 tests)
- `test_beta_join_invalid_code_returns_400`
- `test_beta_join_missing_code_returns_400`
- `test_beta_join_unauthenticated_redirects_to_login`
- `test_beta_join_valid_code_upgrades_tier`
- `test_beta_join_already_beta_redirects_to_dashboard`
- `test_beta_join_already_premium_redirects_to_dashboard`
- `test_beta_onboarding_welcome_requires_auth`
- `test_beta_onboarding_add_property_requires_auth`
- `test_beta_onboarding_severity_preview_requires_auth`
- `test_beta_onboarding_welcome_renders`
- `test_beta_onboarding_add_property_renders`
- `test_beta_onboarding_severity_preview_renders`

#### tests/test_tier_gate.py (NEW — 14 tests)
- `test_has_tier_free_user_fails_beta_check`
- `test_has_tier_free_user_fails_premium_check`
- `test_has_tier_beta_user_passes_beta_check`
- `test_has_tier_beta_user_fails_premium_check`
- `test_has_tier_premium_user_passes_beta_check`
- `test_has_tier_premium_user_passes_premium_check`
- `test_has_tier_missing_tier_field_treated_as_free`
- `test_has_tier_none_tier_treated_as_free`
- `test_has_tier_unknown_tier_treated_as_free`
- `test_requires_tier_anonymous_redirects_to_login`
- `test_requires_tier_free_user_gets_403_teaser`
- `test_requires_tier_beta_user_sees_content`
- `test_requires_tier_premium_user_sees_beta_content`
- `test_requires_tier_decorator_preserves_function_name`

### Design Token Compliance
- Score: 5/5 — 0 violations across 4 changed template files
- No inline colors outside DESIGN_TOKENS.md palette
- Font families: --mono for data/labels, --sans for prose (correct)
- All components use token classes and CSS custom properties
