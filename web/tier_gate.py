"""Tier gate decorator for subscription-gated routes.

Provides @requires_tier('beta') and @requires_tier('premium') decorators.
Used to gate content behind subscription tiers.

Tier hierarchy:
  free < beta < premium

Usage:
    from web.tier_gate import requires_tier

    @bp.route('/some-feature')
    @login_required
    @requires_tier('beta')
    def some_feature():
        return render_template('some_feature.html')

    # Or for teaser rendering (non-redirect behavior):
    @bp.route('/portfolio')
    @login_required
    def portfolio():
        if not has_tier(g.user, 'beta'):
            return render_template('portfolio.html', tier_locked=True, ...)
        return render_template('portfolio.html', tier_locked=False, ...)
"""
import functools
import logging

from flask import g, redirect, render_template, url_for

# Tier hierarchy: index = access level (higher = more access)
_TIER_LEVELS = {
    "free": 0,
    "beta": 1,
    "premium": 2,
}


def _user_tier_level(user: dict) -> int:
    """Return numeric tier level for a user dict. Defaults to 0 (free)."""
    tier = user.get("subscription_tier", "free") or "free"
    return _TIER_LEVELS.get(tier, 0)


def has_tier(user: dict, required_tier: str) -> bool:
    """Return True if user meets or exceeds required_tier."""
    required_level = _TIER_LEVELS.get(required_tier, 0)
    return _user_tier_level(user) >= required_level


def requires_tier(required_tier: str):
    """Decorator: gate a route behind a subscription tier.

    Behavior by user state:
    - Anonymous: redirect to /auth/login
    - Free (below required tier): render tier_gate_teaser.html fragment
    - Beta/Premium (meets required tier): render full content (calls wrapped fn)

    Args:
        required_tier: 'beta' or 'premium'

    Example:
        @bp.route('/tool')
        @login_required
        @requires_tier('beta')
        def tool():
            return render_template('tool.html')
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")

            if not user:
                return redirect(url_for("auth.auth_login"))

            if not has_tier(user, required_tier):
                logging.debug(
                    "tier_gate: user %s (tier=%s) blocked from %s (requires %s)",
                    user.get("user_id"),
                    user.get("subscription_tier", "free"),
                    fn.__name__,
                    required_tier,
                )
                return render_template(
                    "fragments/tier_gate_teaser.html",
                    required_tier=required_tier,
                    current_tier=user.get("subscription_tier", "free"),
                    user=user,
                ), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
