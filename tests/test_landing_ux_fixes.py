"""Tests for landing page UX fixes applied in QS12 sprint.

Verifies template-level changes:
- BETA badge text is 'Beta Tester'
- scroll-cue has visible opacity (fadeInCue at 0.6)
- Property links in beta/returning states go to /?q= not /search?q=
"""

import re
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _landing_html():
    """Read the landing template once per test session."""
    with open("web/templates/landing.html", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Fix 1: BETA badge text
# ---------------------------------------------------------------------------

class TestBetaBadgeText:
    """The beta-badge element shows 'Beta Tester' not 'beta'."""

    def test_beta_badge_text_is_beta_tester(self):
        """id=beta-badge should contain 'Beta Tester'."""
        html = _landing_html()
        # Find the beta-badge span
        m = re.search(r'id="beta-badge"[^>]*>([^<]+)<', html)
        assert m is not None, "beta-badge element not found"
        badge_text = m.group(1).strip()
        assert badge_text == "Beta Tester", (
            f"Expected 'Beta Tester', got {badge_text!r}"
        )

    def test_beta_badge_id_present(self):
        """The id=beta-badge element must still be in the template."""
        html = _landing_html()
        assert 'id="beta-badge"' in html

    def test_beta_badge_not_lowercase_beta(self):
        """The old text 'beta' (exact, standalone) should not appear as badge text."""
        html = _landing_html()
        m = re.search(r'id="beta-badge"[^>]*>([^<]+)<', html)
        assert m is not None, "beta-badge element not found"
        badge_text = m.group(1).strip()
        assert badge_text != "beta", "Badge text is still lowercase 'beta' — should be 'Beta Tester'"


# ---------------------------------------------------------------------------
# Fix 2: scroll-cue opacity at 0.6
# ---------------------------------------------------------------------------

class TestScrollCueOpacity:
    """The scroll-cue animation should use fadeInCue (ends at opacity 0.6)."""

    def test_fadein_cue_keyframe_defined(self):
        """The @keyframes fadeInCue must be defined in the template."""
        html = _landing_html()
        assert "@keyframes fadeInCue" in html, (
            "fadeInCue keyframe not found — scroll-cue opacity fix missing"
        )

    def test_fadein_cue_ends_at_0_6(self):
        """fadeInCue should animate to opacity: 0.6."""
        html = _landing_html()
        # Match "@keyframes fadeInCue { to { opacity: 0.6; } }" (or similar whitespace)
        m = re.search(
            r'@keyframes\s+fadeInCue\s*\{[^}]*to\s*\{[^}]*opacity\s*:\s*0\.6',
            html,
        )
        assert m is not None, (
            "fadeInCue keyframe does not end at opacity: 0.6"
        )

    def test_scroll_cue_uses_fadein_cue(self):
        """The .scroll-cue CSS block should reference fadeInCue animation."""
        html = _landing_html()
        # Find the .scroll-cue block and verify it uses fadeInCue
        m = re.search(r'\.scroll-cue\s*\{[^}]+animation:[^}]+', html)
        assert m is not None, ".scroll-cue block not found"
        assert "fadeInCue" in m.group(0), (
            ".scroll-cue still uses old fadeIn animation — should use fadeInCue"
        )


# ---------------------------------------------------------------------------
# Fix 4: Property click targets — beta/returning use /?q= not /search?q=
# ---------------------------------------------------------------------------

class TestPropertyClickTargets:
    """Demo watched property links navigate to /?q= (full search) not /search?q=."""

    def test_beta_state_property_link_uses_index(self):
        """Beta state watched properties link to /?q= not /search?q=."""
        html = _landing_html()
        # Find the beta state JS object
        beta_section = re.search(
            r"beta\s*:\s*\{[^}]+watched[^}]+\}",
            html,
            re.DOTALL,
        )
        assert beta_section is not None, "beta state not found in JS"
        beta_text = beta_section.group(0)
        # Should not contain /search?q= for watched property addresses
        assert '/search?q=487' not in beta_text, (
            "Beta state has /search?q= link that loops through public search"
        )

    def test_returning_state_property_link_uses_index(self):
        """Returning state watched properties link to /?q= not /search?q=."""
        html = _landing_html()
        # Find the returning state JS object
        returning_section = re.search(
            r"returning\s*:\s*\{[^}]+watched[^}]+\}",
            html,
            re.DOTALL,
        )
        assert returning_section is not None, "returning state not found in JS"
        returning_text = returning_section.group(0)
        # Should not contain /search?q= for watched property addresses
        assert '/search?q=487' not in returning_text, (
            "Returning state has /search?q= link that loops through public search"
        )
        assert '/search?q=225' not in returning_text, (
            "Returning state has /search?q= link that loops through public search"
        )

    def test_beta_state_uses_root_search_path(self):
        """Beta state property links use /?q= prefix."""
        html = _landing_html()
        beta_section = re.search(
            r"beta\s*:\s*\{[^}]+watched[^}]+\}",
            html,
            re.DOTALL,
        )
        assert beta_section is not None, "beta state not found"
        beta_text = beta_section.group(0)
        assert '/?q=' in beta_text, (
            "Beta state property links should use /?q= to go to full search"
        )

    def test_portfolio_link_preserved(self):
        """The /portfolio link should still exist in watched states."""
        html = _landing_html()
        # Portfolio link should still be in the beta state
        assert 'href="/portfolio"' in html
