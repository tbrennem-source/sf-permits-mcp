"""Sprint 69 Session 4: Portfolio Artifacts + PWA + Showcase Polish tests."""

import json
import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Task 1: Portfolio Brief
# ---------------------------------------------------------------------------

class TestPortfolioBrief:
    brief_path = ROOT / "docs" / "portfolio-brief.md"

    def test_portfolio_brief_exists(self):
        assert self.brief_path.exists(), "docs/portfolio-brief.md must exist"

    def test_portfolio_brief_word_count(self):
        text = self.brief_path.read_text()
        word_count = len(text.split())
        assert word_count > 500, f"Portfolio brief has {word_count} words, expected >500"

    def test_portfolio_brief_mentions_entity_resolution(self):
        text = self.brief_path.read_text()
        assert "entity resolution" in text.lower(), "Portfolio brief must mention entity resolution"

    def test_portfolio_brief_contains_tim_brenneman(self):
        text = self.brief_path.read_text()
        assert "Tim Brenneman" in text, "Portfolio brief must contain 'Tim Brenneman'"

    def test_portfolio_brief_contains_test_count(self):
        """Portfolio brief should reference a test count in the 3000+ range."""
        text = self.brief_path.read_text()
        # Look for a number in the 3,000-4,000 range (with or without comma)
        import re
        matches = re.findall(r"3[,.]?\d{3}", text)
        assert len(matches) > 0, "Portfolio brief must contain a test count in the 3,000+ range"

    def test_portfolio_brief_mentions_mcp_tools(self):
        text = self.brief_path.read_text()
        assert "MCP tool" in text, "Portfolio brief must mention MCP tools"

    def test_portfolio_brief_mentions_dforge(self):
        text = self.brief_path.read_text()
        assert "dforge" in text, "Portfolio brief must mention dforge"


# ---------------------------------------------------------------------------
# Task 2: LinkedIn Update
# ---------------------------------------------------------------------------

class TestLinkedInUpdate:
    linkedin_path = ROOT / "docs" / "linkedin-update.md"

    def test_linkedin_update_exists(self):
        assert self.linkedin_path.exists(), "docs/linkedin-update.md must exist"

    def test_linkedin_has_headline(self):
        text = self.linkedin_path.read_text()
        assert "## Headline" in text, "LinkedIn update must have a Headline section"

    def test_linkedin_has_about(self):
        text = self.linkedin_path.read_text()
        assert "## About" in text, "LinkedIn update must have an About section"

    def test_linkedin_has_experience(self):
        text = self.linkedin_path.read_text()
        assert "Experience" in text, "LinkedIn update must have an Experience section"


# ---------------------------------------------------------------------------
# Task 3: dforge Public README
# ---------------------------------------------------------------------------

class TestDforgeReadme:
    readme_path = ROOT / "docs" / "dforge-public-readme.md"

    def test_dforge_readme_exists(self):
        assert self.readme_path.exists(), "docs/dforge-public-readme.md must exist"

    def test_dforge_readme_mentions_dforge(self):
        text = self.readme_path.read_text()
        assert "dforge" in text, "dforge README must mention dforge"

    def test_dforge_readme_mentions_behavioral_scenarios(self):
        text = self.readme_path.read_text()
        assert "behavioral scenario" in text.lower(), \
            "dforge README must mention behavioral scenarios"

    def test_dforge_readme_mentions_black_box(self):
        text = self.readme_path.read_text()
        assert "Black Box" in text, "dforge README must mention Black Box Protocol"


# ---------------------------------------------------------------------------
# Task 4: Model Release Probes
# ---------------------------------------------------------------------------

class TestModelReleaseProbes:
    probes_path = ROOT / "docs" / "model-release-probes.md"

    def test_probes_file_exists(self):
        assert self.probes_path.exists(), "docs/model-release-probes.md must exist"

    def test_probes_has_minimum_count(self):
        """Must have at least 10 probe entries."""
        text = self.probes_path.read_text()
        # Count probe headers (### Probe N.N:)
        import re
        probes = re.findall(r"### Probe \d+\.\d+", text)
        assert len(probes) >= 10, f"Found {len(probes)} probes, expected >=10"

    def test_probes_cover_all_categories(self):
        text = self.probes_path.read_text()
        categories = [
            "Permit Prediction",
            "Vision Analysis",
            "Multi-Source Synthesis",
            "Entity Reasoning",
            "Specification Quality",
            "Domain Knowledge",
        ]
        for cat in categories:
            assert cat in text, f"Probes must cover category: {cat}"


# ---------------------------------------------------------------------------
# Task 5: PWA Manifest + Icons
# ---------------------------------------------------------------------------

class TestPWAManifest:
    manifest_path = ROOT / "web" / "static" / "manifest.json"
    icon_192_path = ROOT / "web" / "static" / "icon-192.png"
    icon_512_path = ROOT / "web" / "static" / "icon-512.png"

    def test_manifest_exists(self):
        assert self.manifest_path.exists(), "web/static/manifest.json must exist"

    def test_manifest_valid_json(self):
        with open(self.manifest_path) as f:
            data = json.load(f)
        assert "name" in data
        assert "theme_color" in data

    def test_manifest_theme_color(self):
        with open(self.manifest_path) as f:
            data = json.load(f)
        assert data["theme_color"] == "#22D3EE", \
            f"theme_color should be #22D3EE, got {data['theme_color']}"

    def test_manifest_has_icons(self):
        with open(self.manifest_path) as f:
            data = json.load(f)
        assert "icons" in data
        assert len(data["icons"]) >= 2

    def test_icon_192_exists(self):
        assert self.icon_192_path.exists(), "web/static/icon-192.png must exist"

    def test_icon_512_exists(self):
        assert self.icon_512_path.exists(), "web/static/icon-512.png must exist"


# ---------------------------------------------------------------------------
# Task 6: robots.txt
# ---------------------------------------------------------------------------

class TestRobotsTxt:
    def _get_robots_txt(self):
        """Read the ROBOTS_TXT constant from app.py."""
        app_path = ROOT / "web" / "app.py"
        text = app_path.read_text()
        # Extract the ROBOTS_TXT string
        start = text.index('ROBOTS_TXT = """\\\n') + len('ROBOTS_TXT = """\\\n')
        end = text.index('"""', start)
        return text[start:end]

    def test_robots_disallows_admin(self):
        robots = self._get_robots_txt()
        assert "Disallow: /admin/" in robots

    def test_robots_disallows_cron(self):
        robots = self._get_robots_txt()
        assert "Disallow: /cron/" in robots

    def test_robots_disallows_api(self):
        robots = self._get_robots_txt()
        assert "Disallow: /api/" in robots

    def test_robots_disallows_auth(self):
        robots = self._get_robots_txt()
        assert "Disallow: /auth/" in robots

    def test_robots_allows_root(self):
        robots = self._get_robots_txt()
        assert "Allow: /" in robots

    def test_robots_has_sitemap(self):
        robots = self._get_robots_txt()
        assert "Sitemap:" in robots
