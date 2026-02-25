"""Tests for Phase 2: DuckDB schema, entity resolution, graph, validation.

Uses an in-memory DuckDB database with synthetic test data.
No network access required.
"""

import pytest
import duckdb

from src.db import init_schema
from src.entities import (
    resolve_entities,
    _pick_canonical_name,
    _pick_canonical_firm,
    _most_common_role,
    _token_set_similarity,
)
from src.graph import build_graph, get_neighbors, get_network
from src.validate import (
    search_entity,
    entity_network,
    inspector_contractor_links,
    find_clusters,
    anomaly_scan,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary DuckDB database with test data."""
    path = str(tmp_path / "test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    # Insert test contacts — 3 permits, multiple actors
    contacts = [
        # Permit P001: contractor Alice, architect Bob
        (1, "building", "P001", "contractor", "Alice Smith", "Alice", "Smith",
         "Smith Construction", "AGT001", "LIC001", "BIZ001", None,
         "123 Main St", "SF", "CA", "94110", "Y", "2024-01-01", None, "2024-01-01"),
        (2, "building", "P001", "architect", "Bob Jones", "Bob", "Jones",
         "Jones Architecture", "AGT002", "LIC002", None, None,
         "456 Oak St", "SF", "CA", "94110", "N", "2024-01-01", None, "2024-01-01"),

        # Permit P002: contractor Alice (same), engineer Charlie
        (3, "building", "P002", "contractor", "Alice Smith", "Alice", "Smith",
         "Smith Construction", "AGT001", "LIC001", "BIZ001", None,
         "123 Main St", "SF", "CA", "94110", "Y", "2024-02-01", None, "2024-02-01"),
        (4, "building", "P002", "engineer", "Charlie Brown", "Charlie", "Brown",
         None, "AGT003", None, None, None,
         "789 Elm St", "SF", "CA", "94110", "N", "2024-02-01", None, "2024-02-01"),

        # Permit P003: contractor Dave (electrical), same license as Alice in different system
        (5, "electrical", "P003", "contractor", "Smith Const LLC", None, None,
         "Smith Const LLC", None, "LIC001", "BIZ001", "555-1234",
         "123 Main St", None, "CA", "94110", None, None, None, "2024-03-01"),

        # Permit P003: also has Bob (via license match)
        (6, "electrical", "P003", "contractor", "Jones Arch", None, None,
         "Jones Arch", None, "LIC002", None, "555-5678",
         "456 Oak St", None, "CA", "94110", None, None, None, "2024-03-01"),

        # Permit P004: unrelated contractor Eve
        (7, "plumbing", "P004", "contractor", "Eve Williams Plumbing", None, None,
         "Eve Williams Plumbing", None, "LIC999", None, "555-9999",
         "999 Pine St", None, "CA", "94102", None, None, None, "2024-04-01"),
    ]

    conn.executemany(
        "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        contacts,
    )

    # Insert test permits
    permits = [
        ("P001", "1", "additions alterations or repairs", "complete", "2024-06-01",
         "Kitchen remodel", "2024-01-01", "2024-01-05", "2024-01-03", "2024-06-01",
         50000.0, None, "office", "office", 1, 1,
         "123", "MAIN", "ST", "94110", "Mission", "9", "3512", "001", None, "2024-01-01"),
        ("P002", "1", "additions alterations or repairs", "issued", "2024-02-15",
         "Bathroom addition", "2024-02-01", "2024-02-10", "2024-02-08", None,
         200000.0, None, "residential", "residential", 2, 3,
         "456", "OAK", "AVE", "94110", "Mission", "9", "3512", "002", None, "2024-02-01"),
        ("P003", "8", "otc alterations", "complete", "2024-05-01",
         "Electrical upgrade", "2024-03-01", "2024-03-02", "2024-03-01", "2024-05-01",
         150000.0, None, "commercial", "commercial", None, None,
         "789", "ELM", "ST", "94110", "SoMa", "6", "3600", "010", None, "2024-03-01"),
        ("P004", "1", "new construction", "issued", "2024-04-20",
         "New plumbing install", "2024-04-01", "2024-04-15", "2024-04-10", None,
         500000.0, None, None, None, None, None,
         "999", "PINE", "ST", "94102", "Nob Hill", "3", "0200", "005", None, "2024-04-01"),
    ]

    conn.executemany(
        "INSERT INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        permits,
    )

    # Insert test inspections
    inspections = [
        (1, "P001", "permit", "R Santos", "2024-03-01", "approved",
         "Final inspection", "3512", "001", "123", "MAIN", "ST",
         "Mission", "9", "94110", "2024-03-01", "building"),
        (2, "P002", "permit", "R Santos", "2024-04-01", "approved",
         "Rough inspection", "3512", "002", "456", "OAK", "AVE",
         "Mission", "9", "94110", "2024-04-01", "building"),
        (3, "P003", "permit", "J Smith", "2024-05-01", "approved",
         "Electrical inspection", "3600", "010", "789", "ELM", "ST",
         "SoMa", "6", "94110", "2024-05-01", "building"),
        (4, "P004", "permit", "J Smith", "2024-06-01", "disapproved",
         "Plumbing rough", "0200", "005", "999", "PINE", "ST",
         "Nob Hill", "3", "94102", "2024-06-01", "building"),
    ]

    conn.executemany(
        "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        inspections,
    )

    conn.close()
    return path


# ---- Schema Tests ----

def test_schema_creation(tmp_path):
    """Verify all tables are created by init_schema."""
    path = str(tmp_path / "schema_test.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)

    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    table_names = {t[0] for t in tables}

    assert "contacts" in table_names
    assert "entities" in table_names
    assert "relationships" in table_names
    assert "permits" in table_names
    assert "inspections" in table_names
    assert "ingest_log" in table_names
    assert "addenda" in table_names
    assert "violations" in table_names
    assert "complaints" in table_names
    assert "businesses" in table_names
    conn.close()


# ---- Entity Resolution Helper Tests ----

def test_pick_canonical_name():
    assert _pick_canonical_name(["Bob", "Robert Johnson", None, ""]) == "Robert Johnson"
    assert _pick_canonical_name([None, None]) is None
    assert _pick_canonical_name(["A"]) == "A"


def test_pick_canonical_firm():
    assert _pick_canonical_firm(["ABC", "ABC Construction LLC", None]) == "ABC Construction LLC"
    assert _pick_canonical_firm([None]) is None


def test_most_common_role():
    assert _most_common_role(["contractor", "contractor", "architect"]) == "contractor"
    assert _most_common_role(["architect"]) == "architect"


def test_token_set_similarity():
    assert _token_set_similarity("Alice Smith", "ALICE SMITH") == 1.0
    assert _token_set_similarity("Alice Smith", "Alice B Smith") > 0.5
    assert _token_set_similarity("Alice Smith", "Bob Jones") == 0.0
    assert _token_set_similarity("", "") == 0.0


# ---- Entity Resolution Pipeline Test ----

def test_entity_resolution(db_path):
    """Resolve entities and verify grouping by pts_agent_id and license."""
    stats = resolve_entities(db_path=db_path)

    assert stats["total_contacts"] == 7
    assert stats["total_entities"] > 0
    # All contacts should be resolved
    conn = duckdb.connect(db_path)
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE entity_id IS NULL"
    ).fetchone()[0]
    assert unresolved == 0

    # Alice (AGT001) and Smith Const LLC (LIC001) should be same entity
    alice_entity = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT001' LIMIT 1"
    ).fetchone()[0]
    smith_entity = conn.execute(
        "SELECT entity_id FROM contacts WHERE id = 5"
    ).fetchone()[0]
    assert alice_entity == smith_entity, "Alice and Smith Const LLC should share entity (LIC001 match)"

    # Bob (AGT002) and Jones Arch (LIC002) should be same entity
    bob_entity = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT002' LIMIT 1"
    ).fetchone()[0]
    jones_entity = conn.execute(
        "SELECT entity_id FROM contacts WHERE id = 6"
    ).fetchone()[0]
    assert bob_entity == jones_entity, "Bob and Jones Arch should share entity (LIC002 match)"

    # Eve should be a separate entity
    eve_entity = conn.execute(
        "SELECT entity_id FROM contacts WHERE id = 7"
    ).fetchone()[0]
    assert eve_entity != alice_entity
    assert eve_entity != bob_entity

    conn.close()


# ---- Graph Tests ----

def test_build_graph(db_path):
    """Build graph and verify edges exist."""
    # Must resolve entities first
    resolve_entities(db_path=db_path)
    stats = build_graph(db_path=db_path)

    assert stats["edges"] > 0
    assert stats["resolved_contacts"] == 7

    conn = duckdb.connect(db_path)
    edges = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    assert edges > 0

    # Alice and Bob share permit P001 (and P003 via license merge), so they should have an edge
    alice_eid = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT001' LIMIT 1"
    ).fetchone()[0]
    bob_eid = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT002' LIMIT 1"
    ).fetchone()[0]

    edge = conn.execute(
        """SELECT shared_permits FROM relationships
           WHERE (entity_id_a = ? AND entity_id_b = ?)
              OR (entity_id_a = ? AND entity_id_b = ?)""",
        [alice_eid, bob_eid, bob_eid, alice_eid],
    ).fetchone()
    assert edge is not None, "Alice and Bob should have an edge"
    assert edge[0] >= 1, "Should share at least 1 permit"

    conn.close()


def test_get_neighbors(db_path):
    """Test 1-hop neighbor query."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    conn = duckdb.connect(db_path)
    alice_eid = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT001' LIMIT 1"
    ).fetchone()[0]
    conn.close()

    neighbors = get_neighbors(alice_eid, db_path=db_path)
    assert len(neighbors) > 0
    assert all("entity_id" in n for n in neighbors)
    assert all("shared_permits" in n for n in neighbors)


