"""Feature gating for sfpermits.ai.

Controls which features are visible/accessible based on user authentication.
Four tiers: FREE (anyone), AUTHENTICATED (logged in), PREMIUM (paid/beta),
ADMIN (admin users).

Usage in templates:
    {% if gate.can_analyze %}  ...  {% endif %}
    {% if gate.tier == 'admin' %}  ...  {% endif %}
    {% if gate.is_premium %}  ...  {% endif %}
"""
from __future__ import annotations

from enum import Enum


class FeatureTier(str, Enum):
    FREE = "free"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"   # Paid tier — beta users get this free
    ADMIN = "admin"


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

    # Premium features — gated behind PREMIUM tier.
    # NOTE: All defaulted to AUTHENTICATED during beta so everyone gets access.
    # Raise to PREMIUM when beta period ends.
    "plan_analysis_full": FeatureTier.AUTHENTICATED,   # TODO: raise to PREMIUM post-beta
    "entity_deep_dive": FeatureTier.AUTHENTICATED,     # TODO: raise to PREMIUM post-beta
    "export_pdf": FeatureTier.AUTHENTICATED,           # TODO: raise to PREMIUM post-beta
    "api_access": FeatureTier.AUTHENTICATED,           # TODO: raise to PREMIUM post-beta
    "priority_support": FeatureTier.AUTHENTICATED,     # TODO: raise to PREMIUM post-beta

    # Admin features
    "admin_ops": FeatureTier.ADMIN,
    "admin_qa": FeatureTier.ADMIN,
    "admin_costs": FeatureTier.ADMIN,
}

# Tier hierarchy for comparison
_TIER_ORDER = {
    FeatureTier.FREE: 0,
    FeatureTier.AUTHENTICATED: 1,
    FeatureTier.PREMIUM: 2,
    FeatureTier.ADMIN: 3,
}

# Invite code prefixes that grant PREMIUM tier for free during beta
_PREMIUM_INVITE_PREFIXES = ("sfp-beta-", "sfp-amy-", "sfp-team-")


def _is_beta_premium(user: dict) -> bool:
    """Return True if user qualifies for PREMIUM via beta invite code."""
    # Explicit subscription_tier = 'premium' in DB
    if user.get("subscription_tier") == "premium":
        return True
    # Invite code prefix grants PREMIUM during beta
    code = user.get("invite_code") or ""
    return any(code.startswith(prefix) for prefix in _PREMIUM_INVITE_PREFIXES)


def get_user_tier(user: dict | None) -> FeatureTier:
    """Determine a user's feature tier."""
    if user is None:
        return FeatureTier.FREE
    if user.get("is_admin"):
        return FeatureTier.ADMIN
    if _is_beta_premium(user):
        return FeatureTier.PREMIUM
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
      - is_premium: bool
      - is_admin: bool
    """
    tier = get_user_tier(user)
    ctx = {
        "tier": tier.value,
        "is_authenticated": tier != FeatureTier.FREE,
        "is_premium": _TIER_ORDER[tier] >= _TIER_ORDER[FeatureTier.PREMIUM],
        "is_admin": tier == FeatureTier.ADMIN,
    }
    # Add can_* flags for each feature
    for feature in FEATURE_REGISTRY:
        ctx[f"can_{feature}"] = can_access(feature, user)
    return ctx
