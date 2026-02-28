"""Analytics events for tier gating and onboarding."""


def _get_posthog_track():
    """Lazy import to handle missing posthog gracefully."""
    try:
        from web.helpers import posthog_track
        return posthog_track
    except (ImportError, AttributeError):
        # Fallback: no-op if posthog not configured
        import logging

        def _noop(event, props=None, user_id=None):
            logging.debug(f"[posthog noop] {event}: {props}")
        return _noop


def track_gate_impression(user, required_tier, current_tier, page):
    posthog_track = _get_posthog_track()
    posthog_track("tier_gate_impression", {
        "required_tier": required_tier,
        "current_tier": current_tier,
        "page": page,
    }, user_id=user.get("user_id") if user else None)


def track_onboarding_complete(user, role, property_address):
    posthog_track = _get_posthog_track()
    posthog_track("onboarding_complete", {
        "role": role,
        "property_address": property_address,
    }, user_id=user.get("user_id") if user else None)


def track_onboarding_skip(user, step):
    posthog_track = _get_posthog_track()
    posthog_track("onboarding_skip", {
        "step": step,
    }, user_id=user.get("user_id") if user else None)
