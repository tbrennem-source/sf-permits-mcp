"""Billing gate logic for plan analysis tiers.

Thin plumbing layer — checks subscription tier to determine
whether a user can use full-page analysis. No payment integration,
no credits system. This is the hook for future billing checks.

Analysis tiers:
  - quick_check: Metadata only, zero API calls. Instant.
  - compliance: Sample pages, title block extraction only.
                 Checks sheet set organization (addresses, sheet numbers,
                 stamps, consistency). ~7 API calls for 12-page PDF.
  - sample:     Sample pages, title blocks + annotations + hatching.
                 Full AI markup with spatial overlay. ~12 API calls.
  - full:       All pages (Pro tier), title blocks + annotations + hatching.
                 Every page analyzed. Pro subscription required.
"""

import logging

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

    Args:
        user: User dict from auth (may be None for anonymous users).

    Returns:
        True if the user has a 'pro' subscription tier.
        Anonymous users and 'free' tier users get False.
    """
    if user is None:
        return False
    tier = user.get("subscription_tier", TIER_FREE)
    return tier == TIER_PRO


def resolve_analysis_mode(
    user: dict | None,
    requested_mode: str = "sample",
) -> str:
    """Determine the actual analysis mode based on user tier and request.

    Args:
        user: User dict from auth (may be None for anonymous).
        requested_mode: One of 'compliance', 'sample', 'full'.

    Returns:
        The requested mode if allowed, or a downgraded mode if not.
        'full' requires Pro tier; others are available to all users.
    """
    if requested_mode == MODE_FULL:
        if can_use_full_analysis(user):
            return MODE_FULL
        # Downgrade to sample if not Pro
        return MODE_SAMPLE

    if requested_mode == MODE_COMPLIANCE:
        return MODE_COMPLIANCE

    return MODE_SAMPLE
