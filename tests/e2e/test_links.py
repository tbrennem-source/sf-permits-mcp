"""Dead link spider — crawls internal links and verifies none return 404/500.

Extended from Sprint 67-C:
- Page cap: 200 (up from 100)
- Authenticated admin crawl covers /admin/* pages
- Response time tracking: flags pages >5s
- Separates internal vs external links (does not follow external)
- Summary output at end of crawl
"""

import time
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser

import pytest

from web.app import app, _rate_buckets


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


def _login_admin(client, email="spider-admin@test.com"):
    """Login helper for admin crawling."""
    import src.db as db_mod
    if db_mod.BACKEND == "duckdb":
        db_mod.init_user_schema()
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    conn = db_mod.get_connection()
    try:
        conn.execute(
            "UPDATE users SET is_admin = TRUE WHERE user_id = ?",
            [user["user_id"]],
        )
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception:
        pass
    finally:
        if hasattr(db_mod, "release_connection"):
            db_mod.release_connection(conn)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


# ---------------------------------------------------------------------------
# Skip patterns
# ---------------------------------------------------------------------------

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
    "/api/",              # JSON API endpoints
    "/project/",          # requires valid project_id
)

SKIP_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".xml", ".json")


def _is_external(url: str) -> bool:
    """Check if URL is external (different host)."""
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in ("", "http", "https"):
        return True
    if parsed.netloc and parsed.netloc not in ("", "localhost", "localhost:5001"):
        return True
    if url.startswith("mailto:") or url.startswith("javascript:") or url.startswith("tel:"):
        return True
    return False


def should_crawl(url: str) -> bool:
    """Return True if this URL should be visited by the spider."""
    if _is_external(url):
        return False

    parsed = urlparse(url)
    path = parsed.path

    if not path or path == "#":
        return False
    if any(path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False

    return True


# ---------------------------------------------------------------------------
# Spider core
# ---------------------------------------------------------------------------

def _crawl(client, seeds: list[str], max_pages: int = 200):
    """Crawl pages starting from seeds. Returns (visited, errors, external, slow)."""
    visited: set[str] = set()
    to_visit: list[str] = list(seeds)
    errors: list[tuple[str, int, str]] = []       # (url, status, referrer)
    external_links: set[str] = set()
    slow_pages: list[tuple[str, float]] = []       # (url, seconds)

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        path = urlparse(url).path or url

        if path in visited:
            continue
        visited.add(path)

        start_time = time.time()
        rv = client.get(url, follow_redirects=True)
        elapsed = time.time() - start_time

        if elapsed > 5.0:
            slow_pages.append((url, elapsed))

        if rv.status_code in (404, 500, 502, 503):
            errors.append((url, rv.status_code, "spider"))
            continue

        content_type = rv.content_type or ""
        if "html" not in content_type:
            continue

        html = rv.data.decode("utf-8", errors="replace")
        links = extract_links(html)

        for link in links:
            if _is_external(link):
                external_links.add(link)
                continue

            resolved = urljoin(url, link)
            resolved_path = urlparse(resolved).path

            if should_crawl(resolved) and resolved_path not in visited:
                to_visit.append(resolved_path)

    return visited, errors, external_links, slow_pages


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeadLinkSpider:
    """Crawl internal links and verify none return 404/500."""

    MAX_PAGES = 200

    def test_no_dead_links_anonymous(self, client):
        """Crawl from / as anonymous user. No 404s or 500s."""
        visited, errors, external, slow = _crawl(
            client, ["/"], max_pages=self.MAX_PAGES,
        )

        # Print summary
        print(f"\n--- Anonymous Spider Summary ---")
        print(f"Pages crawled: {len(visited)}")
        print(f"External links found: {len(external)}")
        print(f"Slow pages (>5s): {len(slow)}")
        if slow:
            for url, secs in slow:
                print(f"  {secs:.1f}s {url}")
        print(f"Broken links: {len(errors)}")

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

        visited, errors, external, slow = _crawl(
            client,
            ["/", "/account", "/portfolio", "/brief"],
            max_pages=self.MAX_PAGES,
        )

        print(f"\n--- Authenticated Spider Summary ---")
        print(f"Pages crawled: {len(visited)}")
        print(f"External links found: {len(external)}")
        print(f"Slow pages (>5s): {len(slow)}")
        if slow:
            for url, secs in slow:
                print(f"  {secs:.1f}s {url}")
        print(f"Broken links: {len(errors)}")

        assert len(visited) > 3, "Authenticated spider should visit at least 4 pages"

        if errors:
            error_summary = "\n".join(
                f"  {status} {url}" for url, status, _ in errors
            )
            pytest.fail(
                f"Dead links found ({len(errors)}):\n{error_summary}\n"
                f"Visited {len(visited)} pages total."
            )

    def test_no_dead_links_admin(self, client):
        """Crawl /admin/* as admin user. No 404s or 500s."""
        _login_admin(client)

        admin_seeds = [
            "/admin/ops",
            "/admin/feedback",
            "/admin/pipeline",
            "/admin/costs",
            "/admin/beta-requests",
            "/admin/activity",
            "/admin/sources",
            "/admin/regulatory-watch",
        ]

        visited, errors, external, slow = _crawl(
            client, admin_seeds, max_pages=self.MAX_PAGES,
        )

        print(f"\n--- Admin Spider Summary ---")
        print(f"Pages crawled: {len(visited)}")
        print(f"External links found: {len(external)}")
        print(f"Slow pages (>5s): {len(slow)}")
        if slow:
            for url, secs in slow:
                print(f"  {secs:.1f}s {url}")
        print(f"Broken links: {len(errors)}")

        assert len(visited) > 1, "Admin spider should visit at least 2 pages"

        if errors:
            error_summary = "\n".join(
                f"  {status} {url}" for url, status, _ in errors
            )
            pytest.fail(
                f"Dead links found ({len(errors)}):\n{error_summary}\n"
                f"Visited {len(visited)} pages total."
            )

    def test_no_slow_pages(self, client):
        """No page should take >5 seconds to respond."""
        visited, errors, external, slow = _crawl(
            client, ["/"], max_pages=50,
        )

        if slow:
            slow_summary = "\n".join(
                f"  {secs:.1f}s {url}" for url, secs in slow
            )
            pytest.fail(
                f"Slow pages found ({len(slow)}):\n{slow_summary}"
            )


class TestSpiderCoverage:
    """Verify the spider finds expected pages."""

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

    def test_methodology_page_accessible(self, client):
        """Methodology page returns 200."""
        rv = client.get("/methodology")
        assert rv.status_code == 200
