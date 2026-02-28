# Scenarios — QS8-T3-A: Multi-step Onboarding + PREMIUM Tier + Feature Flags

## SUGGESTED SCENARIO: homeowner completes 3-step onboarding wizard

**Source:** web/routes_auth.py, web/templates/onboarding_step1.html
**User:** homeowner
**Starting state:** New user just verified their magic link for the first time; no role set, no watches, onboarding_complete=False
**Goal:** Complete the onboarding flow to get oriented with the product
**Expected outcome:** Role saved to profile, demo property added to portfolio, onboarding_complete=True, user lands on dashboard
**Edge cases seen in code:** User can skip step 2 (no watch created); all roles validated server-side; re-running onboarding via ?redo=1 is supported
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: expediter skips role selection and still advances

**Source:** web/routes_auth.py (onboarding_step1 has skip link to step 2)
**User:** expediter
**Starting state:** User is on step 1 of onboarding
**Goal:** Skip role selection and go directly to step 2 without choosing a role
**Expected outcome:** User proceeds to step 2 (watch property) without error; role remains unset in DB; no data loss
**Edge cases seen in code:** Skip link bypasses POST entirely — no validation happens; role stays NULL in DB
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: user adds demo property in step 2 and sees it in portfolio

**Source:** web/routes_auth.py (onboarding_step2_save), web/auth.py (add_watch)
**User:** homeowner
**Starting state:** User is on step 2 of onboarding; no watch items exist
**Goal:** Click "Add to portfolio" for 1455 Market St
**Expected outcome:** Watch item created for 1455 Market St (type=address); user advances to step 3; property appears in portfolio/account page
**Edge cases seen in code:** add_watch is idempotent — clicking twice doesn't duplicate the watch; add_watch failure is non-fatal (redirects anyway)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: beta user automatically gets PREMIUM tier access

**Source:** web/feature_gate.py (get_user_tier, _is_beta_premium)
**User:** expediter (beta invite code holder)
**Starting state:** User created account with invite code starting with "sfp-beta-" or "sfp-amy-" or "sfp-team-"
**Goal:** Access premium-gated features (plan_analysis_full, entity_deep_dive, etc.)
**Expected outcome:** gate_context() returns is_premium=True; can_plan_analysis_full=True; no paywall shown; seamless experience identical to paid users
**Edge cases seen in code:** is_admin check comes before PREMIUM check — admin tier always wins; subscription_tier='premium' in DB also grants PREMIUM regardless of invite code
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: feature flags default open during beta; all authenticated users access premium features

**Source:** web/feature_gate.py (FEATURE_REGISTRY TODO comments)
**User:** homeowner
**Starting state:** Regular authenticated user with no special invite code; subscription_tier='free'
**Goal:** Access plan_analysis_full, entity_deep_dive, export_pdf, api_access, priority_support
**Expected outcome:** All 5 features accessible during beta period (FEATURE_REGISTRY defaults to AUTHENTICATED); no upgrade prompt; TODO comments in code mark the transition point
**Edge cases seen in code:** When beta ends, raising tier to PREMIUM will gate these for non-premium users; this is a deliberate gradual reveal pattern
**CC confidence:** high
**Status:** PENDING REVIEW
