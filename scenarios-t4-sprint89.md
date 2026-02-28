# Sprint 89-4A — Suggested Scenarios

## SUGGESTED SCENARIO: New beta user clicks invite link and completes 3-step onboarding
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** homeowner
**Starting state:** User has a valid beta invite link (/beta/join?code=xxx). User is unauthenticated.
**Goal:** Complete beta onboarding from invite link to dashboard
**Expected outcome:** User is redirected to login with code preserved, logs in, tier is upgraded to beta, is walked through 3-step onboarding (welcome → add property → severity preview), lands on dashboard with onboarding marked complete
**Edge cases seen in code:** Code is preserved as query param through login redirect; if INVITE_CODES is empty (open signup) validate_invite_code returns True for any code
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user encounters tier gate teaser on gated feature
**Source:** Sprint 89 — @requires_tier decorator
**User:** homeowner
**Starting state:** User is authenticated with subscription_tier = 'free'. They navigate to a route decorated with @requires_tier('beta').
**Goal:** Access a beta-gated feature
**Expected outcome:** User sees a 403 page with a glass-card teaser explaining the beta feature benefit and a CTA to join beta. Current plan is shown as "free". No raw error page — a properly branded upgrade prompt.
**Edge cases seen in code:** has_tier() treats None, missing, or unknown tier values as free (level 0); tier hierarchy means premium users automatically pass beta checks
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Already-beta user clicks invite link again — no double upgrade
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** expediter
**Starting state:** User is authenticated with subscription_tier = 'beta'. They receive a second invite link and click it.
**Goal:** Click a beta invite link they already used
**Expected outcome:** User is immediately redirected to dashboard (/). No tier modification, no error. No second round of onboarding is triggered.
**Edge cases seen in code:** Route checks current_tier in ("beta", "premium") before calling execute_write; premium users also skip the upgrade
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Unauthenticated user hits /beta/join — redirected to login with code preserved
**Source:** Sprint 89 — Beta Onboarding Flow
**User:** homeowner
**Starting state:** User is not logged in. They click a beta invite link with a valid code.
**Goal:** Start beta onboarding without being logged in
**Expected outcome:** Redirected to /auth/login with invite_code and referral_source=beta_invite as query parameters. After login, the invite link can be re-visited to complete the tier upgrade.
**Edge cases seen in code:** The redirect preserves the code via query string concatenation; the login page already handles invite_code form field for pre-filling
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Premium user accessing beta-gated feature passes tier check
**Source:** Sprint 89 — @requires_tier decorator + tier hierarchy
**User:** expediter
**Starting state:** User has subscription_tier = 'premium'. They access a route decorated with @requires_tier('beta').
**Goal:** Access a feature that requires beta tier
**Expected outcome:** Full content is rendered (not the teaser). Tier hierarchy means premium >= beta, so premium users always pass beta checks.
**Edge cases seen in code:** _TIER_LEVELS dict uses numeric ordering; _user_tier_level() defaults unknown tiers to 0; the check is >= not ==
**CC confidence:** high
**Status:** PENDING REVIEW

---

# Sprint 89-4B — Suggested Scenarios (Agent 4B)

## SUGGESTED SCENARIO: Free user hits portfolio tier gate
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** homeowner
**Starting state:** User has free tier account, clicks Portfolio in nav
**Goal:** View their property portfolio
**Expected outcome:** Sees portfolio page with upgrade teaser — clear value prop,
  CTA to upgrade to beta, not a hard 403 error. The page returns 200 so HTMX
  and nav continue to work correctly.
**Edge cases seen in code:** tier_locked=True still returns 200 so HTMX works correctly;
  empty properties/summary dicts passed to avoid template errors in teaser mode
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user sees morning brief header but body is gated
**Source:** Sprint 89 — Brief Tier Gate
**User:** homeowner
**Starting state:** Free tier account, navigates to /brief
**Goal:** View their morning brief
**Expected outcome:** Sees the brief page with the morning greeting ("Good morning..."),
  but the property data sections are replaced by a beta upgrade teaser with clear
  value proposition (full severity analysis, AI risk assessment). Not a 403.
**Edge cases seen in code:** Brief header is always rendered; teaser replaces the
  content body between the header and freshness footer
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Free user asks a question, sees AI teaser in search results
**Source:** Sprint 89 — AI Consultation Tier Gate
**User:** homeowner
**Starting state:** Free tier, types a general question in the /ask search box
**Goal:** Get AI analysis of their permit situation
**Expected outcome:** Sees teaser card in search results panel explaining the beta
  AI feature, with upgrade CTA. Not a blank response, not an error, not a redirect.
  Data lookups (permit number, address search) still work without gating.
**Edge cases seen in code:** AI synthesis intents (draft_response, general_question)
  are gated; data lookup intents (lookup_permit, search_address, search_complaint,
  search_parcel, search_person, validate_plans) bypass the gate entirely
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Beta user sees full AI consultation
**Source:** Sprint 89 — Tier-Gated Content Application
**User:** expediter
**Starting state:** Beta tier account
**Goal:** Get AI analysis via /ask
**Expected outcome:** Full AI response (draft_response template) — no teaser, no tier gate.
  Modifier quick-actions (shorter, cite_sources, get_meeting) also work without gating.
**Edge cases seen in code:** has_tier(user, 'beta') returns True for both beta and
  premium users; modifier path also checks tier before calling _ask_draft_response
**CC confidence:** high
**Status:** PENDING REVIEW