def test_get_network(db_path):
    """Test N-hop network query."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    conn = duckdb.connect(db_path)
    alice_eid = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT001' LIMIT 1"
    ).fetchone()[0]
    conn.close()

    network = get_network(alice_eid, hops=2, db_path=db_path)
    assert "nodes" in network
    assert "edges" in network
    assert len(network["nodes"]) > 0


# ---- Validation Tests ----

def test_search_entity(db_path):
    """Test entity search by name."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    results = search_entity("Alice", db_path=db_path)
    assert len(results) > 0
    assert results[0]["canonical_name"] is not None
    assert "top_co_occurring" in results[0]


def test_search_entity_not_found(db_path):
    """Test entity search with no matches."""
    resolve_entities(db_path=db_path)
    results = search_entity("ZZZZNOTFOUND", db_path=db_path)
    assert len(results) == 0


def test_entity_network_validation(db_path):
    """Test entity_network from validate module."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    conn = duckdb.connect(db_path)
    alice_eid = conn.execute(
        "SELECT entity_id FROM contacts WHERE pts_agent_id = 'AGT001' LIMIT 1"
    ).fetchone()[0]
    conn.close()

    network = entity_network(alice_eid, hops=1, db_path=db_path)
    assert "nodes" in network
    assert "edges" in network


def test_inspector_contractor_links(db_path):
    """Test tracing inspector to contractor relationships."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    result = inspector_contractor_links("R Santos", db_path=db_path)
    assert result["found"] is True
    assert result["permit_count"] > 0
    assert len(result["linked_entities"]) > 0


