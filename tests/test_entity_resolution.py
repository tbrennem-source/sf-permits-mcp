"""Tests for entity resolution pipeline improvements.

Covers:
  - _normalize_license(): leading zero stripping, prefix normalization, edge cases
  - _normalize_name(): punctuation stripping, uppercase
  - _token_set_similarity(): identical, reordered, partial, empty
  - _pick_canonical_name() and _pick_canonical_firm()
  - _most_common_role()
  - Cross-source name matching (Step 2.5)
  - Multi-role entity enrichment
  - License normalization in _resolve_by_key()
  - Integration: full pipeline with in-memory DuckDB
"""
from __future__ import annotations

import duckdb
import pytest

from src.entities import (
    _enrich_multi_role_entities,
    _most_common_role,
    _normalize_license,
    _normalize_name,
    _pick_canonical_firm,
    _pick_canonical_name,
    _resolve_by_cross_source_name,
    _resolve_by_fuzzy_name,
    _resolve_by_key,
    _resolve_by_pts_agent_id,
    _resolve_remaining_singletons,
    _token_set_similarity,
    resolve_entities,
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(contacts_data: list[tuple]) -> duckdb.DuckDBPyConnection:
    """Create a minimal in-memory DuckDB with contacts + entities tables.

    contacts_data rows: (id, name, firm_name, role, permit_number, source,
                          pts_agent_id, license_number, sf_business_license, entity_id)
    """
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY,
            name VARCHAR,
            firm_name VARCHAR,
            role VARCHAR,
            permit_number VARCHAR,
            source VARCHAR,
            pts_agent_id VARCHAR,
            license_number VARCHAR,
            sf_business_license VARCHAR,
            entity_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE entities (
            entity_id INTEGER PRIMARY KEY,
            canonical_name VARCHAR,
            canonical_firm VARCHAR,
            entity_type VARCHAR,
            pts_agent_id VARCHAR,
            license_number VARCHAR,
            sf_business_license VARCHAR,
            resolution_method VARCHAR,
            resolution_confidence VARCHAR,
            contact_count INTEGER,
            permit_count INTEGER,
            source_datasets VARCHAR,
            roles VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE relationships (
            entity_id_a INTEGER,
            entity_id_b INTEGER,
            shared_permits INTEGER,
            permit_numbers VARCHAR,
            permit_types VARCHAR,
            date_range_start DATE,
            date_range_end DATE,
            total_estimated_cost DOUBLE,
            neighborhoods VARCHAR
        )
    """)
    if contacts_data:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            contacts_data,
        )
    return conn


# ---------------------------------------------------------------------------
# _normalize_license
# ---------------------------------------------------------------------------

class TestNormalizeLicense:

    def test_none_returns_none(self):
        assert _normalize_license(None) is None

    def test_empty_string_returns_none(self):
        assert _normalize_license("") is None

    def test_whitespace_only_returns_none(self):
        assert _normalize_license("   ") is None

    def test_plain_numeric_no_change(self):
        assert _normalize_license("12345") == "12345"

    def test_strip_leading_zeros(self):
        assert _normalize_license("0012345") == "12345"

    def test_strip_many_leading_zeros(self):
        assert _normalize_license("000001") == "1"

    def test_c10_dash_uppercase(self):
        assert _normalize_license("C-10") == "C10"

    def test_c10_lowercase_dash(self):
        assert _normalize_license("c-10") == "C10"

    def test_c10_lowercase_no_dash(self):
        assert _normalize_license("c10") == "C10"

    def test_b_prefix_with_dash(self):
        assert _normalize_license("B-12345") == "B12345"

    def test_multi_letter_prefix(self):
        # e.g., "CA-12345" (hypothetical prefix)
        result = _normalize_license("CA-12345")
        assert result == "CA12345"

    def test_already_normalized_prefix(self):
        assert _normalize_license("C10") == "C10"

    def test_whitespace_stripped_before_processing(self):
        assert _normalize_license("  12345  ") == "12345"

    def test_single_zero_stays_zero(self):
        # "0" is a valid license number, stripping leading zeros gives "0"
        assert _normalize_license("0") == "0"

    def test_prefix_with_numeric_suffix_no_leading_zeros(self):
        # "C-0010" → "C0010" (prefix present, we don't strip zeros after prefix)
        result = _normalize_license("C-0010")
        assert result == "C0010"


# ---------------------------------------------------------------------------
# _normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:

    def test_uppercase(self):
        assert _normalize_name("john smith") == "JOHN SMITH"

    def test_strip_commas(self):
        assert _normalize_name("SMITH, JOHN") == "SMITH  JOHN".replace("  ", " ")
        # After regex replace "," → " " and collapse spaces
        assert _normalize_name("SMITH, JOHN") == "SMITH JOHN"

    def test_strip_periods(self):
        assert _normalize_name("J. SMITH") == "J SMITH"

    def test_strip_dashes(self):
        assert _normalize_name("SMITH-JONES") == "SMITH JONES"

    def test_strip_apostrophes(self):
        assert _normalize_name("O'BRIEN") == "O BRIEN"

    def test_collapse_multiple_spaces(self):
        assert _normalize_name("JOHN   SMITH") == "JOHN SMITH"

    def test_strip_whitespace(self):
        assert _normalize_name("  JOHN SMITH  ") == "JOHN SMITH"

    def test_empty_string(self):
        assert _normalize_name("") == ""

    def test_combined_normalization(self):
        # DBI-style: "SMITH, JOHN R." → "SMITH JOHN R"
        assert _normalize_name("SMITH, JOHN R.") == "SMITH JOHN R"


# ---------------------------------------------------------------------------
# _token_set_similarity
# ---------------------------------------------------------------------------

class TestTokenSetSimilarity:

    def test_identical(self):
        assert _token_set_similarity("JOHN SMITH", "JOHN SMITH") == 1.0

    def test_reordered_tokens(self):
        # Token SET similarity is order-independent
        assert _token_set_similarity("SMITH JOHN", "JOHN SMITH") == 1.0

    def test_empty_a(self):
        assert _token_set_similarity("", "JOHN") == 0.0

    def test_empty_b(self):
        assert _token_set_similarity("JOHN", "") == 0.0

    def test_both_empty(self):
        assert _token_set_similarity("", "") == 0.0

    def test_partial_overlap(self):
        # "JOHN SMITH" vs "JOHN JONES" → 1 common / 3 total = 0.333...
        sim = _token_set_similarity("JOHN SMITH", "JOHN JONES")
        assert abs(sim - 1/3) < 0.001

    def test_no_overlap(self):
        assert _token_set_similarity("ALICE BROWN", "JOHN SMITH") == 0.0

    def test_case_insensitive(self):
        assert _token_set_similarity("john smith", "JOHN SMITH") == 1.0

    def test_single_token_match(self):
        assert _token_set_similarity("SMITH", "SMITH") == 1.0

    def test_subset(self):
        # "JOHN" is a subset of "JOHN SMITH" → 1/2 = 0.5
        sim = _token_set_similarity("JOHN", "JOHN SMITH")
        assert abs(sim - 0.5) < 0.001


# ---------------------------------------------------------------------------
# _pick_canonical_name / _pick_canonical_firm
# ---------------------------------------------------------------------------

class TestPickCanonical:

    def test_pick_longest_name(self):
        assert _pick_canonical_name(["BOB", "ROBERT SMITH", "R. SMITH"]) == "ROBERT SMITH"

    def test_pick_with_nones(self):
        assert _pick_canonical_name([None, "JOHN", None]) == "JOHN"

    def test_all_none_returns_none(self):
        assert _pick_canonical_name([None, None]) is None

    def test_empty_list_returns_none(self):
        assert _pick_canonical_name([]) is None

    def test_pick_longest_firm(self):
        assert _pick_canonical_firm(["ACME", "ACME ELECTRIC INC", "ACME ELEC"]) == "ACME ELECTRIC INC"

    def test_firm_all_none(self):
        assert _pick_canonical_firm([None]) is None


# ---------------------------------------------------------------------------
# _most_common_role
# ---------------------------------------------------------------------------

class TestMostCommonRole:

    def test_single_role(self):
        assert _most_common_role(["electrical"]) == "electrical"

    def test_majority_role(self):
        assert _most_common_role(["electrical", "plumbing", "electrical"]) == "electrical"

    def test_all_none(self):
        assert _most_common_role([None, None]) is None

    def test_mixed_none(self):
        assert _most_common_role([None, "electrical", None]) == "electrical"

    def test_empty(self):
        assert _most_common_role([]) is None


# ---------------------------------------------------------------------------
# Integration: _resolve_by_key with license normalization
# ---------------------------------------------------------------------------

class TestResolveByKeyLicenseNorm:
    """Verify that license normalization causes contacts with different raw
    license strings (e.g. "0012345" vs "12345") to resolve to the same entity.
    """

    def test_leading_zero_matches_no_zero(self):
        """Contacts with "0012345" and "12345" should merge into one entity."""
        contacts = [
            # (id, name, firm_name, role, permit_number, source, pts_agent_id, license_number, sf_biz, entity_id)
            (1, "JOHN SMITH", None, "electrical", "P001", "electrical", None, "0012345", None, None),
            (2, "JOHN SMITH", None, "electrical", "P002", "electrical", None, "12345",   None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_key(conn, 1, "license_number", "license_number", "medium")

        # Both contacts should have the same entity_id
        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        entity_ids = [r[0] for r in rows]
        assert entity_ids[0] == entity_ids[1], "Leading-zero license should match normalized license"
        assert created == 1, "Only one entity should be created for the normalized license"

    def test_prefix_normalization_c10_matches(self):
        """Contacts with "C-10" and "c10" should merge into one entity."""
        contacts = [
            (1, "JANE DOE", None, "electrical", "P003", "electrical", None, "C-10",  None, None),
            (2, "JANE DOE", None, "electrical", "P004", "electrical", None, "c10",   None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_key(conn, 1, "license_number", "license_number", "medium")

        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        entity_ids = [r[0] for r in rows]
        assert entity_ids[0] == entity_ids[1], "C-10 and c10 should normalize to same entity"
        assert created == 1

    def test_different_licenses_create_separate_entities(self):
        """Different license numbers create separate entities."""
        contacts = [
            (1, "ALICE", None, "electrical", "P005", "electrical", None, "11111", None, None),
            (2, "BOB",   None, "electrical", "P006", "electrical", None, "22222", None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_key(conn, 1, "license_number", "license_number", "medium")

        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        entity_ids = [r[0] for r in rows]
        assert entity_ids[0] != entity_ids[1], "Different licenses → different entities"
        assert created == 2


# ---------------------------------------------------------------------------
# Integration: _resolve_by_cross_source_name
# ---------------------------------------------------------------------------

class TestResolveByCrossSourceName:

    def test_same_name_same_permit_different_sources_merges(self):
        """Same name on same permit from 'building' and 'electrical' sources merges."""
        contacts = [
            (1, "JOHNS ELECTRIC", None, "electrical", "P100", "building",    None, None, None, None),
            (2, "JOHNS ELECTRIC", None, "electrical", "P100", "electrical",  None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_cross_source_name(conn, 1)

        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        entity_ids = [r[0] for r in rows]
        assert entity_ids[0] == entity_ids[1], "Same name on same permit across sources should merge"
        assert created == 1

    def test_same_name_different_permit_no_merge(self):
        """Same name on different permits from different sources should NOT merge."""
        contacts = [
            (1, "SMITH PLUMBING", None, "plumbing", "P200", "building",  None, None, None, None),
            (2, "SMITH PLUMBING", None, "plumbing", "P201", "plumbing",  None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_cross_source_name(conn, 1)

        # Neither should be assigned — different permits means no cross-source match
        unresolved = conn.execute("SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL").fetchone()[0]
        assert unresolved == 2, "Different permits should not trigger cross-source merge"
        assert created == 0

    def test_same_source_no_merge(self):
        """Same name on same permit from same source should NOT be merged by this step."""
        contacts = [
            (1, "ABC CORP", None, "contractor", "P300", "building", None, None, None, None),
            (2, "ABC CORP", None, "contractor", "P300", "building", None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_cross_source_name(conn, 1)

        unresolved = conn.execute("SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL").fetchone()[0]
        assert unresolved == 2, "Same source contacts should not be merged in this step"

    def test_punctuation_insensitive_name_match(self):
        """'JOHN'S ELECTRIC' and 'JOHNS ELECTRIC' normalize to same name via REGEXP_REPLACE."""
        contacts = [
            (1, "JOHN'S ELECTRIC", None, "electrical", "P400", "building",   None, None, None, None),
            (2, "JOHNS ELECTRIC",  None, "electrical", "P400", "electrical", None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        next_eid, created = _resolve_by_cross_source_name(conn, 1)

        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        entity_ids = [r[0] for r in rows]
        assert entity_ids[0] == entity_ids[1], "Punctuation variation should merge across sources"

    def test_already_resolved_contacts_skipped(self):
        """Contacts already resolved should not be touched by this step."""
        contacts = [
            (1, "ACME ELECTRIC", None, "electrical", "P500", "building",   None, None, None, 99),  # pre-assigned
            (2, "ACME ELECTRIC", None, "electrical", "P500", "electrical", None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        # Pre-populate entity 99 to avoid FK issues
        conn.execute("""
            INSERT INTO entities VALUES (99, 'ACME ELECTRIC', NULL, 'electrical',
                NULL, NULL, NULL, 'pts_agent_id', 'high', 1, 1, 'building', NULL)
        """)
        next_eid, created = _resolve_by_cross_source_name(conn, 1)

        # Contact 1 keeps its pre-assigned entity_id
        row1 = conn.execute("SELECT entity_id FROM contacts WHERE id = 1").fetchone()
        assert row1[0] == 99, "Pre-assigned entity_id should not be overwritten"


# ---------------------------------------------------------------------------
# Integration: _enrich_multi_role_entities
# ---------------------------------------------------------------------------

class TestEnrichMultiRoleEntities:

    def test_multi_role_entity_gets_roles_field(self):
        """Entity appearing as both 'owner' and 'contractor' should get roles='contractor,owner'."""
        contacts = [
            (1, "TIM BUILDER", None, "owner",      "P600", "building", None, None, None, 1),
            (2, "TIM BUILDER", None, "contractor",  "P601", "building", None, None, None, 1),
        ]
        conn = _create_test_db(contacts)
        conn.execute("""
            INSERT INTO entities VALUES (1, 'TIM BUILDER', NULL, 'owner',
                NULL, NULL, NULL, 'pts_agent_id', 'high', 2, 2, 'building', NULL)
        """)
        count = _enrich_multi_role_entities(conn)

        entity = conn.execute("SELECT roles FROM entities WHERE entity_id = 1").fetchone()
        assert entity[0] is not None, "Multi-role entity should have roles populated"
        roles_set = set(entity[0].split(","))
        assert "owner" in roles_set
        assert "contractor" in roles_set
        assert count == 1

    def test_single_role_entity_no_roles_field(self):
        """Entity with a single role should have roles = NULL."""
        contacts = [
            (1, "JANE INSPECTOR", None, "electrical", "P700", "electrical", None, None, None, 1),
            (2, "JANE INSPECTOR", None, "electrical", "P701", "electrical", None, None, None, 1),
        ]
        conn = _create_test_db(contacts)
        conn.execute("""
            INSERT INTO entities VALUES (1, 'JANE INSPECTOR', NULL, 'electrical',
                NULL, NULL, NULL, 'license_number', 'medium', 2, 2, 'electrical', NULL)
        """)
        count = _enrich_multi_role_entities(conn)

        entity = conn.execute("SELECT roles FROM entities WHERE entity_id = 1").fetchone()
        assert entity[0] is None, "Single-role entity should have roles = NULL"
        assert count == 0

    def test_three_roles(self):
        """Entity with three distinct roles should list all three."""
        contacts = [
            (1, "MULTI MAN", None, "owner",       "P800", "building",   None, None, None, 5),
            (2, "MULTI MAN", None, "contractor",   "P801", "building",   None, None, None, 5),
            (3, "MULTI MAN", None, "architect",    "P802", "building",   None, None, None, 5),
        ]
        conn = _create_test_db(contacts)
        conn.execute("""
            INSERT INTO entities VALUES (5, 'MULTI MAN', NULL, 'owner',
                NULL, NULL, NULL, 'pts_agent_id', 'high', 3, 3, 'building', NULL)
        """)
        _enrich_multi_role_entities(conn)

        entity = conn.execute("SELECT roles FROM entities WHERE entity_id = 5").fetchone()
        assert entity[0] is not None
        roles_set = set(entity[0].split(","))
        assert roles_set == {"owner", "contractor", "architect"}


# ---------------------------------------------------------------------------
# Integration: full pipeline via resolve_entities with in-memory DB
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    """End-to-end pipeline tests using an in-memory DuckDB.

    We monkey-patch get_connection to use our pre-seeded in-memory conn.
    """

    def _run_pipeline_on_conn(self, conn) -> dict:
        """Run the resolution steps directly on a pre-built conn (no file I/O)."""
        total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]

        conn.execute("DELETE FROM entities")
        conn.execute("UPDATE contacts SET entity_id = NULL")

        next_eid = 1
        stats: dict[str, int] = {}

        next_eid, count = _resolve_by_pts_agent_id(conn, next_eid)
        stats["pts_agent_id"] = count

        next_eid, count = _resolve_by_key(conn, next_eid, "license_number", "license_number", "medium")
        stats["license_number"] = count

        next_eid, count = _resolve_by_cross_source_name(conn, next_eid)
        stats["cross_source_name"] = count

        next_eid, count = _resolve_by_key(conn, next_eid, "sf_business_license", "sf_business_license", "medium")
        stats["sf_business_license"] = count

        next_eid, count = _resolve_by_fuzzy_name(conn, next_eid)
        stats["fuzzy_name"] = count

        next_eid, count = _resolve_remaining_singletons(conn, next_eid)
        stats["singleton"] = count

        multi = _enrich_multi_role_entities(conn)
        stats["multi_role_entities"] = multi

        stats["total_entities"] = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        stats["total_contacts"] = total_contacts
        return stats

    def test_all_contacts_get_entity_ids(self):
        """After full pipeline, no contacts should have entity_id = NULL."""
        contacts = [
            (1, "ALICE SMITH",   None, "electrical", "P001", "electrical", None, "L001", None, None),
            (2, "BOB JONES",     None, "plumbing",   "P002", "plumbing",   None, None,   None, None),
            (3, "CAROL BUILDER", None, "contractor", "P003", "building",   "A1", None,   None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        unresolved = conn.execute("SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL").fetchone()[0]
        assert unresolved == 0, "All contacts should have entity_ids after full pipeline"

    def test_license_number_deduplication(self):
        """Two contacts with the same license number → one entity."""
        contacts = [
            (1, "JOHN ELECTRIC",  None, "electrical", "P001", "electrical", None, "L999", None, None),
            (2, "JOHN ELEC INC",  None, "electrical", "P002", "electrical", None, "L999", None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        assert rows[0][0] == rows[1][0], "Same license → same entity"
        assert stats["total_entities"] == 1

    def test_pts_agent_id_deduplication(self):
        """Multiple building contacts with same pts_agent_id → one entity."""
        contacts = [
            (1, "TIM OWNER", None, "owner", "P010", "building", "PTS-42", None, None, None),
            (2, "TIM OWNER", None, "owner", "P011", "building", "PTS-42", None, None, None),
            (3, "TIM OWNER", None, "owner", "P012", "building", "PTS-42", None, None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        rows = conn.execute("SELECT DISTINCT entity_id FROM contacts").fetchall()
        assert len(rows) == 1, "All PTS-42 contacts → same entity"
        assert stats["pts_agent_id"] == 1
        assert stats["total_entities"] == 1

    def test_cross_source_deduplication(self):
        """Cross-source match on same permit reduces entity count."""
        contacts = [
            (1, "QUICK PLUMBING", None, "plumbing", "P020", "building",  None, None, None, None),
            (2, "QUICK PLUMBING", None, "plumbing", "P020", "plumbing",  None, None, None, None),
            (3, "OTHER PLUMBER",  None, "plumbing", "P021", "plumbing",  None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        # Contacts 1 and 2 should share an entity
        rows = conn.execute("SELECT id, entity_id FROM contacts ORDER BY id").fetchall()
        eid_map = {r[0]: r[1] for r in rows}
        assert eid_map[1] == eid_map[2], "Cross-source contacts on same permit should merge"
        assert eid_map[1] != eid_map[3], "Different permit → different entity"

    def test_fuzzy_matching_consolidates_name_variants(self):
        """Name variants that share most tokens get merged by fuzzy matching."""
        contacts = [
            (1, "GARCIA CARLOS",  None, "architect", "P030", "building", None, None, None, None),
            (2, "GARCIA CARLOS",  None, "architect", "P031", "building", None, None, None, None),
            # Third contact with distinct name should be separate
            (3, "TANAKA KENJI",   None, "architect", "P032", "building", None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        rows = conn.execute("SELECT id, entity_id FROM contacts ORDER BY id").fetchall()
        eid_map = {r[0]: r[1] for r in rows}
        assert eid_map[1] == eid_map[2], "Identical names → same fuzzy entity"
        assert eid_map[1] != eid_map[3], "Different names → different entity"

    def test_singletons_cover_unnamed_contacts(self):
        """Contacts with no name, no license, no pts_agent_id become singletons."""
        contacts = [
            (1, None, "FIRM A", "contractor", "P040", "building", None, None, None, None),
            (2, None, "FIRM B", "contractor", "P041", "building", None, None, None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        unresolved = conn.execute("SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL").fetchone()[0]
        assert unresolved == 0
        assert stats["singleton"] == 2

    def test_multi_role_enrichment_in_pipeline(self):
        """After pipeline, multi-role entities have roles column populated."""
        contacts = [
            (1, "DANA BUILDER", None, "owner",      "P050", "building", "P50", None, None, None),
            (2, "DANA BUILDER", None, "contractor",  "P051", "building", "P50", None, None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        # Both contacts share the same pts_agent_id → same entity
        rows = conn.execute("SELECT entity_id FROM contacts ORDER BY id").fetchall()
        assert rows[0][0] == rows[1][0]

        entity = conn.execute("SELECT roles FROM entities LIMIT 1").fetchone()
        assert entity[0] is not None, "Multi-role entity should have roles set"
        assert stats["multi_role_entities"] == 1

    def test_entity_count_less_than_contact_count(self):
        """After deduplication, entity count should be less than contact count."""
        contacts = [
            (1, "PETE ELECTRIC", None, "electrical", "P060", "electrical", None, "L100", None, None),
            (2, "PETE ELECTRIC", None, "electrical", "P061", "electrical", None, "L100", None, None),
            (3, "PETE ELECTRIC", None, "electrical", "P062", "electrical", None, "L100", None, None),
            (4, "SARA PLUMBER",  None, "plumbing",   "P063", "plumbing",   None, "L200", None, None),
            (5, "SARA PLUMBER",  None, "plumbing",   "P064", "plumbing",   None, "L200", None, None),
        ]
        conn = _create_test_db(contacts)
        stats = self._run_pipeline_on_conn(conn)

        assert stats["total_entities"] < stats["total_contacts"]
        assert stats["total_entities"] == 2, "5 contacts with 2 distinct licenses → 2 entities"

    def test_empty_database(self):
        """Pipeline handles zero contacts gracefully."""
        conn = _create_test_db([])
        stats = self._run_pipeline_on_conn(conn)

        assert stats["total_entities"] == 0
        assert stats["total_contacts"] == 0
