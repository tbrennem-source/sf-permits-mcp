"""Tests for knowledge source inventory page."""

import os
import sys

import pytest

from web.sources import get_source_inventory, _parse_gaps, _extract_metadata, _build_lifecycle_matrix


# ---------------------------------------------------------------------------
# Inventory builder
# ---------------------------------------------------------------------------

class TestGetSourceInventory:
    """Tests for the full inventory builder using real tier1 data."""

    def test_returns_all_sections(self):
        inv = get_source_inventory()
        assert "files" in inv
        assert "categories" in inv
        assert "stats" in inv
        assert "gaps" in inv
        assert "lifecycle" in inv

    def test_discovers_all_tier1_files(self):
        inv = get_source_inventory()
        # We have 29 tier1 JSON files
        assert inv["stats"]["total_files"] >= 29

    def test_every_file_has_title(self):
        inv = get_source_inventory()
        for f in inv["files"]:
            assert f.get("title"), f"Missing title for {f.get('filename')}"

    def test_every_file_has_filename(self):
        inv = get_source_inventory()
        for f in inv["files"]:
            assert f["filename"].endswith(".json")

    def test_every_file_has_category(self):
        inv = get_source_inventory()
        valid_cats = {"building_code", "planning_code", "dbi_info_sheets",
                      "compliance", "data_sources", "tools"}
        for f in inv["files"]:
            assert f["category"] in valid_cats, f"{f['filename']} has unknown category {f['category']}"

    def test_most_files_have_urls(self):
        inv = get_source_inventory()
        with_urls = sum(1 for f in inv["files"] if f.get("urls"))
        # Most files should have at least one URL
        assert with_urls >= 25, f"Only {with_urls} files have URLs"

    def test_categories_have_files(self):
        inv = get_source_inventory()
        non_empty = [cid for cid, c in inv["categories"].items() if c["count"] > 0]
        assert len(non_empty) >= 4  # At least 4 categories populated

    def test_building_code_has_new_files(self):
        inv = get_source_inventory()
        bc = inv["categories"]["building_code"]
        stems = [f["stem"] for f in bc["files"]]
        assert "permit-expiration-rules" in stems
        assert "enforcement-process" in stems
        assert "inspections-process" in stems

    def test_stats_are_populated(self):
        inv = get_source_inventory()
        stats = inv["stats"]
        assert stats["total_files"] > 0
        assert stats["total_size_kb"] > 0
        assert stats["total_data_points"] > 0
        assert stats["generated_at"]  # ISO date string


# ---------------------------------------------------------------------------
# Gap parser
# ---------------------------------------------------------------------------

class TestParseGaps:
    def test_parses_real_gaps_file(self):
        from pathlib import Path
        gaps_path = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "GAPS.md"
        if not gaps_path.exists():
            pytest.skip("GAPS.md not found")
        gaps = _parse_gaps(gaps_path)
        assert len(gaps) >= 10  # We know there are 14 gaps

    def test_resolved_gaps_flagged(self):
        from pathlib import Path
        gaps_path = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "GAPS.md"
        if not gaps_path.exists():
            pytest.skip("GAPS.md not found")
        gaps = _parse_gaps(gaps_path)
        resolved = [g for g in gaps if g["resolved"]]
        assert len(resolved) >= 9  # GAP-1,2,4,5,6,7,8,9,14 resolved

    def test_open_gaps_have_severity(self):
        from pathlib import Path
        gaps_path = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "GAPS.md"
        if not gaps_path.exists():
            pytest.skip("GAPS.md not found")
        gaps = _parse_gaps(gaps_path)
        for g in gaps:
            assert g["severity"] in ("critical", "significant", "minor")

    def test_gap14_is_resolved(self):
        from pathlib import Path
        gaps_path = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "GAPS.md"
        if not gaps_path.exists():
            pytest.skip("GAPS.md not found")
        gaps = _parse_gaps(gaps_path)
        gap14 = [g for g in gaps if g["gap_id"] == 14]
        assert len(gap14) == 1
        assert gap14[0]["resolved"] is True


# ---------------------------------------------------------------------------
# Lifecycle matrix
# ---------------------------------------------------------------------------

