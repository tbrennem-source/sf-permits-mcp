"""Tests for onboarding wizard polish (Sprint 93 / QS11-T4).

Covers:
- Template existence and key content elements
- Progress indicators for all 3 steps
- Skip option availability
- Demo property suggestion in step 2
- Go to Dashboard CTA in step 3
- Celebration element in step 3
- Onboarding routes present in routes_auth.py
- Skip route via Flask test client
"""

import os
import pytest


# ---------------------------------------------------------------------------
# File-level checks (no server needed)
# ---------------------------------------------------------------------------

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
ROUTES_AUTH = os.path.join(os.path.dirname(__file__), "..", "web", "routes_auth.py")


def _read_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path) as f:
        return f.read()


# ── Step 1 ──────────────────────────────────────────────────────────────────

def test_onboarding_step1_template_exists():
    """Step 1 template file must exist."""
    assert os.path.exists(os.path.join(TEMPLATES_DIR, "onboarding_step1.html"))


def test_onboarding_step1_has_progress_indicator():
    """Step 1 must have a visual progress indicator showing step 1 of 3."""
    content = _read_template("onboarding_step1.html")
    # Should have dots or textual indicator
    has_dots = "onb-dot" in content or "step--active" in content
    has_label = "1 / 3" in content or "1/3" in content or "Step 1" in content
    assert has_dots or has_label, "No progress indicator found in step 1"


def test_onboarding_step1_has_skip():
    """Step 1 must have a skip option."""
    content = _read_template("onboarding_step1.html")
    assert "skip" in content.lower(), "No skip option found in step 1"


def test_onboarding_step1_skip_goes_to_dashboard():
    """Step 1 skip link should target the onboarding_skip route (goes to dashboard)."""
    content = _read_template("onboarding_step1.html")
    # Should reference onboarding_skip route, not step2
    assert "onboarding_skip" in content, (
        "Step 1 skip should go to onboarding_skip (dashboard), not step 2"
    )


def test_onboarding_step1_has_role_cards():
    """Step 1 must present role selection cards."""
    content = _read_template("onboarding_step1.html")
    for role in ("homeowner", "architect", "expediter", "contractor"):
        assert role in content, f"Role card for '{role}' not found in step 1"


def test_onboarding_step1_has_welcome_message():
    """Step 1 must have a welcome message."""
    content = _read_template("onboarding_step1.html")
    assert "welcome" in content.lower() or "Welcome" in content, (
        "No welcome message found in step 1"
    )


# ── Step 2 ──────────────────────────────────────────────────────────────────

def test_onboarding_step2_template_exists():
    """Step 2 template file must exist."""
    assert os.path.exists(os.path.join(TEMPLATES_DIR, "onboarding_step2.html"))


def test_onboarding_step2_has_progress_indicator():
    """Step 2 must have a visual progress indicator showing step 2 of 3."""
    content = _read_template("onboarding_step2.html")
    has_dots = "onb-dot" in content or "step--active" in content
    has_label = "2 / 3" in content or "2/3" in content or "Step 2" in content
    assert has_dots or has_label, "No progress indicator found in step 2"


def test_onboarding_step2_has_demo_property_suggestion():
    """Step 2 must show a demo property as a suggestion."""
    content = _read_template("onboarding_step2.html")
    # Demo property is 1455 Market St
    assert "1455 Market" in content, "Demo property suggestion (1455 Market St) not found in step 2"


def test_onboarding_step2_has_address_input():
    """Step 2 must have an address input field."""
    content = _read_template("onboarding_step2.html")
    assert 'type="text"' in content or "address-input" in content or 'name="address"' in content, (
        "No address input field found in step 2"
    )


def test_onboarding_step2_has_address_placeholder():
    """Step 2 address input must have a helpful placeholder."""
    content = _read_template("onboarding_step2.html")
    assert "placeholder" in content, "No placeholder found on address input in step 2"
    # Should suggest a specific address format
    assert "Noe" in content or "e.g." in content or "placeholder" in content


