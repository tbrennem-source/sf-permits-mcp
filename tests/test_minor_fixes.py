"""Tests for minor UX fixes: /demo mobile overflow, stats counter, and
landing page property navigation state machine.

Fix 1: demo.html .callout elements get display:block + max-width:100% at <=480px.
Fix 2: landing.html stats counter target is 1,137,816.
Fix 3: landing.html beta/returning state watched-property links go to /search
       or /portfolio, not back to /.
"""
import os
import re
import pytest
import web.app as _app_mod
from web.helpers import _rate_buckets


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
DEMO_TEMPLATE = os.path.join(TEMPLATES_DIR, "demo.html")
LANDING_TEMPLATE = os.path.join(TEMPLATES_DIR, "landing.html")


# ---------------------------------------------------------------------------
# Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app = _app_mod.app
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Fix 1 — /demo page renders and has mobile callout CSS
# ---------------------------------------------------------------------------

def test_demo_page_renders_without_error(client):
    """/demo route returns HTTP 200 with no server error."""
    rv = client.get("/demo")
    assert rv.status_code == 200


def test_demo_page_contains_callout_elements(client):
    """demo.html renders .callout elements for the annotation chips."""
    rv = client.get("/demo")
    html = rv.data.decode()
    assert 'class="callout"' in html


def test_demo_html_has_mobile_callout_fix():
    """demo.html @media (max-width: 480px) block includes .callout override."""
    with open(DEMO_TEMPLATE, "r") as fh:
        source = fh.read()

    # Locate the start of the 480px media block, then grab everything until
    # the closing outer brace. The block contains multiple rules each with
    # their own {}, so we can't use [^}]+ — instead find the block boundaries
    # by tracking brace depth.
    media_start = source.find("@media (max-width: 480px)")
    assert media_start != -1, "@media (max-width: 480px) block not found in demo.html"

    # Walk from the opening { to the matching closing }
    open_pos = source.index("{", media_start)
    depth = 0
    block_end = open_pos
    for i, ch in enumerate(source[open_pos:], start=open_pos):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                block_end = i
                break
    block = source[open_pos:block_end + 1]

    assert ".callout" in block, (
        ".callout rule missing from @media (max-width: 480px) in demo.html"
    )
    assert "display: block" in block, (
        "display: block missing from .callout rule in @media (max-width: 480px)"
    )
    assert "max-width: 100%" in block, (
        "max-width: 100% missing from .callout rule in @media (max-width: 480px)"
    )
    assert "box-sizing: border-box" in block, (
        "box-sizing: border-box missing from .callout rule in @media (max-width: 480px)"
    )


# ---------------------------------------------------------------------------
# Fix 2 — stats counter target is 1,137,816
# ---------------------------------------------------------------------------

def test_landing_stats_counter_target():
    """landing.html counting animation targets 1137816 (1,137,816 permits)."""
    with open(LANDING_TEMPLATE, "r") as fh:
        source = fh.read()

    # Look for the data-target attribute on the counting element
    match = re.search(r'data-target="(\d+)"', source)
    assert match, "No data-target attribute found on counting element in landing.html"
    target = int(match.group(1))
    assert target == 1137816, (
        f"Stats counter target is {target}, expected 1137816"
    )


# ---------------------------------------------------------------------------
# Fix 3 — property links in beta/returning states don't go to "/"
# ---------------------------------------------------------------------------

def test_landing_state_machine_watched_links_not_home():
    """beta/returning watched property links navigate to /search or /portfolio, not /."""
    with open(LANDING_TEMPLATE, "r") as fh:
        source = fh.read()

    # Extract the states JS object. Look for the states = { ... } block.
    # We care about the 'watched' values in beta and returning states.
    # The structure is: watched: '<a href="...">', so parse out hrefs inside watched strings.
    states_match = re.search(
        r"const states\s*=\s*\{(.+?)\};",
        source,
        re.DOTALL,
    )
    assert states_match, "states object not found in landing.html JS"
    states_block = states_match.group(1)

    # Find all href values inside watched strings in beta/returning states
    # Extract watched lines for beta and returning states
    watched_values = re.findall(r"watched:\s*'([^']*)'", states_block)
    assert len(watched_values) > 0, "No watched values found in states object"

    # For each watched value that contains href links, check none go to "/"
    for watched in watched_values:
        hrefs = re.findall(r'href="([^"]+)"', watched)
        for href in hrefs:
            assert href != "/", (
                f"Watched property link navigates to '/' (landing page) — "
                f"should go to /search or /portfolio. Found in: {watched}"
            )
