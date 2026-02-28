## SUGGESTED SCENARIO: New user skips onboarding from step 1

**Source:** onboarding_step1.html, web/routes_auth.py onboarding_skip route
**User:** homeowner
**Starting state:** User has just verified their email and landed on onboarding step 1
**Goal:** Skip the entire setup and go straight to the dashboard
**Expected outcome:** User is redirected to the dashboard immediately; flash message "Welcome to sfpermits.ai!" is displayed; no role is saved; user can still use the app normally
**Edge cases seen in code:** onboarding_dismissed flag is set in session; show_onboarding_banner is cleared; onboarding_complete is NOT persisted to DB (skip does not mark complete)
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user selects role on step 1 and advances

**Source:** onboarding_step1.html, web/routes_auth.py onboarding_step1_save
**User:** expediter
**Starting state:** User is on step 1 of onboarding; no role has been saved yet
**Goal:** Select "Expediter" role and continue to step 2
**Expected outcome:** Role is persisted to the users table; user's session g.user reflects the new role; user is redirected to step 2 with progress indicator showing step 1 as "done" (green dot)
**Edge cases seen in code:** Submitting with no role selected returns an error message; role must be one of homeowner/architect/expediter/contractor
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user enters custom address on step 2

**Source:** onboarding_step2.html, web/routes_auth.py onboarding_step2_save
**User:** homeowner
**Starting state:** User is on step 2 with an address input field visible
**Goal:** Type their own address (e.g., "487 Noe St") into the input and add it to their portfolio
**Expected outcome:** The address is saved as a watch item; user advances to step 3; demo property (1455 Market St) was NOT automatically added
**Edge cases seen in code:** address field is accepted as-is; no validation or geocoding happens on the form submission itself
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user uses demo property on step 2

**Source:** onboarding_step2.html, web/routes_auth.py onboarding_step2_save (action=skip)
**User:** architect
**Starting state:** User is on step 2; they don't have a specific SF property to watch yet
**Goal:** Use the demo property (1455 Market St) to proceed through onboarding
**Expected outcome:** 1455 Market St is added to their portfolio as a watch item (label "Demo — 1455 Market St"); user advances to step 3; add_watch failure is non-fatal (may already exist)
**Edge cases seen in code:** Non-fatal exception handling if watch already exists
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: New user completes onboarding on step 3

**Source:** onboarding_step3.html, web/routes_auth.py onboarding_complete
**User:** homeowner
**Starting state:** User is on step 3 (final step); they have watched at least one property
**Goal:** Click "Go to Dashboard →" to complete onboarding
**Expected outcome:** onboarding_complete flag is set to TRUE in the users table; session onboarding_dismissed = True; flash message "Welcome to sfpermits.ai!" appears on dashboard; user will not be shown the onboarding wizard again on future logins
**Edge cases seen in code:** DB update failure is logged but non-fatal; user still gets redirected to dashboard
**CC confidence:** high
**Status:** PENDING REVIEW
