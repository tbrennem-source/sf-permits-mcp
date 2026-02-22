# Scenarios Pending Review
<!-- CC appends suggested scenarios here after each feature session -->
<!-- Do not edit scenario-design-guide.md directly -->
<!-- This file is reviewed and drained each planning session -->

_Last reviewed: never_

---

## SUGGESTED SCENARIO: Admin Ops tab timeout recovery
**Source:** Session 38f — Admin Ops infinite spinner fix
**User:** admin
**Starting state:** Logged in as admin, database under heavy load or slow
**Goal:** View any Admin Ops tab and get either content or a clear error within 30 seconds
**Expected outcome:** Tab loads data OR shows "loading slowly" / "timed out" fallback with retry link. Never shows infinite spinner past 30s. Clicking "Reload page" link in error state recovers.
**Edge cases seen in code:** Server-side SIGALRM (25s) fires before client-side HTMX timeout (30s) — both paths must produce a user-visible message, not a blank or stuck state. Race between the two timeouts should not produce duplicate error messages.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Admin Ops tab switching under load
**Source:** Session 38f — rapid tab switching QA
**User:** admin
**Starting state:** Logged in as admin, on `/admin/ops`, one tab currently loading
**Goal:** Switch to a different tab before the first tab finishes loading
**Expected outcome:** Previous request is superseded by the new tab request. New tab loads or times out gracefully. No orphaned spinner from the canceled tab. Active state (blue highlight) tracks the most-recently-clicked tab.
**Edge cases seen in code:** HTMX doesn't auto-cancel in-flight requests by default. If both responses arrive, the last-clicked tab's content should win. The `loading` CSS class must be removed from the abandoned tab button.
**CC confidence:** medium
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity scoring preserves hold signal through post-processing
**Source:** Session 38f — 532 Sutter hold bug
**User:** expediter
**Starting state:** Property has ≥5 active permits, 1 expired permit, AND an active hold at a routing station
**Goal:** Morning brief correctly shows AT RISK for the hold, not ON TRACK from expired-permit downgrade
**Expected outcome:** Property card shows AT RISK (red) with "Hold at [station]" reason. The expired permit's automatic downgrade logic does NOT fire because holds are a real action signal.
**Edge cases seen in code:** Hold upgrade runs AFTER per-permit scoring but BEFORE post-processing. If the per-permit worst_health is already `at_risk` from expiration, the hold must still overwrite the reason text so post-processing doesn't match "permit expired". Properties with both holds AND enforcement should show whichever was set last (enforcement check runs after hold check).
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Hash routing aliases for Admin Ops
**Source:** Session 38f — hash mapping fix
**User:** admin
**Starting state:** Not on Admin Ops page
**Goal:** Navigate directly to a specific tab via URL hash
**Expected outcome:** `/admin/ops#luck` opens LUCK Sources, `#dq` opens Data Quality, `#watch` opens Regulatory Watch, `#pipeline` opens Pipeline Health. Unknown hashes fall back to Data Quality.
**Edge cases seen in code:** Hash aliases map friendly names to data-tab values (`luck→sources`). If someone bookmarks a tab with the canonical hash (`#sources`), it should also work. Empty hash defaults to `quality`.
**CC confidence:** high
**Status:** PENDING REVIEW

---

## SUGGESTED SCENARIO: Severity not downgraded when property has open enforcement
**Source:** Session 38f — enforcement guard in post-processing
**User:** expediter
**Starting state:** Property has expired permit + open violations/complaints + multiple active permits
**Goal:** Morning brief shows AT RISK for the enforcement, not downgraded to ON TRACK
**Expected outcome:** Property card shows AT RISK (red) with "Open enforcement: X violations" reason. Post-processing skips this property because `has_enforcement` flag is True.
**Edge cases seen in code:** Enforcement check runs after hold check in the per-property loop. If both hold and enforcement exist, enforcement overwrites the hold reason. Post-processing guards check both `has_holds` and `has_enforcement` independently.
**CC confidence:** medium
**Status:** PENDING REVIEW
