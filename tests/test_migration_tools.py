"""Tests for Sprint 91 T2 template migration — design token compliance.

Verifies that all four migrated templates:
- Render without error
- Use head_obsidian.html fragment (for methodology, demo)
- Contain no legacy font variables (--font-body, --font-display)
- Contain no hardcoded hex colors outside the token palette
"""
import re
import pytest
from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────────

TEMPLATE_BASE = Path(__file__).parent.parent / "web" / "templates"

ALLOWED_HEX = {
    "#0a0a0f", "#12121a", "#1a1a26",
    "#5eead4",
    "#34d399", "#fbbf24", "#f87171", "#60a5fa",
    "#22c55e", "#f59e0b", "#ef4444",
    "#fff", "#000",
}

LEGACY_FONT_VARS = ["--font-body", "--font-display", "--font-mono", "--font-sans"]


def read_template(rel_path: str) -> str:
    return (TEMPLATE_BASE / rel_path).read_text(encoding="utf-8")


def find_non_token_hex(content: str) -> list[str]:
    """Return hex colors in content that are not in the token palette."""
    # Skip data URI lines and SVG strokes
    hex_re = re.compile(r"#([0-9a-fA-F]{3,8})\b")
    bad = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("{#") or stripped.startswith("<!--") or stripped.startswith("//"):
            continue
        if "data:image" in line:
            continue
        for m in hex_re.finditer(line):
            hex_val = f"#{m.group(1).lower()}"
            if len(hex_val) == 7 and hex_val in ALLOWED_HEX:
                continue
            if len(hex_val) == 4 and hex_val in ALLOWED_HEX:
                continue
            # OK if adjacent to var(-- context
            context = line[max(0, m.start() - 30):m.end() + 10]
            if "var(--" in context:
                continue
            if "stroke=" in context or "fill=" in context:
                continue
            bad.append(hex_val)
    return bad


# ── Route-level render tests ──────────────────────────────────────────────────

@pytest.fixture
def client():
    import web.app as _app_mod
    from web.helpers import _rate_buckets
    _app = _app_mod.app
    _app.config["TESTING"] = True
    _rate_buckets.clear()
    with _app.test_client() as c:
        yield c
    _rate_buckets.clear()


def test_what_if_renders(client):
    """what_if.html renders without error (unauthenticated)."""
    rv = client.get("/tools/what-if")
    # Page may redirect unauthenticated users; accept 200 or 302
    assert rv.status_code in (200, 302)


def test_cost_of_delay_renders(client):
    """cost_of_delay.html renders without error (unauthenticated)."""
    rv = client.get("/tools/cost-of-delay")
    assert rv.status_code in (200, 302)


def test_methodology_renders(client):
    """methodology.html renders without error."""
    rv = client.get("/methodology")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "sfpermits" in html.lower()
    assert "Methodology" in html or "How It Works" in html


def test_demo_renders(client):
    """demo.html renders without error."""
    rv = client.get("/demo")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "sfpermits" in html.lower()


# ── Static content checks — no browser required ───────────────────────────────

def test_what_if_uses_obsidian_fragment():
    """what_if.html includes head_obsidian.html fragment."""
    content = read_template("tools/what_if.html")
    assert "fragments/head_obsidian.html" in content, (
        "what_if.html must include fragments/head_obsidian.html"
    )


def test_cost_of_delay_uses_obsidian_fragment():
    """cost_of_delay.html includes head_obsidian.html fragment."""
    content = read_template("tools/cost_of_delay.html")
    assert "fragments/head_obsidian.html" in content, (
        "cost_of_delay.html must include fragments/head_obsidian.html"
    )


def test_methodology_uses_obsidian_fragment():
    """methodology.html includes head_obsidian.html fragment (migrated from standalone)."""
    content = read_template("methodology.html")
    assert "fragments/head_obsidian.html" in content, (
        "methodology.html must include fragments/head_obsidian.html"
    )


def test_demo_uses_obsidian_fragment():
    """demo.html includes head_obsidian.html fragment (migrated from standalone)."""
    content = read_template("demo.html")
    assert "fragments/head_obsidian.html" in content, (
        "demo.html must include fragments/head_obsidian.html"
    )


def test_methodology_no_legacy_font_vars():
    """methodology.html does not use legacy --font-body or --font-display vars."""
    content = read_template("methodology.html")
    for legacy in LEGACY_FONT_VARS:
        assert legacy not in content, (
            f"methodology.html still uses legacy font var: {legacy}"
        )


