"""Billing gate logic for plan analysis tiers.

Thin plumbing layer — checks subscription tier to determine
whether a user can use specific analysis modes. No payment integration,
no credits system. This is the hook for future billing checks.

Analysis tiers:
  - quick_check: Metadata only, zero API calls. Instant.
  - compliance: Sample pages, title block extraction only.
                 Checks sheet set organization (addresses, sheet numbers,
                 stamps, consistency). ~7 API calls for 12-page PDF.
  - sample:     Sample pages, title blocks + annotations + hatching.
                 Full AI markup with spatial overlay. ~12 API calls.
  - full:       All pages, title blocks + annotations + hatching.
                 Every page analyzed. Same AI pipeline as sample, more pages.

Billing gate is currently DISABLED — all modes are available to all users.
When billing is implemented, re-enable can_use_full_analysis() checks and
add .btn-locked CSS class to gated buttons in the UI.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Analysis mode constants
MODE_COMPLIANCE = "compliance"
MODE_SAMPLE = "sample"
MODE_FULL = "full"

# Subscription tier constants
TIER_FREE = "free"
TIER_PRO = "pro"


def can_use_full_analysis(user: dict | None) -> bool:
    """Check whether a user is allowed to run full-page analysis.

    Currently returns True for all users (billing not yet implemented).
    When billing is enabled, restrict to Pro tier and admins.

    Args:
        user: User dict from auth (may be None for anonymous users).

    Returns:
        True — all users can currently access full analysis.
    """
    # ── Future billing gate (uncomment when Pro tier exists) ──
    # if user is None:
    #     return False
    # admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAIL", "").split(",") if e.strip()]
    # if user.get("email", "").lower() in admin_emails:
    #     return True
    # tier = user.get("subscription_tier", TIER_FREE)
    # return tier == TIER_PRO
    return True


def resolve_analysis_mode(
    user: dict | None,
    requested_mode: str = "sample",
) -> tuple[str, bool]:
    """Determine the actual analysis mode based on user tier and request.

    Args:
        user: User dict from auth (may be None for anonymous).
        requested_mode: One of 'compliance', 'sample', 'full'.

    Returns:
        Tuple of (actual_mode, was_downgraded).
        Currently no downgrading occurs (billing gate disabled).
    """
    if requested_mode == MODE_FULL:
        if can_use_full_analysis(user):
            return MODE_FULL, False
        # Downgrade to sample if billing gate blocks
        logger.info("Downgrading full→sample for user %s (not authorized)", user.get("email") if user else "anonymous")
        return MODE_SAMPLE, True

    if requested_mode == MODE_COMPLIANCE:
        return MODE_COMPLIANCE, False

    return MODE_SAMPLE, False
