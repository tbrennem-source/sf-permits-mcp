"""Tests for web/billing.py — gate logic for billing tiers."""

from web.billing import (
    can_use_full_analysis,
    resolve_analysis_mode,
    MODE_COMPLIANCE,
    MODE_SAMPLE,
    MODE_FULL,
    TIER_FREE,
    TIER_PRO,
)


# ── can_use_full_analysis ──────────────────────────────────────────


def test_can_use_full_analysis_pro():
    user = {"subscription_tier": TIER_PRO}
    assert can_use_full_analysis(user) is True


def test_can_use_full_analysis_free():
    user = {"subscription_tier": TIER_FREE}
    assert can_use_full_analysis(user) is False


def test_can_use_full_analysis_none():
    assert can_use_full_analysis(None) is False


def test_can_use_full_analysis_missing_tier():
    """User dict without subscription_tier defaults to free."""
    user = {"email": "test@example.com"}
    assert can_use_full_analysis(user) is False


# ── resolve_analysis_mode ──────────────────────────────────────────


def test_resolve_mode_pro_requests_full():
    user = {"subscription_tier": TIER_PRO}
    assert resolve_analysis_mode(user, "full") == MODE_FULL


def test_resolve_mode_pro_requests_sample():
    """Pro user requesting sample still gets sample."""
    user = {"subscription_tier": TIER_PRO}
    assert resolve_analysis_mode(user, "sample") == MODE_SAMPLE


def test_resolve_mode_free_requests_full():
    """Free tier requesting full gets downgraded to sample."""
    user = {"subscription_tier": TIER_FREE}
    assert resolve_analysis_mode(user, "full") == MODE_SAMPLE


def test_resolve_mode_anonymous():
    """Anonymous user requesting full gets downgraded to sample."""
    assert resolve_analysis_mode(None, "full") == MODE_SAMPLE


def test_resolve_mode_compliance():
    """Anyone can use compliance mode."""
    assert resolve_analysis_mode(None, "compliance") == MODE_COMPLIANCE
    user = {"subscription_tier": TIER_FREE}
    assert resolve_analysis_mode(user, "compliance") == MODE_COMPLIANCE


def test_resolve_mode_default():
    """Default mode is sample."""
    assert resolve_analysis_mode(None) == MODE_SAMPLE