def test_demo_no_legacy_font_vars():
    """demo.html does not use legacy --font-body or --font-display vars."""
    content = read_template("demo.html")
    for legacy in LEGACY_FONT_VARS:
        assert legacy not in content, (
            f"demo.html still uses legacy font var: {legacy}"
        )


def test_what_if_no_legacy_font_vars():
    """what_if.html does not use legacy --font-body or --font-display vars."""
    content = read_template("tools/what_if.html")
    for legacy in LEGACY_FONT_VARS:
        assert legacy not in content, (
            f"what_if.html still uses legacy font var: {legacy}"
        )


def test_cost_of_delay_no_legacy_font_vars():
    """cost_of_delay.html does not use legacy --font-body or --font-display vars."""
    content = read_template("tools/cost_of_delay.html")
    for legacy in LEGACY_FONT_VARS:
        assert legacy not in content, (
            f"cost_of_delay.html still uses legacy font var: {legacy}"
        )


def test_methodology_no_standalone_root_vars():
    """methodology.html no longer defines its own :root CSS vars block."""
    content = read_template("methodology.html")
    # The old pattern was defining --obsidian, --accent, etc. directly in :root {}
    # After migration, the token vars come from head_obsidian.html → design-system.css
    # We should NOT have a large :root block with these specific vars in the template itself
    # (head_obsidian.html itself is excluded since it's a fragment with its own :root)
    lines = content.splitlines()
    in_root = False
    root_token_count = 0
    for line in lines:
        s = line.strip()
        if s.startswith(":root") and "{" in s:
            in_root = True
        if in_root:
            if "--obsidian:" in s or "--accent:" in s or "--signal-green:" in s:
                root_token_count += 1
        if in_root and "}" in s and not "{" in s:
            in_root = False

    assert root_token_count == 0, (
        f"methodology.html still defines design token vars in :root "
        f"(found {root_token_count} occurrences). These should come from head_obsidian.html."
    )


def test_demo_no_standalone_root_vars():
    """demo.html no longer defines its own :root CSS vars block."""
    content = read_template("demo.html")
    lines = content.splitlines()
    in_root = False
    root_token_count = 0
    for line in lines:
        s = line.strip()
        if s.startswith(":root") and "{" in s:
            in_root = True
        if in_root:
            if "--obsidian:" in s or "--accent:" in s or "--signal-green:" in s:
                root_token_count += 1
        if in_root and "}" in s and not "{" in s:
            in_root = False

    assert root_token_count == 0, (
        f"demo.html still defines design token vars in :root "
        f"(found {root_token_count} occurrences). These should come from head_obsidian.html."
    )


def test_methodology_uses_nav_fragment():
    """methodology.html uses the shared nav fragment after migration."""
    content = read_template("methodology.html")
    assert "fragments/nav.html" in content, (
        "methodology.html must include fragments/nav.html"
    )


def test_demo_uses_nav_fragment():
    """demo.html uses the shared nav fragment after migration."""
    content = read_template("demo.html")
    assert "fragments/nav.html" in content, (
        "demo.html must include fragments/nav.html"
    )


def test_methodology_no_non_token_hex():
    """methodology.html contains no hardcoded hex colors outside the token palette."""
    content = read_template("methodology.html")
    bad = find_non_token_hex(content)
    assert not bad, (
        f"methodology.html has non-token hex colors: {bad}"
    )


def test_demo_no_non_token_hex():
    """demo.html contains no hardcoded hex colors outside the token palette."""
    content = read_template("demo.html")
    bad = find_non_token_hex(content)
    assert not bad, (
        f"demo.html has non-token hex colors: {bad}"
    )


def test_what_if_no_non_token_hex():
    """what_if.html contains no hardcoded hex colors outside the token palette."""
    content = read_template("tools/what_if.html")
    bad = find_non_token_hex(content)
    assert not bad, (
        f"what_if.html has non-token hex colors: {bad}"
    )


def test_cost_of_delay_no_non_token_hex():
    """cost_of_delay.html contains no hardcoded hex colors outside the token palette."""
    content = read_template("tools/cost_of_delay.html")
    bad = find_non_token_hex(content)
    assert not bad, (
        f"cost_of_delay.html has non-token hex colors: {bad}"
    )
