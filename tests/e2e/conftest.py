"""Playwright E2E test fixtures for sfpermits.ai.

Provides two test modes:

1. **Local live_server** (default): Starts Flask in a background thread.
   Playwright tests run against it automatically. No env vars required for
   anonymous tests; set TEST_LOGIN_SECRET for authenticated tests.

2. **External server**: Set E2E_BASE_URL and TEST_LOGIN_SECRET to test
   against staging or production.

Usage (local — auto-starts Flask):
    pytest tests/e2e/ -v

Usage (against staging):
    E2E_BASE_URL=https://sfpermits-ai-staging.up.railway.app \
    TEST_LOGIN_SECRET=<secret> \
    pytest tests/e2e/ -v
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# E2E gate — legacy skip marker for tests needing external server
# ---------------------------------------------------------------------------

E2E_AVAILABLE = bool(os.environ.get("E2E_BASE_URL"))

skip_if_no_e2e = pytest.mark.skipif(
    not E2E_AVAILABLE,
    reason="E2E_BASE_URL not set — skipping live-server test",
)

# Screenshot output directory
SCREENSHOT_DIR = Path("qa-results/screenshots/e2e")


def _find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

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
def live_server() -> str:
    """Start a live Flask server for Playwright tests.

    If E2E_BASE_URL is set, uses that external server instead.
    Otherwise starts Flask in a background thread on a random port.
    """
    ext_url = os.environ.get("E2E_BASE_URL")
    if ext_url:
        yield ext_url
        return

    # Enable test-login for the embedded server
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("TEST_LOGIN_SECRET", "e2e-test-secret-local")

    # Import Flask app (adds project root to sys.path)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from web.app import app as flask_app
    flask_app.config["TESTING"] = True

    port = _find_free_port()
    thread = threading.Thread(
        target=flask_app.run,
        kwargs={"port": port, "use_reloader": False, "threaded": True},
        daemon=True,
    )
    thread.start()

    url = f"http://localhost:{port}"
    # Wait up to 15s for server readiness
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError(f"Live server failed to start on {url}")

    yield url


@pytest.fixture(scope="session")
def base_url(live_server) -> str:
    """Base URL of the server under test.

    Delegates to live_server (which auto-starts Flask or uses E2E_BASE_URL).
    """
    return live_server


@pytest.fixture(scope="session")
def test_login_secret() -> str:
    """TEST_LOGIN_SECRET for /auth/test-login endpoint."""
    secret = os.environ.get("TEST_LOGIN_SECRET", "")
    if not secret:
        # live_server sets a default; only skip if explicitly testing against
        # an external server with no secret configured
        if E2E_AVAILABLE:
            pytest.skip("TEST_LOGIN_SECRET not set — cannot authenticate")
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


@pytest.fixture(scope="session")
def pw_browser():
    """Launch Playwright headless Chromium (session-scoped)."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(pw_browser, browser_context_args, live_server):
    """Fresh Playwright page for each test. Connected to live_server."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    context = pw_browser.new_context(**browser_context_args)
    pg = context.new_page()
    pg._base_url = live_server  # stash for convenience
    yield pg
    pg.close()
    context.close()


def login_as(page, base_url: str, secret: str, email: str) -> dict:
    """POST to /auth/test-login and authenticate the Playwright page.

    Returns the JSON response from the login endpoint.
    """
    import json as _json

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
def auth_page(pw_browser, browser_context_args, live_server, test_login_secret):
    """Factory: auth_page("admin") returns a Playwright page logged in as that persona.

    Usage:
        def test_something(auth_page):
            pg = auth_page("expediter")
            pg.goto(f"{pg._base_url}/account")
    """
    pages = []
    contexts = []

    def _make(persona_key: str = "admin"):
        if not test_login_secret:
            pytest.skip("TEST_LOGIN_SECRET not set — cannot authenticate")
        persona = PERSONAS[persona_key]
        ctx = pw_browser.new_context(**browser_context_args)
        pg = ctx.new_page()
        login_as(pg, live_server, test_login_secret, persona["email"])
        pg._base_url = live_server
        pages.append(pg)
        contexts.append(ctx)
        return pg

    yield _make

    for pg in pages:
        try:
            pg.close()
        except Exception:
            pass
    for ctx in contexts:
        try:
            ctx.close()
        except Exception:
            pass


@pytest.fixture
def authenticated_page(page, base_url, test_login_secret):
    """Playwright page pre-authenticated as the default admin persona."""
    if not test_login_secret:
        pytest.skip("TEST_LOGIN_SECRET not set — cannot authenticate")
    login_as(page, base_url, test_login_secret, PERSONAS["admin"]["email"])
    yield page


@pytest.fixture
def make_authenticated_page(page, base_url, test_login_secret):
    """Factory fixture: returns a function to authenticate as any persona."""
    def _make(persona_key: str = "admin"):
        if not test_login_secret:
            pytest.skip("TEST_LOGIN_SECRET not set — cannot authenticate")
        persona = PERSONAS[persona_key]
        login_as(page, base_url, test_login_secret, persona["email"])
        return page
    return _make
