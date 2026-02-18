"""Billing gate logic for plan analysis tiers.

Thin plumbing layer — checks subscription tier to determine
whether a user can use full-page analysis. No payment integration,
no credits system. This is the hook for future billing checks.
"""

import logging

logger = logging.getLogger(__name__)

# Analysis mode constants
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


def resolve_analysis_mode(user: dict | None, requested_all_pages: bool) -> str:
    """Determine the actual analysis mode based on user tier and request.

    Args:
        user: User dict from auth (may be None for anonymous).
        requested_all_pages: Whether the user requested full-page analysis.

    Returns:
        'full' if the user requested all pages AND has Pro tier.
        'sample' otherwise.
    """
    if requested_all_pages and can_use_full_analysis(user):
        return MODE_FULL
    return MODE_SAMPLE
