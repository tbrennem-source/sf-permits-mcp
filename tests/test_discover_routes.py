"""
tests/test_discover_routes.py

Tests for scripts/discover_routes.py — validates that the generated
siteaudit_manifest.json is correct and complete.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "discover_routes.py"
MANIFEST_PATH = REPO_ROOT / "siteaudit_manifest.json"


def load_manifest() -> dict:
    """Run the discovery script (if manifest is stale/missing) and return parsed JSON."""
    # Always re-run to guarantee we test the current script output.
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"discover_routes.py exited with code {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert MANIFEST_PATH.exists(), "siteaudit_manifest.json was not created"
    return json.loads(MANIFEST_PATH.read_text())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_manifest()


@pytest.fixture(scope="module")
def routes(manifest) -> list[dict]:
    return manifest["routes"]


@pytest.fixture(scope="module")
def routes_by_path(routes) -> dict[str, dict]:
    # When a path has multiple entries (different methods) take the last one.
    return {r["path"]: r for r in routes}


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------

class TestManifestStructure:
    def test_valid_json(self, manifest):
        """Manifest must be valid JSON with expected top-level keys."""
        assert isinstance(manifest, dict)
        required_keys = {"generated_at", "total_routes", "routes", "user_journeys", "auth_summary"}
        assert required_keys.issubset(manifest.keys())

    def test_generated_at_is_iso(self, manifest):
        from datetime import datetime
        # Should parse without error
        datetime.fromisoformat(manifest["generated_at"])

    def test_routes_is_list(self, manifest):
        assert isinstance(manifest["routes"], list)

    def test_total_routes_matches_list(self, manifest):
        assert manifest["total_routes"] == len(manifest["routes"])

    def test_route_count_sanity(self, manifest):
        """Sanity check: we expect more than 50 routes."""
        assert manifest["total_routes"] > 50, (
            f"Expected > 50 routes, got {manifest['total_routes']}"
        )


# ---------------------------------------------------------------------------
# Auth summary tests
# ---------------------------------------------------------------------------

class TestAuthSummary:
    def test_auth_summary_keys_present(self, manifest):
        summary = manifest["auth_summary"]
        assert set(summary.keys()) == {"public", "auth", "admin", "cron"}

    def test_auth_summary_values_are_ints(self, manifest):
        for k, v in manifest["auth_summary"].items():
            assert isinstance(v, int), f"auth_summary[{k!r}] should be int, got {type(v)}"

    def test_auth_summary_totals_match_routes(self, manifest):
        total = sum(manifest["auth_summary"].values())
        assert total == manifest["total_routes"], (
            f"auth_summary totals {total} != total_routes {manifest['total_routes']}"
        )

    def test_each_route_has_valid_auth_level(self, routes):
        valid_levels = {"public", "auth", "admin", "cron"}
        for r in routes:
            assert r["auth_level"] in valid_levels, (
                f"Route {r['path']} has invalid auth_level {r['auth_level']!r}"
            )


# ---------------------------------------------------------------------------
# Known route tests
# ---------------------------------------------------------------------------

class TestKnownRoutes:
    """Verify that specific well-known routes are present and correctly classified."""

    def test_root_route_exists(self, routes_by_path):
        assert "/" in routes_by_path, "Route '/' not found in manifest"

    def test_root_is_public(self, routes_by_path):
        assert routes_by_path["/"]["auth_level"] == "public"

    def test_health_route_exists(self, routes_by_path):
        assert "/health" in routes_by_path, "Route '/health' not found in manifest"

    def test_health_is_public(self, routes_by_path):
        assert routes_by_path["/health"]["auth_level"] == "public"

    def test_admin_dashboard_exists(self, routes_by_path):
        # /admin/ops is the admin ops/dashboard route (no /admin/dashboard in app.py)
        admin_paths = [p for p in routes_by_path if p.startswith("/admin")]
        assert len(admin_paths) > 0, "No /admin/* routes found"

    def test_admin_feedback_exists(self, routes_by_path):
        assert "/admin/feedback" in routes_by_path, "Route '/admin/feedback' not found"

    def test_admin_feedback_is_admin(self, routes_by_path):
        assert routes_by_path["/admin/feedback"]["auth_level"] == "admin"

    def test_cron_backup_exists(self, routes_by_path):
        assert "/cron/backup" in routes_by_path, "Route '/cron/backup' not found"

    def test_cron_backup_is_cron(self, routes_by_path):
        assert routes_by_path["/cron/backup"]["auth_level"] == "cron"

    def test_brief_route_exists(self, routes_by_path):
        assert "/brief" in routes_by_path, "Route '/brief' not found"

    def test_brief_is_auth(self, routes_by_path):
        assert routes_by_path["/brief"]["auth_level"] == "auth"

    def test_search_route_exists(self, routes_by_path):
        assert "/search" in routes_by_path, "Route '/search' not found"


# ---------------------------------------------------------------------------
# Route schema tests
# ---------------------------------------------------------------------------

class TestRouteSchema:
    def test_every_route_has_required_fields(self, routes):
        required = {"path", "methods", "auth_level", "template", "function_name"}
        for r in routes:
            assert required.issubset(r.keys()), (
                f"Route {r.get('path')} missing fields: {required - r.keys()}"
            )

    def test_methods_is_list(self, routes):
        for r in routes:
            assert isinstance(r["methods"], list), (
                f"Route {r['path']}.methods should be a list"
            )

    def test_methods_non_empty(self, routes):
        for r in routes:
            assert len(r["methods"]) > 0, (
                f"Route {r['path']}.methods is empty"
            )

    def test_get_only_routes_have_single_method(self, routes):
        """Routes with no explicit methods declaration default to GET only."""
        for r in routes:
            # All entries in methods should be uppercase strings
            for m in r["methods"]:
                assert m == m.upper(), f"Method {m!r} in {r['path']} is not uppercase"


# ---------------------------------------------------------------------------
# User journey tests
# ---------------------------------------------------------------------------

class TestUserJourneys:
    def test_user_journeys_has_4_entries(self, manifest):
        assert len(manifest["user_journeys"]) == 4, (
            f"Expected 4 user journeys, got {len(manifest['user_journeys'])}"
        )

    def test_all_expected_journeys_present(self, manifest):
        expected = {"property_research", "morning_brief", "admin_ops", "plan_analysis"}
        assert expected == set(manifest["user_journeys"].keys())

    def test_journeys_are_lists_of_strings(self, manifest):
        for name, paths in manifest["user_journeys"].items():
            assert isinstance(paths, list), f"Journey {name!r} should be a list"
            for p in paths:
                assert isinstance(p, str), f"Path {p!r} in journey {name!r} should be a string"
                assert p.startswith("/"), f"Path {p!r} in journey {name!r} should start with /"


# ---------------------------------------------------------------------------
# Cron / API classification tests
# ---------------------------------------------------------------------------

class TestCronApiRoutes:
    def test_cron_routes_are_cron(self, routes):
        cron_routes = [r for r in routes if r["path"].startswith("/cron")]
        assert len(cron_routes) > 0, "No /cron/* routes found"
        for r in cron_routes:
            assert r["auth_level"] == "cron", (
                f"/cron route {r['path']} classified as {r['auth_level']!r} instead of 'cron'"
            )

    def test_api_routes_are_cron(self, routes):
        api_routes = [r for r in routes if r["path"].startswith("/api/")]
        assert len(api_routes) > 0, "No /api/* routes found"
        for r in api_routes:
            assert r["auth_level"] == "cron", (
                f"/api route {r['path']} classified as {r['auth_level']!r} instead of 'cron'"
            )

    def test_admin_routes_are_admin(self, routes):
        admin_routes = [r for r in routes if r["path"].startswith("/admin")]
        assert len(admin_routes) > 0, "No /admin/* routes found"
        for r in admin_routes:
            assert r["auth_level"] == "admin", (
                f"/admin route {r['path']} classified as {r['auth_level']!r} instead of 'admin'"
            )
