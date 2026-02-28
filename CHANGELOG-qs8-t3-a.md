# CHANGELOG — QS8-T3-A: Multi-step Onboarding Wizard + PREMIUM Tier + Feature Flags

**Sprint:** QS8 Terminal 3 Agent A
**Date:** 2026-02-27
**Files owned:**
- `web/routes_auth.py` (modified)
- `web/feature_gate.py` (modified)
- `web/templates/onboarding_step1.html` (NEW)
- `web/templates/onboarding_step2.html` (NEW)
- `web/templates/onboarding_step3.html` (NEW)
- `tests/test_sprint_81_1.py` (NEW)

---

## Added

### Multi-step Onboarding Wizard (Task A-1)

Replaced the single-page welcome card with a 3-step guided onboarding wizard.

**Step 1 — Role Selector** (`/onboarding/step/1`)
- Role choices: homeowner, architect, expediter, contractor
- Card-based selector with radio inputs; selected card highlighted with accent border
- Server-side validation rejects invalid roles with inline error
- Saves role to `users.role` in DB via `UPDATE users SET role = %s`
- Skip link bypasses to step 2 without setting role

**Step 2 — Watch Demo Property** (`/onboarding/step/2`)
- Pre-filled 1455 Market St (Civic Center demo parcel) with mock stats
- "Add to portfolio" action creates a watch item via `add_watch()` (idempotent)
- "Skip" action advances to step 3 without creating watch
- Both paths redirect to step 3

**Step 3 — Morning Brief Preview** (`/onboarding/step/3`)
- Sample brief card showing permit status changes, stall alerts, new filings
- "Go to Dashboard" CTA POSTs to `/onboarding/step/3/complete`
- Complete action: sets `onboarding_complete=TRUE` in DB, clears session banner flag

**Routes added to `web/routes_auth.py`:**
- `GET /onboarding` → alias for step 1
- `GET /onboarding/step/1` — role selector
- `POST /onboarding/step/1/save` — save role, redirect to step 2
- `GET /onboarding/step/2` — demo property watch
- `POST /onboarding/step/2/save` — add watch or skip, redirect to step 3
- `GET /onboarding/step/3` — brief preview
- `POST /onboarding/step/3/complete` — mark complete, redirect to dashboard

**Design:** All 3 templates use Obsidian tokens exclusively:
- `--mono` for data (addresses, permit numbers, step labels, CTAs)
- `--sans` for prose (descriptions, benefit copy, hero text)
- `glass-card` component for property preview and brief preview
- `--accent` (#5eead4) for progress dots, active selections, CTA button fill
- Progress dot indicators (10px circles): active=accent, done=signal-green
- No hardcoded hex values; all color references via CSS custom properties

---

### PREMIUM Tier (Task A-2)

**`web/feature_gate.py` — FeatureTier enum:**
- Added `PREMIUM = "premium"` between `AUTHENTICATED` and `ADMIN`
- `_TIER_ORDER` updated: FREE=0, AUTHENTICATED=1, PREMIUM=2, ADMIN=3

**Beta PREMIUM grant logic (`_is_beta_premium`):**
- Users with `subscription_tier='premium'` in DB → PREMIUM
- Users with invite codes prefixed `sfp-beta-`, `sfp-amy-`, `sfp-team-` → PREMIUM
- Admin check always wins (takes ADMIN tier, not PREMIUM)

**`get_user_tier()` updated** to check `_is_beta_premium()` before falling back to AUTHENTICATED.

**`gate_context()` updated** to include `is_premium` flag:
```python
"is_premium": _TIER_ORDER[tier] >= _TIER_ORDER[FeatureTier.PREMIUM]
```

---

### Feature Flag Expansion (Task A-3)

**5 new entries in `FEATURE_REGISTRY`:**

| Feature | Current Tier | Intent |
|---------|-------------|--------|
| `plan_analysis_full` | AUTHENTICATED | TODO: raise to PREMIUM post-beta |
| `entity_deep_dive` | AUTHENTICATED | TODO: raise to PREMIUM post-beta |
| `export_pdf` | AUTHENTICATED | TODO: raise to PREMIUM post-beta |
| `api_access` | AUTHENTICATED | TODO: raise to PREMIUM post-beta |
| `priority_support` | AUTHENTICATED | TODO: raise to PREMIUM post-beta |

All 5 default to `AUTHENTICATED` during beta so current users see no change. TODO comments mark the transition point for when beta ends.

---

### Tests (23 passing)

**`tests/test_sprint_81_1.py`:**

| Test Class | Tests |
|-----------|-------|
| `TestOnboardingStep1` | 5 tests: renders, auth gate, saves role, rejects invalid role, DB persistence |
| `TestOnboardingStep2` | 3 tests: renders, creates watch item, skip advances without watch |
| `TestOnboardingStep3` | 2 tests: renders with sample brief, complete marks DB |
| `TestPremiumTier` | 9 tests: tier exists, ordering, admin wins, invite prefixes, DB field, gate_context flags |
| `TestFeatureFlags` | 5 tests: all features registered, beta access, anon blocked, can_* flags in context |

---

## Pre-existing failure (not caused by this agent)

- `tests/test_landing.py::TestLandingPage::test_landing_has_feature_cards` — asserts "Permit Search" in landing HTML; landing was rebuilt from mockup in Sprint 69 and this string no longer exists. Pre-dates this sprint's changes.
