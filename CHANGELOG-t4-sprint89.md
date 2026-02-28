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

---

## [Sprint 89-4B] — 2026-02-28

### Added

#### web/routes_property.py (MODIFIED — ~18 lines)
- Portfolio tier gate: free users see upgrade teaser (200 not 403); beta/premium users see full dashboard
- Imports `has_tier` from `web.tier_gate`
- Passes `tier_locked`, `required_tier`, `current_tier` to portfolio.html template

#### web/routes_misc.py (MODIFIED — ~8 lines)
- Brief tier gate: free users get teaser; beta/premium users see full morning brief
- Imports `has_tier` from `web.tier_gate`
- Passes `tier_locked`, `required_tier`, `current_tier` to brief.html template
- Brief header (greeting, date, metadata) always renders for all tiers

#### web/routes_search.py (MODIFIED — ~25 lines)
- AI consultation tier gate on /ask endpoint
- Two check points: (1) modifier/quick-action path, (2) AI synthesis intents (draft_response, general_question)
- Data lookup intents (lookup_permit, search_address, search_complaint, search_parcel, search_person, validate_plans) bypass the gate — no tier check
- Free users get `tier_gate_teaser_inline.html` fragment in the HTMX response area

#### web/templates/portfolio.html (MODIFIED — ~85 lines added)
- Tier gate teaser card CSS classes added to `<style>` block
- Conditional content block: `{% if tier_locked %}` teaser `{% elif properties %}` full content `{% else %}` empty state
- Teaser copy: "Track all your properties in one place" — portfolio value prop
- Returns 200, not 403, so nav/HTMX continue to work

#### web/templates/brief.html (MODIFIED — ~90 lines added)
- Tier gate CSS classes added to `<style>` block
- Conditional content block wraps the full brief body (lookback toggle through content sections)
- Brief header (greeting, date, cache info) always visible for all tiers
- Teaser copy: "Full severity analysis included with Beta" — brief value prop

#### web/templates/fragments/tier_gate_teaser_inline.html (NEW)
- Lightweight HTMX-compatible teaser fragment (no DOCTYPE, no full page)
- Used by /ask to inject teaser into the search results panel
- Same visual design as the full-page tier_gate_teaser.html but as an inlinable fragment
- Mobile-responsive at 375px: full-width CTA, reduced padding

### Tests Added

#### tests/test_tier_gated_content.py (NEW — 14 tests)
- `test_portfolio_requires_login` — anonymous → redirect to /auth
- `test_portfolio_free_user_gets_200_with_teaser` — free user sees teaser (monkeypatched has_tier)
- `test_portfolio_free_user_returns_200_not_403` — HTTP 200 confirmed for HTMX compat
- `test_portfolio_beta_user_sees_full_content` — beta user sees full portfolio
- `test_portfolio_premium_user_sees_full_content` — premium user (>= beta) sees full portfolio
- `test_brief_requires_login` — anonymous → redirect to /auth
- `test_brief_free_user_gets_tier_locked_context` — free user sees teaser + greeting header
- `test_brief_beta_user_gets_full_content` — beta user sees full brief
- `test_brief_premium_user_gets_full_content` — premium user sees full brief
- `test_ask_anonymous_user_handled` — no 500 for anonymous users
- `test_ask_free_user_gets_teaser_response` — free user gets inline teaser for AI question
- `test_ask_free_user_lookup_permit_bypasses_gate` — permit lookup bypasses AI gate
- `test_ask_beta_user_proceeds_to_ai` — beta user gets AI response (not teaser)
- `test_ask_modifier_free_user_gets_teaser` — modifier path also gated for free users

#### tests/test_brief.py (MODIFIED — 10 lines)
- Updated `_login_user` helper to set subscription_tier='beta' (brief is a beta feature)
- Fixes 5 test failures caused by the brief tier gate
- 53 tests continue to pass

### Design Token Compliance
- Score: 5/5 — 0 violations across 3 changed template files
- No inline colors outside DESIGN_TOKENS.md palette
- Font families: --mono for data/badges/labels, --sans for prose headings/descriptions
- New tier gate card components use CSS custom properties exclusively
- New component logged: `tier-gate-inline-card` in fragments/tier_gate_teaser_inline.html
