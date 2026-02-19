"""Tests for web/billing.py — gate logic for billing tiers.

Billing gate is currently DISABLED — all users get all modes.
Tests verify the passthrough behavior and the resolve_analysis_mode tuple API.
When billing is re-enabled, update these tests to enforce tier checks.
"""

from web.billing import (
    can_use_full_analysis,
    resolve_analysis_mode,
    MODE_COMPLIANCE,
    MODE_SAMPLE,
    MODE_FULL,
    TIER_FREE,
    TIER_PRO,
)


# ── can_use_full_analysis (gate disabled — always True) ──────────


def test_can_use_full_analysis_pro():
    user = {"subscription_tier": TIER_PRO}
    assert can_use_full_analysis(user) is True


def test_can_use_full_analysis_free():
    """Gate disabled — free tier users can use full analysis."""
    user = {"subscription_tier": TIER_FREE}
    assert can_use_full_analysis(user) is True


def test_can_use_full_analysis_none():
    """Gate disabled — even anonymous users get True."""
    assert can_use_full_analysis(None) is True


def test_can_use_full_analysis_missing_tier():
    """User dict without subscription_tier still gets True (gate disabled)."""
    user = {"email": "test@example.com"}
    assert can_use_full_analysis(user) is True


# ── resolve_analysis_mode ──────────────────────────────────────────


def test_resolve_mode_requests_full():
    """Any user requesting full gets full (no downgrade)."""
    user = {"subscription_tier": TIER_FREE}
    mode, downgraded = resolve_analysis_mode(user, "full")
    assert mode == MODE_FULL
    assert downgraded is False


def test_resolve_mode_anonymous_requests_full():
    """Anonymous user requesting full also gets full (gate disabled)."""
    mode, downgraded = resolve_analysis_mode(None, "full")
    assert mode == MODE_FULL
    assert downgraded is False


def test_resolve_mode_requests_sample():
    user = {"subscription_tier": TIER_PRO}
    mode, downgraded = resolve_analysis_mode(user, "sample")
    assert mode == MODE_SAMPLE
    assert downgraded is False


def test_resolve_mode_compliance():
    """Anyone can use compliance mode."""
    mode, downgraded = resolve_analysis_mode(None, "compliance")
    assert mode == MODE_COMPLIANCE
    assert downgraded is False

    user = {"subscription_tier": TIER_FREE}
    mode, downgraded = resolve_analysis_mode(user, "compliance")
    assert mode == MODE_COMPLIANCE
    assert downgraded is False


def test_resolve_mode_default():
    """Default mode is sample."""
    mode, downgraded = resolve_analysis_mode(None)
    assert mode == MODE_SAMPLE
    assert downgraded is False


def test_resolve_mode_returns_tuple():
    """All resolve calls return (mode, downgraded) tuple."""
    result = resolve_analysis_mode(None, "full")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], bool)
