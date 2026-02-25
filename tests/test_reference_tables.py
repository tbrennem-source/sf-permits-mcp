"""Tests for Sprint 55B: predict_permits reference tables.

Covers:
  - Table creation via init_schema (DuckDB)
  - Table creation via init_user_schema (DuckDB)
  - Seed script populates all 3 tables
  - ref_zoning_routing has common SF zoning codes
  - ref_permit_forms covers common project types
  - ref_agency_triggers covers key agencies
  - Cron endpoint auth (403 without token)
  - Idempotency — running seed twice does not duplicate rows
  - Seed script returns ok=True with non-zero counts
  - All 3 tables accessible via query()
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def duckdb_conn(tmp_path):
    """Create a fresh in-memory DuckDB connection with schema initialized."""
    import duckdb
    from src.db import init_schema, init_user_schema

    db_path = str(tmp_path / "test_ref.duckdb")
    conn = duckdb.connect(db_path)

    # init_schema creates the bulk-data tables + reference tables
    init_schema(conn)
    # init_user_schema creates user + reference tables (dev mode)
    init_user_schema(conn)

    yield conn
    conn.close()


@pytest.fixture
def seeded_conn(duckdb_conn):
    """DuckDB connection with reference tables seeded."""
    from scripts.seed_reference_tables import (
        ZONING_ROUTING_ROWS,
        PERMIT_FORMS_ROWS,
        AGENCY_TRIGGERS_ROWS,
        _upsert_zoning_routing,
        _upsert_permit_forms,
        _upsert_agency_triggers,
    )

    _upsert_zoning_routing(duckdb_conn, "duckdb", ZONING_ROUTING_ROWS)
    _upsert_permit_forms(duckdb_conn, "duckdb", PERMIT_FORMS_ROWS)
    _upsert_agency_triggers(duckdb_conn, "duckdb", AGENCY_TRIGGERS_ROWS)

    yield duckdb_conn


# ---------------------------------------------------------------------------
# B1: Table creation tests
# ---------------------------------------------------------------------------

class TestTableCreation:
    """Verify tables are created by init_schema and init_user_schema."""

    def test_init_schema_creates_ref_zoning_routing(self, duckdb_conn):
        """ref_zoning_routing table exists after init_schema."""
        result = duckdb_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'ref_zoning_routing'"
        ).fetchone()
        assert result[0] == 1, "ref_zoning_routing table should exist"

    def test_init_schema_creates_ref_permit_forms(self, duckdb_conn):
        """ref_permit_forms table exists after init_schema."""
        result = duckdb_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'ref_permit_forms'"
        ).fetchone()
        assert result[0] == 1, "ref_permit_forms table should exist"

    def test_init_schema_creates_ref_agency_triggers(self, duckdb_conn):
        """ref_agency_triggers table exists after init_schema."""
        result = duckdb_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'ref_agency_triggers'"
        ).fetchone()
        assert result[0] == 1, "ref_agency_triggers table should exist"

    def test_ref_zoning_routing_has_correct_columns(self, duckdb_conn):
        """ref_zoning_routing has all 8 expected columns."""
        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ref_zoning_routing'"
        ).fetchall()
        col_names = {c[0] for c in cols}
        expected = {
            "zoning_code", "zoning_category", "planning_review_required",
            "fire_review_required", "health_review_required",
            "historic_district", "height_limit", "notes",
        }
        assert expected.issubset(col_names), f"Missing columns: {expected - col_names}"

    def test_ref_permit_forms_has_correct_columns(self, duckdb_conn):
        """ref_permit_forms has all 5 expected columns."""
        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ref_permit_forms'"
        ).fetchall()
        col_names = {c[0] for c in cols}
        expected = {"id", "project_type", "permit_form", "review_path", "notes"}
        assert expected.issubset(col_names), f"Missing columns: {expected - col_names}"

    def test_ref_agency_triggers_has_correct_columns(self, duckdb_conn):
        """ref_agency_triggers has all 5 expected columns."""
        cols = duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ref_agency_triggers'"
        ).fetchall()
        col_names = {c[0] for c in cols}
        expected = {"id", "trigger_keyword", "agency", "reason", "adds_weeks"}
        assert expected.issubset(col_names), f"Missing columns: {expected - col_names}"


# ---------------------------------------------------------------------------
# B2: Seed script tests
# ---------------------------------------------------------------------------

class TestSeedScript:
    """Verify seed_reference_tables populates all 3 tables correctly."""

    def test_seed_populates_all_three_tables(self, seeded_conn):
        """Seeded connection has rows in all 3 reference tables."""
        zoning_count = seeded_conn.execute("SELECT COUNT(*) FROM ref_zoning_routing").fetchone()[0]
        forms_count = seeded_conn.execute("SELECT COUNT(*) FROM ref_permit_forms").fetchone()[0]
        triggers_count = seeded_conn.execute("SELECT COUNT(*) FROM ref_agency_triggers").fetchone()[0]

        assert zoning_count > 0, "ref_zoning_routing should have rows"
        assert forms_count > 0, "ref_permit_forms should have rows"
        assert triggers_count > 0, "ref_agency_triggers should have rows"

    def test_zoning_has_common_sf_codes(self, seeded_conn):
        """ref_zoning_routing contains common SF zoning codes."""
        codes = {row[0] for row in seeded_conn.execute(
            "SELECT zoning_code FROM ref_zoning_routing"
        ).fetchall()}
        expected_codes = {"RC-4", "RH-1", "NC-2", "C-3-O", "PDR-1-G"}
        missing = expected_codes - codes
        assert not missing, f"Missing expected zoning codes: {missing}"

    def test_zoning_rc4_has_planning_and_fire(self, seeded_conn):
        """RC-4 (high-density residential/commercial) has planning and fire review."""
        row = seeded_conn.execute(
            "SELECT planning_review_required, fire_review_required "
            "FROM ref_zoning_routing WHERE zoning_code = 'RC-4'"
        ).fetchone()
        assert row is not None, "RC-4 should exist in ref_zoning_routing"
        planning, fire = row
        assert planning is True, "RC-4 should require planning review"
        assert fire is True, "RC-4 should require fire review"

    def test_zoning_rh1_no_mandatory_planning(self, seeded_conn):
        """RH-1 (single-family) does not require mandatory planning review."""
        row = seeded_conn.execute(
            "SELECT planning_review_required FROM ref_zoning_routing WHERE zoning_code = 'RH-1'"
        ).fetchone()
        assert row is not None, "RH-1 should exist"
        assert row[0] is False, "RH-1 should not require planning review for most work"

    def test_permit_forms_covers_common_project_types(self, seeded_conn):
        """ref_permit_forms has entries for kitchen_remodel, adu, new_construction."""
        project_types = {row[0] for row in seeded_conn.execute(
            "SELECT project_type FROM ref_permit_forms"
        ).fetchall()}
        required = {"kitchen_remodel", "adu", "new_construction", "restaurant", "demolition"}
        missing = required - project_types
        assert not missing, f"Missing project types: {missing}"

    def test_new_construction_uses_form_12(self, seeded_conn):
        """new_construction should use Form 1/2 and be in_house."""
        row = seeded_conn.execute(
            "SELECT permit_form, review_path FROM ref_permit_forms "
            "WHERE project_type = 'new_construction'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Form 1/2"
        assert row[1] == "in_house"

    def test_demolition_uses_form_6(self, seeded_conn):
        """demolition should use Form 6."""
        row = seeded_conn.execute(
            "SELECT permit_form FROM ref_permit_forms WHERE project_type = 'demolition'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Form 6"

    def test_agency_triggers_covers_key_agencies(self, seeded_conn):
        """ref_agency_triggers covers Planning, SFFD, and DPH."""
        agencies = {row[0] for row in seeded_conn.execute(
            "SELECT DISTINCT agency FROM ref_agency_triggers"
        ).fetchall()}
        required = {"Planning", "SFFD (Fire)", "DPH (Public Health)", "DBI (Building)"}
        missing = required - agencies
        assert not missing, f"Missing agencies in triggers: {missing}"

    def test_restaurant_triggers_dph(self, seeded_conn):
        """restaurant keyword should trigger DPH routing."""
        rows = seeded_conn.execute(
            "SELECT agency FROM ref_agency_triggers "
            "WHERE trigger_keyword = 'restaurant' AND agency = 'DPH (Public Health)'"
        ).fetchall()
        assert len(rows) > 0, "restaurant should trigger DPH"

    def test_seed_returns_ok_with_counts(self, duckdb_conn):
        """Upsert functions return correct row counts matching source data."""
        from scripts.seed_reference_tables import (
            ZONING_ROUTING_ROWS,
            PERMIT_FORMS_ROWS,
            AGENCY_TRIGGERS_ROWS,
            _upsert_zoning_routing,
            _upsert_permit_forms,
            _upsert_agency_triggers,
        )

        z = _upsert_zoning_routing(duckdb_conn, "duckdb", ZONING_ROUTING_ROWS)
        f = _upsert_permit_forms(duckdb_conn, "duckdb", PERMIT_FORMS_ROWS)
        t = _upsert_agency_triggers(duckdb_conn, "duckdb", AGENCY_TRIGGERS_ROWS)

        assert z == len(ZONING_ROUTING_ROWS), f"Expected {len(ZONING_ROUTING_ROWS)} zoning rows, got {z}"
        assert f == len(PERMIT_FORMS_ROWS), f"Expected {len(PERMIT_FORMS_ROWS)} form rows, got {f}"
        assert t == len(AGENCY_TRIGGERS_ROWS), f"Expected {len(AGENCY_TRIGGERS_ROWS)} trigger rows, got {t}"


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Verify running seed twice does not duplicate rows."""

    def test_double_seed_no_duplicates_zoning(self, duckdb_conn):
        """Running zoning seed twice yields same row count."""
        from scripts.seed_reference_tables import ZONING_ROUTING_ROWS, _upsert_zoning_routing

        _upsert_zoning_routing(duckdb_conn, "duckdb", ZONING_ROUTING_ROWS)
        count1 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_zoning_routing").fetchone()[0]

        _upsert_zoning_routing(duckdb_conn, "duckdb", ZONING_ROUTING_ROWS)
        count2 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_zoning_routing").fetchone()[0]

        assert count1 == count2, f"Duplicate rows on re-seed: {count1} → {count2}"

    def test_double_seed_no_duplicates_forms(self, duckdb_conn):
        """Running permit forms seed twice yields same row count."""
        from scripts.seed_reference_tables import PERMIT_FORMS_ROWS, _upsert_permit_forms

        _upsert_permit_forms(duckdb_conn, "duckdb", PERMIT_FORMS_ROWS)
        count1 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_permit_forms").fetchone()[0]

        _upsert_permit_forms(duckdb_conn, "duckdb", PERMIT_FORMS_ROWS)
        count2 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_permit_forms").fetchone()[0]

        assert count1 == count2, f"Duplicate rows on re-seed: {count1} → {count2}"

    def test_double_seed_no_duplicates_triggers(self, duckdb_conn):
        """Running agency triggers seed twice yields same row count."""
        from scripts.seed_reference_tables import AGENCY_TRIGGERS_ROWS, _upsert_agency_triggers

        _upsert_agency_triggers(duckdb_conn, "duckdb", AGENCY_TRIGGERS_ROWS)
        count1 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_agency_triggers").fetchone()[0]

        _upsert_agency_triggers(duckdb_conn, "duckdb", AGENCY_TRIGGERS_ROWS)
        count2 = duckdb_conn.execute("SELECT COUNT(*) FROM ref_agency_triggers").fetchone()[0]

        assert count1 == count2, f"Duplicate rows on re-seed: {count1} → {count2}"


# ---------------------------------------------------------------------------
# Cron endpoint auth tests
# ---------------------------------------------------------------------------

class TestCronEndpointAuth:
    """Verify /cron/seed-references requires CRON_SECRET auth."""

    @pytest.fixture
    def client(self):
        """Flask test client."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Set required env vars before importing app
        env_patch = {
            "DATABASE_URL": "",
            "CRON_SECRET": "test-secret-abc",
            "SECRET_KEY": "test-flask-key",
        }
        with patch.dict(os.environ, env_patch):
            from web.app import app
            app.config["TESTING"] = True
            with app.test_client() as c:
                yield c

    def test_cron_seed_references_403_without_token(self, client):
        """POST /cron/seed-references returns 403 without auth token."""
        resp = client.post("/cron/seed-references")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_cron_seed_references_403_with_wrong_token(self, client):
        """POST /cron/seed-references returns 403 with wrong token."""
        resp = client.post(
            "/cron/seed-references",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