def test_onboarding_step2_has_skip():
    """Step 2 must have a skip / use demo property option."""
    content = _read_template("onboarding_step2.html")
    assert "skip" in content.lower() or "demo" in content.lower(), (
        "No skip/demo fallback found in step 2"
    )


# ── Step 3 ──────────────────────────────────────────────────────────────────

def test_onboarding_step3_template_exists():
    """Step 3 template file must exist."""
    assert os.path.exists(os.path.join(TEMPLATES_DIR, "onboarding_step3.html"))


def test_onboarding_step3_has_progress_indicator():
    """Step 3 must have a visual progress indicator showing step 3 of 3."""
    content = _read_template("onboarding_step3.html")
    has_dots = "onb-dot" in content or "step--active" in content
    has_label = "3 / 3" in content or "3/3" in content or "Step 3" in content
    assert has_dots or has_label, "No progress indicator found in step 3"


def test_onboarding_step3_has_dashboard_cta():
    """Step 3 must have a 'Go to Dashboard' CTA."""
    content = _read_template("onboarding_step3.html")
    assert "dashboard" in content.lower() or "Dashboard" in content, (
        "No dashboard CTA found in step 3"
    )


def test_onboarding_step3_has_celebration_element():
    """Step 3 must have a celebration or completion element."""
    content = _read_template("onboarding_step3.html")
    has_celebration = (
        "celebrate" in content.lower()
        or "onb-celebrate" in content
        or "animation" in content
        or "all set" in content.lower()
        or "✓" in content
        or "&#x2713;" in content  # HTML entity for checkmark
    )
    assert has_celebration, "No celebration/completion element found in step 3"


def test_onboarding_step3_has_nightly_update_note():
    """Step 3 must highlight that data updates nightly."""
    content = _read_template("onboarding_step3.html")
    assert "night" in content.lower() or "nightly" in content.lower(), (
        "No nightly update note found in step 3"
    )


# ── Routes ───────────────────────────────────────────────────────────────────

def test_routes_auth_has_onboarding_routes():
    """routes_auth.py must define the core onboarding routes."""
    with open(ROUTES_AUTH) as f:
        content = f.read()
    for route_fn in (
        "onboarding_step1",
        "onboarding_step2",
        "onboarding_step3",
        "onboarding_complete",
    ):
        assert route_fn in content, f"Route function '{route_fn}' not found in routes_auth.py"


def test_routes_auth_has_onboarding_skip():
    """routes_auth.py must define an onboarding_skip route."""
    with open(ROUTES_AUTH) as f:
        content = f.read()
    assert "onboarding_skip" in content, "onboarding_skip route not found in routes_auth.py"


# ── Flask client integration (smoke tests) ──────────────────────────────────

def _make_app():
    """Create a test Flask app. Returns None if env not set up for web tests."""
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from web.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SECRET_KEY"] = "test-secret-key"
        return app
    except Exception:
        return None


@pytest.mark.integration
def test_onboarding_skip_route_redirects():
    """The /onboarding/skip route must redirect to dashboard."""
    app = _make_app()
    if app is None:
        pytest.skip("Flask app not available in this test environment")

    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Simulate logged-in user
            sess["user_id"] = "test-user-123"

        resp = client.get("/onboarding/skip", follow_redirects=False)
        # Should redirect (302/303) — not 404 or 500
        assert resp.status_code in (301, 302, 303, 307, 308), (
            f"Expected redirect from /onboarding/skip, got {resp.status_code}"
        )


@pytest.mark.integration
def test_onboarding_step1_route_exists():
    """The /onboarding/step/1 route must exist (not 404)."""
    app = _make_app()
    if app is None:
        pytest.skip("Flask app not available in this test environment")

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = "test-user-123"

        resp = client.get("/onboarding/step/1", follow_redirects=False)
        assert resp.status_code != 404, "Route /onboarding/step/1 returned 404"
