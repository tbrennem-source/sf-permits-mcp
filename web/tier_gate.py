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

    # Teaser mode — renders page with blur overlay for non-qualifying users:
    @bp.route('/portfolio')
    @login_required
    @requires_tier('beta', teaser=True)
    def portfolio():
        # g.tier_locked is set by the decorator; template checks it
        return render_template('portfolio.html')

    # Or for manual teaser rendering (non-decorator pattern):
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


def requires_tier(required_tier: str, teaser: bool = False):
    """Decorator: gate a route behind a subscription tier.

    Args:
        required_tier: 'beta' or 'premium'
        teaser: If True, render the page content with a blur overlay + signup CTA
                instead of a hard redirect or 403. The wrapped function IS called,
                but g.tier_locked is set so the template can add the overlay.

    Behavior by user state (teaser=False — hard gate, existing behavior):
    - Anonymous: redirect to /auth/login
    - Free (below required tier): render tier_gate_teaser.html fragment (403)
    - Beta/Premium (meets required tier): render full content (calls wrapped fn)

    Behavior by user state (teaser=True — soft gate):
    - Anonymous: calls wrapped fn with g.tier_locked=True, g.tier_current='anonymous'
    - Free (below required tier): calls wrapped fn with g.tier_locked=True
    - Beta/Premium (meets required tier): calls wrapped fn with g.tier_locked=False

    Example:
        @bp.route('/tool')
        @login_required
        @requires_tier('beta')
        def tool():
            return render_template('tool.html')

        @bp.route('/portfolio')
        @login_required
        @requires_tier('beta', teaser=True)
        def portfolio():
            # g.tier_locked and tier_locked template variable set automatically
            return render_template('portfolio.html')
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")

            if teaser:
                # Teaser mode: always call the wrapped function, but set a flag
                # so the template can render a blur overlay + CTA for locked users.
                g.tier_locked = not has_tier(user, required_tier) if user else True
                g.tier_required = required_tier
                g.tier_current = (user.get("subscription_tier", "free") if user else "anonymous")
                return fn(*args, **kwargs)
            else:
                # Hard gate mode (existing behavior)
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
