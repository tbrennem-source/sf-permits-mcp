"""Tests for web/billing.py — gate logic for billing tiers."""

from web.billing import (
    can_use_full_analysis,
    resolve_analysis_mode,
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


def test_resolve_mode_pro_requests_all():
    user = {"subscription_tier": TIER_PRO}
    assert resolve_analysis_mode(user, True) == MODE_FULL


def test_resolve_mode_pro_requests_sample():
    """Pro user not requesting all pages still gets sample."""
    user = {"subscription_tier": TIER_PRO}
    assert resolve_analysis_mode(user, False) == MODE_SAMPLE


def test_resolve_mode_free_requests_all():
    """Free tier requesting all pages still gets sample."""
    user = {"subscription_tier": TIER_FREE}
    assert resolve_analysis_mode(user, True) == MODE_SAMPLE


def test_resolve_mode_anonymous():
    """Anonymous user always gets sample."""
    assert resolve_analysis_mode(None, True) == MODE_SAMPLE
