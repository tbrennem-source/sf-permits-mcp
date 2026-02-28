"""
Tests for the redesigned showcase_stuck.html component.

Verifies:
- Component renders without error
- Headline contains "432 days" (or days_stuck value)
- CRITICAL badge present
- All 4 station names visible (BLDG, MECH, SFFD, CP-ZOC)
- Pipeline station blocks present
- CTA links to /tools/stuck-permit with permit param
- No raw JSON or dict output in rendered HTML
- Intervention step present
- Intelligence label present
- Severity pulse element present
"""

import json
import os
import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape


WORKTREE_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = WORKTREE_ROOT / "web" / "templates"
SHOWCASE_DATA_PATH = WORKTREE_ROOT / "web" / "static" / "data" / "showcase_data.json"


@pytest.fixture(scope="module")
def showcase_data():
    """Load real showcase_data.json from disk."""
    with open(SHOWCASE_DATA_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def jinja_env():
    """Create a Jinja2 environment pointed at the templates directory."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        # Allow undefined variables to surface as empty string (not exception)
        undefined=_SilentUndefined,
    )
    return env


from jinja2 import Undefined


class _SilentUndefined(Undefined):
    """Return empty string for undefined variables so partial renders work."""

    def __str__(self):
        return ""

    def __call__(self, *args, **kwargs):
        return ""

    def __getattr__(self, name):
        return _SilentUndefined()


@pytest.fixture(scope="module")
def rendered_html(jinja_env, showcase_data):
    """Render showcase_stuck.html with real fixture data."""
    template = jinja_env.get_template("components/showcase_stuck.html")
    html = template.render(showcase=showcase_data)
    return html


# ──────────────────────────────────────────────────────────────
# Test 1 — Component renders without error and is non-empty
# ──────────────────────────────────────────────────────────────

def test_component_renders_without_error(rendered_html):
    """Template must render to non-empty HTML."""
    assert rendered_html
    assert len(rendered_html) > 100


# ──────────────────────────────────────────────────────────────
# Test 2 — Headline contains days_stuck value ("432 days")
# ──────────────────────────────────────────────────────────────

def test_headline_contains_days_stuck(rendered_html, showcase_data):
    """Headline must contain the days_stuck value from data."""
    days = str(showcase_data["stuck_permit"]["days_stuck"])  # "432"
    assert days in rendered_html, f"Expected '{days} days' in headline"
    assert "days" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 3 — CRITICAL badge is present
# ──────────────────────────────────────────────────────────────

def test_critical_badge_present(rendered_html):
    """CRITICAL severity badge must appear in rendered output."""
    assert "CRITICAL" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 4 — All 4 station abbreviations are visible
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("station", ["BLDG", "MECH", "SFFD", "CP-ZOC"])
def test_station_abbreviations_present(station, rendered_html):
    """Each of the 4 blocked stations must appear in the rendered HTML."""
    assert station in rendered_html, f"Station '{station}' not found in rendered component"


# ──────────────────────────────────────────────────────────────
# Test 5 — Pipeline visual elements (station blocks) present
# ──────────────────────────────────────────────────────────────

def test_pipeline_station_blocks_present(rendered_html):
    """The horizontal pipeline must contain station block elements."""
    assert "stuck-pipeline" in rendered_html
    assert "stuck-station-block" in rendered_html
    # 4 blocks expected — count occurrences of the block class
    block_count = rendered_html.count("stuck-station-block")
    # Each block has the class twice (outer div + variant modifier appears 1x per blocked block)
    # At minimum we expect 4 occurrences of the base class
    assert block_count >= 4, f"Expected at least 4 station blocks, found {block_count}"


# ──────────────────────────────────────────────────────────────
# Test 6 — CTA links to /tools/stuck-permit with permit param
# ──────────────────────────────────────────────────────────────

def test_cta_links_to_stuck_permit_tool(rendered_html, showcase_data):
    """CTA anchor must link to stuck-permit tool with the correct permit number."""
    permit = showcase_data["stuck_permit"]["permit"]  # "202412237330"
    expected_href = f"/tools/stuck-permit?permit={permit}"
    assert expected_href in rendered_html, (
        f"Expected CTA href '{expected_href}' not found in rendered HTML"
    )


def test_cta_text_present(rendered_html):
    """CTA link text 'See full playbook' must be present."""
    assert "See full playbook" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 7 — No raw JSON / Python dict output
# ──────────────────────────────────────────────────────────────

def test_no_raw_json_or_dict_output(rendered_html):
    """Rendered HTML must not contain raw Python dict or JSON dumps."""
    # Raw dict output looks like: {'station': 'BLDG', ...} or {"station": "BLDG", ...}
    assert "&#39;station&#39;:" not in rendered_html, "Raw escaped dict found"
    assert "'station':" not in rendered_html, "Raw Python dict found"
    # Raw JSON array open bracket followed by quote and key
    assert '{"permit"' not in rendered_html
    assert '{"station"' not in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 8 — Intelligence label present
# ──────────────────────────────────────────────────────────────

def test_intelligence_label_present(rendered_html):
    """The 'Diagnostic Intelligence' label must appear at the top of the card."""
    assert "Diagnostic Intelligence" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 9 — Severity pulse animation element present
# ──────────────────────────────────────────────────────────────

def test_severity_pulse_element_present(rendered_html):
    """Pulsing red dot element must have the severity-pulse CSS class."""
    assert "severity-pulse" in rendered_html
    # The keyframe animation definition must also be present
    assert "pulse-red" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 10 — First intervention step displayed
# ──────────────────────────────────────────────────────────────

def test_first_intervention_step_present(rendered_html):
    """The first playbook step must be rendered as the intervention hint."""
    assert "Step 1:" in rendered_html
    # Should NOT display all 3 steps inline
    assert "Step 3:" not in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 11 — Card uses ghost-cta class for CTA link
# ──────────────────────────────────────────────────────────────

def test_cta_uses_ghost_cta_class(rendered_html):
    """CTA must use the design-system ghost-cta class."""
    assert "ghost-cta" in rendered_html


# ──────────────────────────────────────────────────────────────
# Test 12 — Agency count in headline
# ──────────────────────────────────────────────────────────────

def test_headline_contains_agency_count(rendered_html, showcase_data):
    """Headline must include block_count (4) and 'agencies blocked'."""
    block_count = str(showcase_data["stuck_permit"]["block_count"])  # "4"
    assert block_count in rendered_html
    assert "agencies blocked" in rendered_html