def test_inspector_not_found(db_path):
    """Test inspector search with no matches."""
    result = inspector_contractor_links("ZZZZNOTFOUND", db_path=db_path)
    assert result["found"] is False


def test_anomaly_scan(db_path):
    """Test anomaly scan returns structured results."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    result = anomaly_scan(min_permits=1, db_path=db_path)
    assert "summary" in result
    assert "anomalies" in result
    assert "high_permit_volume" in result["anomalies"]
    assert "fast_approvals" in result["anomalies"]


def test_find_clusters(db_path):
    """Test cluster detection."""
    resolve_entities(db_path=db_path)
    build_graph(db_path=db_path)

    # With low thresholds, should find at least one cluster
    clusters = find_clusters(min_size=2, min_edge_weight=1, db_path=db_path)
    assert isinstance(clusters, list)
    # Alice, Bob, Charlie are connected — should form a cluster
    if clusters:
        assert clusters[0]["size"] >= 2
        assert "members" in clusters[0]


# ---- New Dataset Normalizer Tests ----

from src.ingest import (
    _normalize_addenda,
    _normalize_violation,
    _normalize_complaint,
    _normalize_business,
    _extract_addenda_contacts,
    _extract_business_contacts,
)


def test_normalize_addenda():
    record = {
        "primary_key": "PK-001",
        "application_number": "2024-0001",
        "addenda_number": "1",
        "step": "5",
        "station": "PLANNING",
        "arrive": "2024-01-15",
        "assign_date": "2024-01-16",
        "start_date": "2024-01-17",
        "finish_date": "2024-01-20",
        "approved_date": "2024-01-20",
        "plan_checked_by": "Jane Doe",
        "review_results": "Approved",
        "hold_description": "",
        "addenda_status": "Approved",
        "department": "CPC",
        "title": "Plan Check",
        "data_as_of": "2024-06-01",
    }
    result = _normalize_addenda(record, 1)
    assert result[0] == 1  # row_id
    assert result[1] == "PK-001"  # primary_key
    assert result[2] == "2024-0001"  # application_number
    assert result[3] == 1  # addenda_number (int)
    assert result[4] == 5  # step (int)
    assert result[5] == "PLANNING"  # station
    assert result[11] == "Jane Doe"  # plan_checked_by
    assert result[15] == "CPC"  # department
    assert len(result) == 18


def test_normalize_addenda_empty_checker():
    record = {"application_number": "X", "plan_checked_by": "  "}
    result = _normalize_addenda(record, 1)
    assert result[11] is None  # empty string stripped to None


def test_normalize_violation():
    record = {
        "complaint_number": "202400001",
        "item_sequence_number": "1",
        "date_filed": "2024-03-15T00:00:00.000",
        "block": "3512",
        "lot": "001",
        "street_number": "123",
        "street_name": "MAIN",
        "street_suffix": "ST",
        "status": "open",
        "nov_category_description": "building",
        "nov_item_description": "Unpermitted work",
        "neighborhoods_analysis_boundaries": "Mission",
        "supervisor_district": "9",
        "zipcode": "94110",
        "data_as_of": "2024-06-01",
    }
    result = _normalize_violation(record, 42)
    assert result[0] == 42
    assert result[1] == "202400001"
    assert result[10] == "open"  # status
    assert result[15] == "Unpermitted work"  # nov_item_description
    assert len(result) == 20


def test_normalize_complaint():
    record = {
        "complaint_number": "202400099",
        "date_filed": "2024-02-01T00:00:00.000",
        "block": "0200",
        "lot": "005",
        "complaint_description": "Noisy construction",
        "status": "open",
        "data_as_of": "2024-06-01",
    }
    result = _normalize_complaint(record, 10)
    assert result[0] == 10
    assert result[1] == "202400099"
    assert result[12] == "Noisy construction"  # complaint_description
    assert result[13] == "open"  # status
    assert len(result) == 18


def test_normalize_business():
    record = {
        "certificate_number": "1234567",
        "ttxid": "0000-1234",
        "ownership_name": "  Acme Corp  ",
        "dba_name": "  Acme Widgets  ",
        "full_business_address": "  100 Market St  ",
        "city": "San Francisco",
        "state": "CA",
        "business_zip": "94105",
        "dba_start_date": "2020-01-01",
        "location_end_date": None,
        "data_as_of": "2024-06-01",
    }
    result = _normalize_business(record, 5)
    assert result[0] == 5
    assert result[1] == "1234567"  # certificate_number
    assert result[3] == "Acme Corp"  # stripped
    assert result[4] == "Acme Widgets"  # stripped
    assert result[5] == "100 Market St"  # stripped
    assert len(result) == 16


def test_normalize_business_empty_names():
    record = {"ownership_name": "  ", "dba_name": None}
    result = _normalize_business(record, 1)
    assert result[3] is None  # empty string stripped to None
    assert result[4] is None


# ---- Contact Extraction Tests ----

def test_extract_addenda_contacts(db_path):
    """Extract plan_checked_by from addenda into contacts table."""
    conn = duckdb.connect(db_path)

    # Insert test addenda records (18 cols: id, primary_key, application_number,
    # addenda_number, step, station, arrive, assign_date, start_date, finish_date,
    # approved_date, plan_checked_by, review_results, hold_description,
    # addenda_status, department, title, data_as_of)
    conn.executemany(
        "INSERT INTO addenda VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "PK1", "P001", 1, 5, "PLANNING", "2024-01-15", None, None, None, None,
             "Jane Doe", "Approved", None, "approved", "CPC", None, None),
            (2, "PK2", "P001", 1, 6, "FIRE", "2024-01-16", None, None, None, None,
             "John Smith", "Approved", None, "approved", "SFFD", None, None),
            (3, "PK3", "P002", 1, 5, "PLANNING", "2024-02-01", None, None, None, None,
             "Jane Doe", "Approved", None, "approved", "CPC", None, None),
            (4, "PK4", "P003", 1, 5, "PLANNING", "2024-03-01", None, None, None, None,
             None, None, None, "pending", "CPC", None, None),  # NULL checker
        ],
    )

    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM contacts").fetchone()[0]
    count = _extract_addenda_contacts(conn, max_id)

    # Jane Doe on P001 + P002 (2 records), John Smith on P001 (1 record) = 3 total
    # NULL checker row excluded
    assert count == 3

    addenda_contacts = conn.execute(
        "SELECT * FROM contacts WHERE source = 'addenda'"
    ).fetchall()
    assert len(addenda_contacts) == 3

    # Verify roles
    roles = conn.execute(
        "SELECT DISTINCT role FROM contacts WHERE source = 'addenda'"
    ).fetchall()
    assert roles[0][0] == "plan_checker"

    conn.close()


def test_extract_business_contacts(db_path):
    """Extract ownership_name and dba_name from businesses into contacts table."""
    conn = duckdb.connect(db_path)

    # Insert test business records
    conn.executemany(
        "INSERT INTO businesses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # Business 1: owner != dba -> 2 contacts
            (1, "CERT001", "TX001", "Alice Owner", "Alice's Shop",
             "100 Main St", "SF", "CA", "94110",
             "2020-01-01", None, "2020-01-01", None, None, None, None),
            # Business 2: owner == dba -> 1 contact (dedup)
            (2, "CERT002", "TX002", "Bob Owner", "Bob Owner",
             "200 Oak St", "SF", "CA", "94102",
             "2021-01-01", None, "2021-01-01", None, None, None, None),
            # Business 3: only dba, no owner -> 1 contact
            (3, "CERT003", "TX003", None, "Charlie's Place",
             "300 Elm St", "SF", "CA", "94103",
             "2022-01-01", None, "2022-01-01", None, None, None, None),
        ],
    )

    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM contacts").fetchone()[0]
    count = _extract_business_contacts(conn, max_id)

    # Business 1: owner + dba (different) = 2
    # Business 2: owner + dba (same) = 1 (dedup)
    # Business 3: no owner + dba = 1
    # Total = 4
    assert count == 4

    biz_contacts = conn.execute(
        "SELECT * FROM contacts WHERE source = 'business'"
    ).fetchall()
    assert len(biz_contacts) == 4

    # Verify roles present
    roles = {r[0] for r in conn.execute(
        "SELECT DISTINCT role FROM contacts WHERE source = 'business'"
    ).fetchall()}
    assert "owner" in roles
    assert "dba" in roles

    conn.close()


def test_extract_addenda_contacts_empty_table(db_path):
    """Extraction from empty addenda table returns 0."""
    conn = duckdb.connect(db_path)
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM contacts").fetchone()[0]
    count = _extract_addenda_contacts(conn, max_id)
    assert count == 0
    conn.close()


def test_extract_business_contacts_empty_table(db_path):
    """Extraction from empty businesses table returns 0."""
    conn = duckdb.connect(db_path)
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM contacts").fetchone()[0]
    count = _extract_business_contacts(conn, max_id)
    assert count == 0
    conn.close()
