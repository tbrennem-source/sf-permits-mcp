"""Playwright E2E test fixtures for sfpermits.ai.

SESSION A: Staging environment + test-login infrastructure.

These fixtures are used by all E2E tests that run against a live server
(staging or local dev). Tests are gated by E2E_BASE_URL env var so they
are skipped in CI unless explicitly configured.

Usage (against staging):
    E2E_BASE_URL=https://sfpermits-ai-staging.up.railway.app \
    TEST_LOGIN_SECRET=<secret> \
    pytest tests/e2e/ -v

Usage (against local dev):
    E2E_BASE_URL=http://localhost:5001 \
    TEST_LOGIN_SECRET=<secret> \
    pytest tests/e2e/ -v
"""

from __future__ import annotations

import os
import pytest

# ---------------------------------------------------------------------------
# E2E gate — skip all E2E tests unless E2E_BASE_URL is configured
# ---------------------------------------------------------------------------

E2E_AVAILABLE = bool(os.environ.get("E2E_BASE_URL"))

skip_if_no_e2e = pytest.mark.skipif(
    not E2E_AVAILABLE,
    reason="E2E_BASE_URL not set — skipping live-server test",
)

# ---------------------------------------------------------------------------
# Test personas
# ---------------------------------------------------------------------------
# 12 personas covering all user roles for E2E coverage.
# Each persona is a dict with: email, name, role (as displayed in UI context)
# role values: admin | expediter | homeowner | architect | contractor |
#              engineer | developer | planner | reviewer | owner | inspector | guest

PERSONAS: dict[str, dict[str, str]] = {
    "admin": {
        "email": "test-admin@sfpermits.ai",
        "name": "Test Admin",
        "role": "admin",
    },
    "expediter": {
        "email": "test-expediter@sfpermits.ai",
        "name": "Alice Expediter",
        "role": "expediter",
    },
    "homeowner": {
        "email": "test-homeowner@sfpermits.ai",
        "name": "Bob Homeowner",
        "role": "homeowner",
    },
    "architect": {
        "email": "test-architect@sfpermits.ai",
        "name": "Carol Architect",
        "role": "architect",
    },
    "contractor": {
        "email": "test-contractor@sfpermits.ai",
        "name": "Dave Contractor",
        "role": "contractor",
    },
    "engineer": {
        "email": "test-engineer@sfpermits.ai",
        "name": "Eve Engineer",
        "role": "engineer",
    },
    "developer": {
        "email": "test-developer@sfpermits.ai",
        "name": "Frank Developer",
        "role": "developer",
    },
    "planner": {
        "email": "test-planner@sfpermits.ai",
        "name": "Grace Planner",
        "role": "planner",
    },
    "reviewer": {
        "email": "test-reviewer@sfpermits.ai",
        "name": "Heidi Reviewer",
        "role": "reviewer",
    },
    "owner": {
        "email": "test-owner@sfpermits.ai",
        "name": "Ivan Owner",
        "role": "owner",
    },
    "inspector": {
        "email": "test-inspector@sfpermits.ai",
        "name": "Judy Inspector",
        "role": "inspector",
    },
    "guest": {
        "email": "test-guest@sfpermits.ai",
        "name": "Karl Guest",
        "role": "guest",
    },
}


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL of the server under test.

    Reads E2E_BASE_URL env var.  Default: http://localhost:5001.
    Override on command line:
        pytest tests/e2e/ --base-url https://sfpermits-ai-staging.up.railway.app
    """
    return os.environ.get("E2E_BASE_URL", "http://localhost:5001")


@pytest.fixture(scope="session")
def test_login_secret() -> str:
    """TEST_LOGIN_SECRET shared secret for /auth/test-login endpoint.

    Must match the TEST_LOGIN_SECRET env var configured on the server.
    """
    secret = os.environ.get("TEST_LOGIN_SECRET", "")
    if not secret and E2E_AVAILABLE:
        pytest.skip("TEST_LOGIN_SECRET not set — cannot authenticate for E2E test")
    return secret


# ---------------------------------------------------------------------------
# Playwright fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context args — can be overridden per-test."""
    return {
        "viewport": {"width": 1280, "height": 800},
        "ignore_https_errors": True,
    }


def login_as(page, base_url: str, secret: str, email: str) -> dict:
    """POST to /auth/test-login and authenticate the Playwright page.

    Makes a direct API call to /auth/test-login with the test secret,
    then navigates the page to capture the session cookie.

    Returns the JSON response from the login endpoint.

    Raises:
        RuntimeError: if the login fails (non-200 response)
    """
    import json as _json

    # Use page.request to POST with JSON body
    response = page.request.post(
        f"{base_url}/auth/test-login",
        data=_json.dumps({"secret": secret, "email": email}),
        headers={"Content-Type": "application/json"},
    )
    if response.status != 200:
        raise RuntimeError(
            f"test-login failed: HTTP {response.status} for {email}\n"
            f"Body: {response.text()}"
        )
    return response.json()


@pytest.fixture
def authenticated_page(page, base_url, test_login_secret):
    """Playwright page pre-authenticated as the default admin persona.

    Skipped automatically if E2E_BASE_URL is not configured.
    Yields the page after successful test-login.
    """
    if not E2E_AVAILABLE:
        pytest.skip("E2E_BASE_URL not set — skipping live-server test")
    login_as(
        page,
        base_url,
        test_login_secret,
        PERSONAS["admin"]["email"],
    )
    yield page


@pytest.fixture
def make_authenticated_page(page, base_url, test_login_secret):
    """Factory fixture: returns a function to authenticate as any persona.

    Usage:
        def test_something(make_authenticated_page):
            pg = make_authenticated_page("expediter")
            pg.goto("/account")
            ...
    """
    def _make(persona_key: str = "admin"):
        if not E2E_AVAILABLE:
            pytest.skip("E2E_BASE_URL not set — skipping live-server test")
        persona = PERSONAS[persona_key]
        login_as(page, base_url, test_login_secret, persona["email"])
        return page
    return _make
