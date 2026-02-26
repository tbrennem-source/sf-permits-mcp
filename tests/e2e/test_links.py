"""Sprint 67-C: Dead link spider using Flask test client.

Crawls from / and follows all internal links, verifying each returns
a successful response (200 or 302). Caps at 100 pages to prevent
infinite crawl.

Does NOT follow:
- External links (different host)
- Links to static assets (CSS, JS, images)
- Links with # anchors only
- POST-only endpoints
"""

import os
import sys
import re
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# HTML link extractor
# ---------------------------------------------------------------------------

class LinkExtractor(HTMLParser):
    """Extract href values from <a> tags."""

    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def extract_links(html: str) -> list[str]:
    """Extract all href values from HTML."""
    parser = LinkExtractor()
    parser.feed(html)
    return parser.links


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def _login(client, email="spider-test@test.com"):
    """Login helper for authenticated crawling."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Skip patterns
# ---------------------------------------------------------------------------

# Paths to skip crawling (auth-only, external, or known-heavy)
SKIP_PREFIXES = (
    "/static/",
    "/auth/logout",
    "/auth/verify/",
    "/cron/",
    "/admin/feedback/",   # POST-heavy admin actions
    "/watch/",            # POST-only watch management
    "/plan-images/",      # requires valid session_id
    "/plan-session/",     # requires valid session_id
    "/plan-jobs/",        # requires valid job_id
    "/analysis/",         # requires valid analysis_id
    "/report/",           # requires valid block/lot
    "/portfolio/timeline/",  # requires valid block/lot
    "/dashboard/bottlenecks/station/",  # JSON-only endpoint
    "/email/",            # email endpoints
    "/onboarding/",       # POST-only
)

SKIP_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".xml", ".json")


def should_crawl(url: str) -> bool:
    """Return True if this URL should be visited by the spider."""
    parsed = urlparse(url)

    # Skip external links
    if parsed.scheme and parsed.scheme not in ("", "http", "https"):
        return False
    if parsed.netloc and parsed.netloc not in ("", "localhost", "localhost:5001"):
        return False

    path = parsed.path

    # Skip anchor-only links
    if not path or path == "#":
        return False

    # Skip static assets
    if any(path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False

    # Skip known skip prefixes
    if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False

    # Skip mailto and javascript links
    if url.startswith("mailto:") or url.startswith("javascript:"):
        return False

    return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeadLinkSpider:
    """Crawl internal links and verify none return 404/500."""

    MAX_PAGES = 100

    def test_no_dead_links_anonymous(self, client):
        """Crawl from / as anonymous user. No 404s or 500s."""
        visited: set[str] = set()
        to_visit: list[str] = ["/"]
        errors: list[tuple[str, int, str]] = []  # (url, status, referrer)

        while to_visit and len(visited) < self.MAX_PAGES:
            url = to_visit.pop(0)
            path = urlparse(url).path or url

            if path in visited:
                continue
            visited.add(path)

            rv = client.get(url, follow_redirects=True)

            if rv.status_code in (404, 500, 502, 503):
                errors.append((url, rv.status_code, "spider"))
                continue

            # Only parse HTML responses for more links
            content_type = rv.content_type or ""
            if "html" not in content_type:
                continue

            html = rv.data.decode("utf-8", errors="replace")
            links = extract_links(html)

            for link in links:
                # Resolve relative URLs
                resolved = urljoin(url, link)
                resolved_path = urlparse(resolved).path

                if should_crawl(resolved) and resolved_path not in visited:
                    to_visit.append(resolved_path)

        assert len(visited) > 1, "Spider should have visited at least 2 pages"

        if errors:
            error_summary = "\n".join(
                f"  {status} {url}" for url, status, _ in errors
            )
            pytest.fail(
                f"Dead links found ({len(errors)}):\n{error_summary}\n"
                f"Visited {len(visited)} pages total."
            )

    def test_no_dead_links_authenticated(self, client):
        """Crawl from / as authenticated user. No 404s or 500s."""
        _login(client)

        visited: set[str] = set()
        to_visit: list[str] = ["/", "/account", "/portfolio"]
        errors: list[tuple[str, int]] = []

        while to_visit and len(visited) < self.MAX_PAGES:
            url = to_visit.pop(0)
            path = urlparse(url).path or url

            if path in visited:
                continue
            visited.add(path)

            rv = client.get(url, follow_redirects=True)

            if rv.status_code in (404, 500, 502, 503):
                errors.append((url, rv.status_code))
                continue

            content_type = rv.content_type or ""
            if "html" not in content_type:
                continue

            html = rv.data.decode("utf-8", errors="replace")
            links = extract_links(html)

            for link in links:
                resolved = urljoin(url, link)
                resolved_path = urlparse(resolved).path

                if should_crawl(resolved) and resolved_path not in visited:
                    to_visit.append(resolved_path)

        assert len(visited) > 3, "Authenticated spider should visit at least 4 pages"

        if errors:
            error_summary = "\n".join(
                f"  {status} {url}" for url, status in errors
            )
            pytest.fail(
                f"Dead links found ({len(errors)}):\n{error_summary}\n"
                f"Visited {len(visited)} pages total."
            )


class TestSpiderCoverage:
    """Verify the spider found expected pages."""

    def test_spider_visits_login(self, client):
        """Spider should reach /auth/login from landing page."""
        rv = client.get("/")
        html = rv.data.decode()
        links = extract_links(html)
        paths = [urlparse(l).path for l in links]
        assert "/auth/login" in paths, (
            f"/auth/login not linked from landing page. Found links: {paths}"
        )

    def test_spider_visits_search(self, client):
        """Landing page should have a search form action."""
        rv = client.get("/")
        html = rv.data.decode()
        assert "/search" in html