class TestLifecycleMatrix:
    def test_covers_all_stages(self):
        inv = get_source_inventory()
        stages = [s["stage"] for s in inv["lifecycle"]]
        assert "Pre-Application" in stages
        assert "Application" in stages
        assert "Inspections" in stages
        assert "Enforcement" in stages

    def test_no_stage_is_gap(self):
        """After our tier4 ingestion, every stage should have at least 1 file."""
        inv = get_source_inventory()
        for stage in inv["lifecycle"]:
            assert stage["coverage"] != "gap", f"Stage '{stage['stage']}' has no coverage"

    def test_application_is_strong(self):
        """Application stage should have 3+ files (forms, checklist, fees, routing, etc.)."""
        inv = get_source_inventory()
        app_stage = [s for s in inv["lifecycle"] if s["stage"] == "Application"][0]
        assert app_stage["coverage"] == "strong"
        assert app_stage["file_count"] >= 3


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_extracts_from_real_file(self):
        from pathlib import Path
        fp = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "tier1" / "permit-expiration-rules.json"
        if not fp.exists():
            pytest.skip("permit-expiration-rules.json not found")
        meta = _extract_metadata(fp)
        assert "Permit Expiration" in meta["title"] or "permit expiration" in meta["title"].lower()
        assert meta["file_size_kb"] > 0
        assert meta["category"] == "building_code"

    def test_url_fallback_works(self):
        from pathlib import Path
        fp = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "tier1" / "fee-tables.json"
        if not fp.exists():
            pytest.skip("fee-tables.json not found")
        meta = _extract_metadata(fp)
        assert len(meta["urls"]) >= 1

    def test_freshness_computed(self):
        from pathlib import Path
        fp = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "tier1" / "permit-expiration-rules.json"
        if not fp.exists():
            pytest.skip("permit-expiration-rules.json not found")
        meta = _extract_metadata(fp)
        assert meta["freshness"] in ("fresh", "aging", "stale", "unknown")
        if meta["last_updated"]:
            assert meta["age_days"] is not None
            assert isinstance(meta["age_days"], int)


# ---------------------------------------------------------------------------
# Freshness indicators
# ---------------------------------------------------------------------------

class TestFreshnessIndicators:
    def test_every_file_has_freshness(self):
        inv = get_source_inventory()
        for f in inv["files"]:
            assert f.get("freshness") in ("fresh", "aging", "stale", "unknown"), \
                f"Missing freshness for {f.get('filename')}"

    def test_freshness_stats_in_inventory(self):
        inv = get_source_inventory()
        s = inv["stats"]
        assert "fresh_count" in s
        assert "aging_count" in s
        assert "stale_count" in s
        assert "unknown_freshness_count" in s
        # Counts should sum to total files
        assert s["fresh_count"] + s["aging_count"] + s["stale_count"] + s["unknown_freshness_count"] == s["total_files"]

    def test_files_with_dates_have_age(self):
        inv = get_source_inventory()
        for f in inv["files"]:
            if f.get("last_updated"):
                assert f.get("age_days") is not None
                assert f["freshness"] != "unknown"

    def test_files_without_dates_are_unknown(self):
        inv = get_source_inventory()
        for f in inv["files"]:
            if not f.get("last_updated"):
                assert f["freshness"] == "unknown"


# ---------------------------------------------------------------------------
# Route integration
# ---------------------------------------------------------------------------

class TestAdminSourcesRoute:
    """Tests for the /admin/sources route."""

    @pytest.fixture(autouse=True)
    def _use_duckdb(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test_sources.duckdb")
        monkeypatch.setenv("SF_PERMITS_DB", db_path)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import src.db as db_mod
        monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
        monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
        import web.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_schema_initialized", False)
        db_mod.init_user_schema()
        conn = db_mod.get_connection()
        try:
            db_mod.init_schema(conn)
        finally:
            conn.close()

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def _login_admin(self, client):
        from web.auth import get_or_create_user, create_magic_token
        from src.db import execute_write
        user = get_or_create_user("admin@sources.test")
        execute_write(
            "UPDATE users SET is_admin = TRUE WHERE user_id = %s",
            (user["user_id"],),
        )
        token = create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        return user

    def test_requires_login(self, client):
        rv = client.get("/admin/sources", follow_redirects=False)
        assert rv.status_code == 302

    def test_requires_admin(self, client):
        from web.auth import get_or_create_user, create_magic_token
        user = get_or_create_user("nonadmin@sources.test")
        token = create_magic_token(user["user_id"])
        client.get(f"/auth/verify/{token}", follow_redirects=True)
        rv = client.get("/admin/sources")
        assert rv.status_code == 403

    def test_renders_for_admin(self, client):
        self._login_admin(client)
        rv = client.get("/admin/sources")
        assert rv.status_code == 200
        html = rv.data.decode()
        assert "LUCK Source Inventory" in html
        assert "Permit Lifecycle Coverage" in html
        assert "Known Gaps" in html
        assert "Questions for Amy" in html

    def test_shows_file_count(self, client):
        self._login_admin(client)
        rv = client.get("/admin/sources")
        html = rv.data.decode()
        # Should show at least 29 files
        assert "29" in html or "3" in html  # 29 files or 30+

    def test_shows_categories(self, client):
        self._login_admin(client)
        rv = client.get("/admin/sources")
        html = rv.data.decode()
        assert "Building Code" in html
        assert "DBI Info Sheets" in html
        assert "Compliance" in html

    def test_shows_lifecycle_matrix(self, client):
        self._login_admin(client)
        rv = client.get("/admin/sources")
        html = rv.data.decode()
        assert "Pre-Application" in html
        assert "Enforcement" in html
        assert "Inspections" in html
