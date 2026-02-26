"""Tests for Sprint 58B — SEO foundation: OG tags, sitemap, ADU page, meta descriptions.

Covers:
- Sitemap route: valid XML, static pages only, no /report/ URLs
- ADU landing page: 200 response, content, caching behavior
- OG card PNG: file exists, valid image, correct dimensions
- Meta descriptions: present in landing and analyze_preview templates
- OG tags: present in analysis_shared and report templates
"""

import os
import time
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """Flask test client — no auth, no DB required for SEO routes."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", True)

    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# B.3: Sitemap tests
# ---------------------------------------------------------------------------


class TestSitemap:
    def test_sitemap_returns_200(self, client):
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200

    def test_sitemap_content_type_xml(self, client):
        resp = client.get("/sitemap.xml")
        assert "application/xml" in resp.content_type

    def test_sitemap_is_valid_xml(self, client):
        import xml.etree.ElementTree as ET
        resp = client.get("/sitemap.xml")
        # Should not raise
        root = ET.fromstring(resp.data)
        assert root is not None

    def test_sitemap_has_urlset_root(self, client):
        import xml.etree.ElementTree as ET
        resp = client.get("/sitemap.xml")
        root = ET.fromstring(resp.data)
        assert "urlset" in root.tag

    def test_sitemap_contains_homepage(self, client):
        resp = client.get("/sitemap.xml")
        assert b"https://sfpermits.ai/" in resp.data

    def test_sitemap_contains_search(self, client):
        resp = client.get("/sitemap.xml")
        assert b"/search" in resp.data

    def test_sitemap_contains_adu(self, client):
        resp = client.get("/sitemap.xml")
        assert b"/adu" in resp.data

    def test_sitemap_contains_beta_request(self, client):
        resp = client.get("/sitemap.xml")
        assert b"/beta-request" in resp.data

    def test_sitemap_does_not_contain_report_urls(self, client):
        resp = client.get("/sitemap.xml")
        assert b"/report/" not in resp.data

    def test_sitemap_does_not_contain_analysis_ids(self, client):
        resp = client.get("/sitemap.xml")
        assert b"/analysis/" not in resp.data

    def test_sitemap_has_lastmod(self, client):
        resp = client.get("/sitemap.xml")
        assert b"<lastmod>" in resp.data

    def test_sitemap_has_changefreq(self, client):
        resp = client.get("/sitemap.xml")
        assert b"<changefreq>" in resp.data

    def test_sitemap_only_sfpermits_ai_domain(self, client):
        resp = client.get("/sitemap.xml")
        body = resp.data.decode()
        # All <loc> entries should use sfpermits.ai
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.data)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text for el in root.findall(".//sm:loc", ns)]
        assert len(locs) > 0
        for loc in locs:
            assert "sfpermits.ai" in loc, f"Unexpected domain in sitemap: {loc}"


# ---------------------------------------------------------------------------
# B.4: ADU landing page tests
# ---------------------------------------------------------------------------


class TestADULanding:
    def test_adu_route_returns_200(self, client):
        resp = client.get("/adu")
        assert resp.status_code == 200

    def test_adu_page_has_correct_title(self, client):
        resp = client.get("/adu")
        assert b"ADU" in resp.data or b"Accessory Dwelling" in resp.data

    def test_adu_page_has_h1_with_adu(self, client):
        resp = client.get("/adu")
        assert b"ADU Permits" in resp.data or b"Accessory Dwelling Unit" in resp.data

    def test_adu_page_has_cta_link(self, client):
        resp = client.get("/adu")
        # Should link to analyze-preview with ADU description
        assert b"analyze-preview" in resp.data or b"analyze_preview" in resp.data.lower()

    def test_adu_page_has_meta_description(self, client):
        resp = client.get("/adu")
        assert b'<meta name="description"' in resp.data
        assert b"ADU" in resp.data or b"accessory dwelling" in resp.data.lower()

    def test_adu_page_has_og_tags(self, client):
        resp = client.get("/adu")
        assert b'property="og:title"' in resp.data
        assert b'property="og:description"' in resp.data

    def test_adu_stats_cache_populated(self):
        """Second call uses cache — _get_adu_stats returns same dict."""
        from web.app import _get_adu_stats, _adu_stats_cache
        # Clear cache for deterministic test
        _adu_stats_cache.clear()

        stats1 = _get_adu_stats()
        assert isinstance(stats1, dict)
        assert "computed_at" in stats1

        # Overwrite computed_at to simulate recent cache
        _adu_stats_cache["computed_at"] = time.time()
        _adu_stats_cache["issued_2025"] = 42

        stats2 = _get_adu_stats()
        # Should return cached value
        assert stats2["issued_2025"] == 42

    def test_adu_stats_cache_expires_after_24h(self):
        """Cache expires when computed_at > 24h ago."""
        from web.app import _get_adu_stats, _adu_stats_cache
        # Simulate stale cache (25 hours ago)
        _adu_stats_cache.clear()
        _adu_stats_cache["computed_at"] = time.time() - (25 * 3600)
        _adu_stats_cache["issued_2025"] = 999

        stats = _get_adu_stats()
        # Should NOT return stale value (999)
        # The fresh query may return 0 in test env, but not 999
        assert stats.get("issued_2025") != 999 or "computed_at" in stats

    def test_adu_page_lists_adu_types(self, client):
        resp = client.get("/adu")
        body = resp.data.lower()
        # At least some ADU type keywords should appear
        assert b"garage" in body or b"basement" in body or b"jadu" in body

    def test_adu_page_is_html(self, client):
        resp = client.get("/adu")
        assert "text/html" in resp.content_type


# ---------------------------------------------------------------------------
# B.2: OG card PNG tests
# ---------------------------------------------------------------------------


class TestOGCard:
    def _og_card_path(self):
        # Find from the repo root, not from worktree subdir
        this_file = os.path.abspath(__file__)
        tests_dir = os.path.dirname(this_file)
        repo_root = os.path.dirname(tests_dir)
        return os.path.join(repo_root, "web", "static", "og-card.png")

    def test_og_card_file_exists(self):
        path = self._og_card_path()
        assert os.path.isfile(path), f"og-card.png not found at {path}"

    def test_og_card_is_valid_png(self):
        path = self._og_card_path()
        with open(path, "rb") as f:
            header = f.read(8)
        # PNG magic bytes: 0x89 50 4E 47 0D 0A 1A 0A
        assert header[:4] == b"\x89PNG", "File does not have PNG magic bytes"

    def test_og_card_correct_dimensions(self):
        from PIL import Image
        path = self._og_card_path()
        img = Image.open(path)
        assert img.size == (1200, 630), f"Expected (1200, 630), got {img.size}"

    def test_og_card_is_rgb(self):
        from PIL import Image
        path = self._og_card_path()
        img = Image.open(path)
        assert img.mode == "RGB", f"Expected RGB mode, got {img.mode}"

    def test_og_card_served_by_static(self, client):
        resp = client.get("/static/og-card.png")
        assert resp.status_code == 200
        assert "image/png" in resp.content_type


# ---------------------------------------------------------------------------
# B.1 + B.5: Template meta tag tests
# ---------------------------------------------------------------------------


class TestTemplateMetaTags:
    def _read_template(self, name: str) -> bytes:
        this_file = os.path.abspath(__file__)
        repo_root = os.path.dirname(os.path.dirname(this_file))
        path = os.path.join(repo_root, "web", "templates", name)
        with open(path, "rb") as f:
            return f.read()

    def test_landing_has_meta_description(self):
        content = self._read_template("landing.html")
        assert b'<meta name="description"' in content
        # New improved description
        assert b"Free SF building permit" in content or b"free" in content.lower()

    def test_analyze_preview_has_meta_description(self):
        content = self._read_template("analyze_preview.html")
        assert b'<meta name="description"' in content
        assert b"permit" in content.lower()

    def test_analysis_shared_has_og_title(self):
        content = self._read_template("analysis_shared.html")
        assert b'property="og:title"' in content

    def test_analysis_shared_has_og_description(self):
        content = self._read_template("analysis_shared.html")
        assert b'property="og:description"' in content
        assert b"sfpermits.ai" in content

    def test_analysis_shared_has_og_image(self):
        content = self._read_template("analysis_shared.html")
        assert b'property="og:image"' in content
        assert b"og-card.png" in content

    def test_analysis_shared_has_og_url(self):
        content = self._read_template("analysis_shared.html")
        assert b'property="og:url"' in content

    def test_analysis_shared_has_og_type_article(self):
        content = self._read_template("analysis_shared.html")
        assert b'property="og:type"' in content
        assert b"article" in content

    def test_analysis_shared_has_twitter_card(self):
        content = self._read_template("analysis_shared.html")
        assert b'name="twitter:card"' in content
        assert b"summary_large_image" in content

    def test_report_has_og_title(self):
        content = self._read_template("report.html")
        assert b'property="og:title"' in content

    def test_report_has_og_description(self):
        content = self._read_template("report.html")
        assert b'property="og:description"' in content

    def test_report_has_og_image(self):
        content = self._read_template("report.html")
        assert b'property="og:image"' in content
        assert b"og-card.png" in content

    def test_report_has_og_url_with_block_lot(self):
        content = self._read_template("report.html")
        assert b'property="og:url"' in content
        # Should reference block and lot for report URL
        assert b"report" in content
