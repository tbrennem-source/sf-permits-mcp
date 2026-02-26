"""Feature gating for sfpermits.ai.

Controls which features are visible/accessible based on user authentication.
Three tiers: FREE (anyone), AUTHENTICATED (logged in), ADMIN (admin users).

Usage in templates:
    {% if gate.can_analyze %}  ...  {% endif %}
    {% if gate.tier == 'admin' %}  ...  {% endif %}
"""
from __future__ import annotations

from enum import Enum


class FeatureTier(str, Enum):
    FREE = "free"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"
    # PREMIUM = "premium"  # reserved for paid tier


# Feature registry: feature_name -> minimum tier required
FEATURE_REGISTRY = {
    # Free features (anyone can access)
    "search": FeatureTier.FREE,
    "landing": FeatureTier.FREE,
    "public_search": FeatureTier.FREE,

    # Authenticated features (must be logged in)
    "analyze": FeatureTier.AUTHENTICATED,
    "plans": FeatureTier.AUTHENTICATED,
    "brief": FeatureTier.AUTHENTICATED,
    "portfolio": FeatureTier.AUTHENTICATED,
    "watch": FeatureTier.AUTHENTICATED,
    "projects": FeatureTier.AUTHENTICATED,
    "analyses": FeatureTier.AUTHENTICATED,
    "ask": FeatureTier.AUTHENTICATED,

    # Admin features
    "admin_ops": FeatureTier.ADMIN,
    "admin_qa": FeatureTier.ADMIN,
    "admin_costs": FeatureTier.ADMIN,
}

# Tier hierarchy for comparison
_TIER_ORDER = {
    FeatureTier.FREE: 0,
    FeatureTier.AUTHENTICATED: 1,
    FeatureTier.ADMIN: 2,
}


def get_user_tier(user: dict | None) -> FeatureTier:
    """Determine a user's feature tier."""
    if user is None:
        return FeatureTier.FREE
    if user.get("is_admin"):
        return FeatureTier.ADMIN
    return FeatureTier.AUTHENTICATED


def can_access(feature: str, user: dict | None) -> bool:
    """Check if a user can access a feature."""
    required = FEATURE_REGISTRY.get(feature, FeatureTier.AUTHENTICATED)
    user_tier = get_user_tier(user)
    return _TIER_ORDER[user_tier] >= _TIER_ORDER[required]


def gate_context(user: dict | None) -> dict:
    """Build template context dict for feature gating.

    Returns a dict with:
      - tier: current user's tier string
      - can_search, can_analyze, can_brief, etc.: boolean flags
      - is_authenticated: bool
      - is_admin: bool
    """
    tier = get_user_tier(user)
    ctx = {
        "tier": tier.value,
        "is_authenticated": tier != FeatureTier.FREE,
        "is_admin": tier == FeatureTier.ADMIN,
    }
    # Add can_* flags for each feature
    for feature in FEATURE_REGISTRY:
        ctx[f"can_{feature}"] = can_access(feature, user)
    return ctx
