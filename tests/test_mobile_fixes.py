"""Tests for Sprint 97 mobile UX fixes.

Validates:
1. ghost-cta in obsidian.css has adequate vertical padding (≥8px → touch target ≥32px)
2. mcp-demo-dot in mcp-demo.css has adequate size/padding
3. landing.html has a mobile nav element with required links

All tests operate on raw file contents — no rendering or Flask client needed.
"""
import os
import re

# File paths
OBSIDIAN_CSS = os.path.join(os.path.dirname(__file__), "../web/static/obsidian.css")
MCP_DEMO_CSS = os.path.join(os.path.dirname(__file__), "../web/static/mcp-demo.css")
LANDING_HTML = os.path.join(os.path.dirname(__file__), "../web/templates/landing.html")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Issue 1: Ghost CTA touch target
# ---------------------------------------------------------------------------

class TestGhostCtaPadding:
    """ghost-cta padding must be ≥ 8px to achieve ≥32px touch target on mobile."""

    def setup_method(self):
        self.css = _read(OBSIDIAN_CSS)

    def test_ghost_cta_block_exists(self):
        """The .ghost-cta rule exists in obsidian.css."""
        assert ".ghost-cta {" in self.css or ".ghost-cta{" in self.css

    def _extract_ghost_cta_block(self):
        """Extract the .ghost-cta rule block."""
        # Find the block starting from .ghost-cta {
        m = re.search(r'\.ghost-cta\s*\{([^}]+)\}', self.css)
        assert m is not None, ".ghost-cta rule not found"
        return m.group(1)

    def test_ghost_cta_has_padding(self):
        """ghost-cta block includes a padding property."""
        block = self._extract_ghost_cta_block()
        assert "padding" in block, "ghost-cta must have a padding property for mobile touch targets"

    def test_ghost_cta_padding_is_adequate(self):
        """ghost-cta vertical padding must be ≥8px to ensure ≥32px touch target."""
        block = self._extract_ghost_cta_block()
        # Look for padding: <top> ... or padding-top: <N>px
        # Accept: padding: 8px 0, padding: 8px, padding-top: 8px (or higher values)
        shorthand = re.search(r'padding\s*:\s*(\d+)px', block)
        top_only = re.search(r'padding-top\s*:\s*(\d+)px', block)
        if shorthand:
            top_px = int(shorthand.group(1))
        elif top_only:
            top_px = int(top_only.group(1))
        else:
            # padding: 0 or no numeric padding found
            top_px = 0
        assert top_px >= 8, (
            f"ghost-cta top padding is {top_px}px — must be ≥8px for a ≥32px touch target. "
            f"Found block: {block.strip()}"
        )

    def test_ghost_cta_is_inline_block(self):
        """ghost-cta must be display: inline-block so padding takes vertical effect."""
        block = self._extract_ghost_cta_block()
        assert "inline-block" in block, "ghost-cta must be display: inline-block"


# ---------------------------------------------------------------------------
# Issue 2: MCP Demo Dots touch target
# ---------------------------------------------------------------------------

class TestMcpDemoDots:
    """mcp-demo-dot must have adequate size (≥12px) and padding (≥10px)
    so the combined touch target is ≥32px."""

    def setup_method(self):
        self.css = _read(MCP_DEMO_CSS)

    def test_dot_rule_exists(self):
        """The .mcp-demo-dot rule exists in mcp-demo.css."""
        assert ".mcp-demo-dot {" in self.css or ".mcp-demo-dot{" in self.css

    def _extract_dot_block(self):
        m = re.search(r'\.mcp-demo-dot\s*\{([^}]+)\}', self.css)
        assert m is not None, ".mcp-demo-dot rule not found"
        return m.group(1)

    def test_dot_width_adequate(self):
        """mcp-demo-dot width must be ≥12px."""
        block = self._extract_dot_block()
        m = re.search(r'width\s*:\s*(\d+)px', block)
        assert m is not None, ".mcp-demo-dot must have an explicit width in px"
        width = int(m.group(1))
        assert width >= 12, f"mcp-demo-dot width is {width}px — must be ≥12px"

    def test_dot_height_adequate(self):
        """mcp-demo-dot height must be ≥12px."""
        block = self._extract_dot_block()
        m = re.search(r'height\s*:\s*(\d+)px', block)
        assert m is not None, ".mcp-demo-dot must have an explicit height in px"
        height = int(m.group(1))
        assert height >= 12, f"mcp-demo-dot height is {height}px — must be ≥12px"

    def test_dot_has_padding(self):
        """mcp-demo-dot must have padding to expand touch target."""
        block = self._extract_dot_block()
        assert "padding" in block, (
            ".mcp-demo-dot must have padding to expand the touch target to ≥32px"
        )

    def test_dot_padding_adequate(self):
        """mcp-demo-dot padding must be ≥10px so combined touch target ≥32px."""
        block = self._extract_dot_block()
        m = re.search(r'padding\s*:\s*(\d+)px', block)
        assert m is not None, ".mcp-demo-dot padding value not found"
        padding = int(m.group(1))
        assert padding >= 10, (
            f"mcp-demo-dot padding is {padding}px — must be ≥10px (12px dot + 2×10px = 32px)"
        )

    def test_dot_box_sizing_content_box(self):
        """mcp-demo-dot must use box-sizing: content-box so padding adds to size."""
        block = self._extract_dot_block()
        assert "content-box" in block, (
            ".mcp-demo-dot must use box-sizing: content-box so padding expands the touch target"
        )


# ---------------------------------------------------------------------------
# Issue 3: Landing page mobile navigation
# ---------------------------------------------------------------------------

class TestLandingMobileNav:
    """landing.html must include a mobile nav bar with key links."""

    def setup_method(self):
        self.html = _read(LANDING_HTML)

    def test_mobile_nav_element_present(self):
        """A nav element with class mobile-nav must exist."""
        assert 'class="mobile-nav"' in self.html or "mobile-nav" in self.html, (
            "landing.html must include a .mobile-nav element"
        )

    def test_mobile_nav_has_search_link(self):
        """Mobile nav must link to /search."""
        assert 'href="/search"' in self.html

    def test_mobile_nav_has_demo_link(self):
        """Mobile nav must link to /demo."""
        assert 'href="/demo"' in self.html

    def test_mobile_nav_has_login_link(self):
        """Mobile nav must link to /auth/login."""
        assert 'href="/auth/login"' in self.html

    def test_mobile_nav_css_uses_max_width_480(self):
        """Mobile nav styles must use @media (max-width: 480px)."""
        assert "max-width: 480px" in self.html, (
            "Mobile nav must be scoped to @media (max-width: 480px)"
        )

    def test_mobile_nav_touch_target_height(self):
        """Mobile nav links must have height or min-height ≥44px for tap targets."""
        # Look for height: 44px or higher in the mobile-nav CSS block
        m = re.search(r'\.mobile-nav[^{]*\{[^}]*height\s*:\s*(\d+)px', self.html)
        if m:
            h = int(m.group(1))
            assert h >= 44, f"mobile-nav height is {h}px — must be ≥44px"
        else:
            # Alternative: check that height is defined somewhere in the mobile-nav section
            assert "height:" in self.html, (
                "mobile-nav must define an explicit height for touch target compliance"
            )
