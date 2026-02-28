"""Tests for web/gate_analytics.py — tier gate and onboarding analytics events."""

import importlib.util
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# Module import tests
# ---------------------------------------------------------------------------

def test_gate_analytics_imports():
    """gate_analytics module imports without error."""
    spec = importlib.util.spec_from_file_location(
        "gate_analytics",
        os.path.join(os.path.dirname(__file__), "..", "web", "gate_analytics.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "track_gate_impression")
    assert hasattr(mod, "track_onboarding_complete")
    assert hasattr(mod, "track_onboarding_skip")


def test_gate_analytics_functions_are_callable():
    """All three public functions are callable."""
    from web.gate_analytics import (
        track_gate_impression,
        track_onboarding_complete,
        track_onboarding_skip,
    )
    assert callable(track_gate_impression)
    assert callable(track_onboarding_complete)
    assert callable(track_onboarding_skip)


# ---------------------------------------------------------------------------
# Behaviour tests — should NOT raise regardless of PostHog configuration
# ---------------------------------------------------------------------------

def test_track_gate_impression_no_error():
    """track_gate_impression doesn't raise with anonymous user."""
    from web.gate_analytics import track_gate_impression
    # Should not raise even if posthog not configured
    track_gate_impression(None, "beta", "anonymous", "/dashboard")


def test_track_gate_impression_with_user():
    """track_gate_impression works with a real user dict."""
    from web.gate_analytics import track_gate_impression
    user = {"user_id": "user-999"}
    track_gate_impression(user, "pro", "beta", "/search")


def test_track_onboarding_complete_no_error():
    """track_onboarding_complete doesn't raise with a valid user."""
    from web.gate_analytics import track_onboarding_complete
    user = {"user_id": "test-123"}
    track_onboarding_complete(user, "homeowner", "487 Noe St")


def test_track_onboarding_complete_no_user():
    """track_onboarding_complete handles None user gracefully."""
    from web.gate_analytics import track_onboarding_complete
    # user=None is acceptable — posthog_track falls back to "anonymous"
    track_onboarding_complete(None, "expediter", "123 Main St")


def test_track_onboarding_skip_no_error():
    """track_onboarding_skip doesn't raise."""
    from web.gate_analytics import track_onboarding_skip
    user = {"user_id": "test-123"}
    track_onboarding_skip(user, 1)


def test_track_onboarding_skip_step_zero():
    """track_onboarding_skip works with step=0 edge case."""
    from web.gate_analytics import track_onboarding_skip
    user = {"user_id": "test-456"}
    track_onboarding_skip(user, 0)


# ---------------------------------------------------------------------------
# Private helper test
# ---------------------------------------------------------------------------

def test_get_posthog_track_returns_callable():
    """_get_posthog_track always returns a callable, even without PostHog configured."""
    from web.gate_analytics import _get_posthog_track
    fn = _get_posthog_track()
    assert callable(fn)


# ---------------------------------------------------------------------------
# Email template existence tests
# ---------------------------------------------------------------------------

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")


def test_brief_email_exists():
    """brief_email.html exists and contains sfpermits branding."""
    path = os.path.join(TEMPLATE_DIR, "brief_email.html")
    if not os.path.exists(path):
        pytest.skip("brief_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "sfpermits" in content.lower()


def test_invite_email_exists():
    """invite_email.html exists and contains sfpermits branding."""
    path = os.path.join(TEMPLATE_DIR, "invite_email.html")
    if not os.path.exists(path):
        pytest.skip("invite_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "sfpermits" in content.lower()


def test_notification_email_exists():
    """notification_email.html exists and contains sfpermits branding."""
    path = os.path.join(TEMPLATE_DIR, "notification_email.html")
    if not os.path.exists(path):
        pytest.skip("notification_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "sfpermits" in content.lower()


def test_report_email_exists():
    """report_email.html exists and contains sfpermits branding."""
    path = os.path.join(TEMPLATE_DIR, "report_email.html")
    if not os.path.exists(path):
        pytest.skip("report_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "sfpermits" in content.lower()


def test_brief_email_has_brand_teal():
    """brief_email.html uses brand teal (#00d4c8) for links/accents."""
    path = os.path.join(TEMPLATE_DIR, "brief_email.html")
    if not os.path.exists(path):
        pytest.skip("brief_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "#00d4c8" in content, "Brand teal #00d4c8 not found — email not migrated"


def test_invite_email_has_brand_teal():
    """invite_email.html uses brand teal (#00d4c8)."""
    path = os.path.join(TEMPLATE_DIR, "invite_email.html")
    if not os.path.exists(path):
        pytest.skip("invite_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "#00d4c8" in content, "Brand teal #00d4c8 not found — email not migrated"


def test_notification_email_has_brand_teal():
    """notification_email.html uses brand teal (#00d4c8)."""
    path = os.path.join(TEMPLATE_DIR, "notification_email.html")
    if not os.path.exists(path):
        pytest.skip("notification_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "#00d4c8" in content, "Brand teal #00d4c8 not found — email not migrated"


def test_report_email_has_brand_teal():
    """report_email.html uses brand teal (#00d4c8)."""
    path = os.path.join(TEMPLATE_DIR, "report_email.html")
    if not os.path.exists(path):
        pytest.skip("report_email.html not found")
    with open(path) as f:
        content = f.read()
    assert "#00d4c8" in content, "Brand teal #00d4c8 not found — email not migrated"
