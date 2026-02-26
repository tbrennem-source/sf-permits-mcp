"""Tests for Sprint 65-A: Planning contacts extraction and entity resolution."""

import pytest
import duckdb

import src.db as db_mod
from src.db import init_schema
from src.ingest import extract_planning_contacts
from src.entities import _resolve_planning_contacts, _normalize_name


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_65a.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    conn = db_mod.get_connection()
    try:
        init_schema(conn)
    finally:
        conn.close()


def _insert_planning_records(conn, records):
    """Insert planning records for testing."""
    for r in records:
        conn.execute("""
            INSERT INTO planning_records
            (record_id, record_type, record_status, block, lot, address,
             project_name, description, applicant, applicant_org,
             assigned_planner, open_date, environmental_doc_type,
             is_project, units_existing, units_proposed, units_net,
             affordable_units, child_id, parent_id, data_as_of)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, r)


# ── extract_planning_contacts tests ──────────────────────────────


class TestExtractPlanningContacts:
    def test_basic_extraction(self):
        """Extract applicant and planner contacts from planning records."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-001PRJ", "project", "open", "3512", "001", "123 MARKET ST",
                 "Kitchen remodel", "Remodel kitchen", "JOHN SMITH", "SMITH CONSTRUCTION",
                 "JANE DOE", "2024-01-15", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            count = extract_planning_contacts(conn)
            assert count == 2  # 1 applicant + 1 planner

            contacts = conn.execute(
                "SELECT source, role, name, firm_name FROM contacts WHERE source = 'planning' ORDER BY role"
            ).fetchall()
            assert len(contacts) == 2

            applicant = [c for c in contacts if c[1] == 'applicant'][0]
            assert applicant[0] == 'planning'
            assert applicant[2] == 'JOHN SMITH'
            assert applicant[3] == 'SMITH CONSTRUCTION'

            planner = [c for c in contacts if c[1] == 'planner'][0]
            assert planner[0] == 'planning'
            assert planner[2] == 'JANE DOE'
            assert planner[3] is None  # planners have no firm
        finally:
            conn.close()

    def test_no_applicant(self):
        """Records without applicant only produce planner contacts."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-002PRJ", "project", "open", "3512", "002", "456 MARKET ST",
                 "Window replacement", "Replace windows", None, None,
                 "BOB JOHNSON", "2024-02-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            count = extract_planning_contacts(conn)
            assert count == 1

            contacts = conn.execute(
                "SELECT role, name FROM contacts WHERE source = 'planning'"
            ).fetchall()
            assert len(contacts) == 1
            assert contacts[0][0] == 'planner'
            assert contacts[0][1] == 'BOB JOHNSON'
        finally:
            conn.close()

    def test_no_planner(self):
        """Records without planner only produce applicant contacts."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-003PRJ", "project", "open", "3512", "003", "789 MARKET ST",
                 "ADU", "Build ADU", "ALICE WONG", "WONG LLC",
                 None, "2024-03-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            count = extract_planning_contacts(conn)
            assert count == 1

            contacts = conn.execute(
                "SELECT role, name, firm_name FROM contacts WHERE source = 'planning'"
            ).fetchall()
            assert len(contacts) == 1
            assert contacts[0][0] == 'applicant'
            assert contacts[0][1] == 'ALICE WONG'
            assert contacts[0][2] == 'WONG LLC'
        finally:
            conn.close()

    def test_empty_planning_records(self):
        """No planning records produces zero contacts."""
        conn = db_mod.get_connection()
        try:
            count = extract_planning_contacts(conn)
            assert count == 0
        finally:
            conn.close()

    def test_blank_applicant_skipped(self):
        """Blank or whitespace-only applicant names are skipped."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-004PRJ", "project", "open", "3512", "004", "100 MAIN ST",
                 "Test", "Test", "   ", None,
                 "PLANNER ONE", "2024-04-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            count = extract_planning_contacts(conn)
            assert count == 1  # Only the planner

            contacts = conn.execute(
                "SELECT role FROM contacts WHERE source = 'planning'"
            ).fetchall()
            assert contacts[0][0] == 'planner'
        finally:
            conn.close()

    def test_permit_number_is_record_id(self):
        """Contacts use planning record_id as permit_number."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-005PRJ", "project", "open", "3512", "005", "200 MAIN ST",
                 "Test", "Test", "TEST USER", None,
                 None, "2024-05-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            extract_planning_contacts(conn)

            contacts = conn.execute(
                "SELECT permit_number FROM contacts WHERE source = 'planning'"
            ).fetchall()
            assert contacts[0][0] == '2024-005PRJ'
        finally:
            conn.close()

    def test_multiple_records(self):
        """Multiple planning records produce correct contact count."""
        conn = db_mod.get_connection()
        try:
            _insert_planning_records(conn, [
                ("2024-010PRJ", "project", "open", "3512", "010", "10 A ST",
                 "P1", "D1", "APP ONE", "ORG1", "PLAN A", "2024-01-01", None, True, None, None, None, None, None, None, "2024-06-01"),
                ("2024-011PRJ", "project", "open", "3512", "011", "11 A ST",
                 "P2", "D2", "APP TWO", None, "PLAN B", "2024-02-01", None, True, None, None, None, None, None, None, "2024-06-01"),
                ("2024-012PRJ", "project", "open", "3512", "012", "12 A ST",
                 "P3", "D3", "APP THREE", None, None, "2024-03-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            count = extract_planning_contacts(conn)
            # 3 applicants + 2 planners = 5
            assert count == 5
        finally:
            conn.close()

    def test_id_continuity(self):
        """Planning contact IDs start after existing contacts."""
        conn = db_mod.get_connection()
        try:
            # Insert an existing building contact
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name)
                VALUES (100, 'building', 'BLD-001', 'architect', 'EXISTING PERSON')
            """)

            _insert_planning_records(conn, [
                ("2024-020PRJ", "project", "open", "3512", "020", "20 B ST",
                 "P", "D", "NEW PERSON", None, None, "2024-01-01", None, True, None, None, None, None, None, None, "2024-06-01"),
            ])
            extract_planning_contacts(conn)

            planning_ids = conn.execute(
                "SELECT id FROM contacts WHERE source = 'planning'"
            ).fetchall()
            assert all(row[0] > 100 for row in planning_ids)
        finally:
            conn.close()


# ── _resolve_planning_contacts tests ─────────────────────────────


class TestResolvePlanningContacts:
    def test_merges_into_existing_entity(self):
        """Planning contact with matching name merges into existing entity."""
        conn = db_mod.get_connection()
        try:
            # Create existing entity + contact
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (1, 'building', 'BLD-001', 'architect', 'JOHN SMITH', 1)
            """)
            conn.execute("""
                INSERT INTO entities (entity_id, canonical_name, entity_type,
                    resolution_method, resolution_confidence, contact_count, permit_count, source_datasets)
                VALUES (1, 'JOHN SMITH', 'architect', 'pts_agent_id', 'high', 1, 1, 'building')
            """)

            # Add planning contact with same name
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (2, 'planning', '2024-001PRJ', 'applicant', 'JOHN SMITH', NULL)
            """)

            next_eid, merged = _resolve_planning_contacts(conn, 2)
            assert merged == 1
            assert next_eid == 2  # No new entities created

            # Planning contact should now have entity_id = 1
            eid = conn.execute(
                "SELECT entity_id FROM contacts WHERE id = 2"
            ).fetchone()[0]
            assert eid == 1

            # Entity source_datasets should include planning
            srcs = conn.execute(
                "SELECT source_datasets FROM entities WHERE entity_id = 1"
            ).fetchone()[0]
            assert 'planning' in srcs
        finally:
            conn.close()

    def test_no_match_leaves_unresolved(self):
        """Planning contacts that don't match existing entities stay unresolved."""
        conn = db_mod.get_connection()
        try:
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (1, 'building', 'BLD-001', 'architect', 'ALICE WONG', 1)
            """)
            conn.execute("""
                INSERT INTO entities (entity_id, canonical_name, entity_type,
                    resolution_method, resolution_confidence, contact_count, permit_count, source_datasets)
                VALUES (1, 'ALICE WONG', 'architect', 'pts_agent_id', 'high', 1, 1, 'building')
            """)
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (2, 'planning', '2024-002PRJ', 'applicant', 'BOB DIFFERENT', NULL)
            """)

            next_eid, merged = _resolve_planning_contacts(conn, 2)
            assert merged == 0

            eid = conn.execute(
                "SELECT entity_id FROM contacts WHERE id = 2"
            ).fetchone()[0]
            assert eid is None
        finally:
            conn.close()

    def test_no_planning_contacts(self):
        """No planning contacts returns zero."""
        conn = db_mod.get_connection()
        try:
            next_eid, merged = _resolve_planning_contacts(conn, 1)
            assert merged == 0
        finally:
            conn.close()

    def test_does_not_create_new_entities(self):
        """Planning resolution is additive-only — never creates new entities."""
        conn = db_mod.get_connection()
        try:
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (1, 'planning', '2024-003PRJ', 'applicant', 'UNIQUE NAME', NULL)
            """)

            entity_count_before = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            next_eid, merged = _resolve_planning_contacts(conn, 1)
            entity_count_after = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

            assert entity_count_before == entity_count_after
            assert merged == 0
        finally:
            conn.close()

    def test_case_insensitive_matching(self):
        """Name matching is case-insensitive via normalization."""
        conn = db_mod.get_connection()
        try:
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (1, 'building', 'BLD-001', 'owner', 'John Smith', 1)
            """)
            conn.execute("""
                INSERT INTO entities (entity_id, canonical_name, entity_type,
                    resolution_method, resolution_confidence, contact_count, permit_count, source_datasets)
                VALUES (1, 'John Smith', 'owner', 'pts_agent_id', 'high', 1, 1, 'building')
            """)
            conn.execute("""
                INSERT INTO contacts (id, source, permit_number, role, name, entity_id)
                VALUES (2, 'planning', '2024-004PRJ', 'applicant', 'JOHN SMITH', NULL)
            """)

            next_eid, merged = _resolve_planning_contacts(conn, 2)
            assert merged == 1
        finally:
            conn.close()
