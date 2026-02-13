"""DuckDB connection and schema management for sf-permits-mcp."""

import duckdb
import os
from pathlib import Path

DB_PATH = os.environ.get(
    "SF_PERMITS_DB",
    str(Path(__file__).parent.parent / "data" / "sf_permits.duckdb"),
)


def get_connection(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection, creating the database if needed."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = duckdb.connect(path)
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            permit_number TEXT NOT NULL,
            role TEXT,
            name TEXT,
            first_name TEXT,
            last_name TEXT,
            firm_name TEXT,
            pts_agent_id TEXT,
            license_number TEXT,
            sf_business_license TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zipcode TEXT,
            is_applicant TEXT,
            from_date TEXT,
            entity_id INTEGER,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            canonical_firm TEXT,
            entity_type TEXT,
            pts_agent_id TEXT,
            license_number TEXT,
            sf_business_license TEXT,
            resolution_method TEXT,
            resolution_confidence TEXT,
            contact_count INTEGER,
            permit_count INTEGER,
            source_datasets TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            entity_id_a INTEGER,
            entity_id_b INTEGER,
            shared_permits INTEGER,
            permit_numbers TEXT,
            permit_types TEXT,
            date_range_start TEXT,
            date_range_end TEXT,
            total_estimated_cost DOUBLE,
            neighborhoods TEXT,
            PRIMARY KEY (entity_id_a, entity_id_b)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS permits (
            permit_number TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_type_definition TEXT,
            status TEXT,
            status_date TEXT,
            description TEXT,
            filed_date TEXT,
            issued_date TEXT,
            approved_date TEXT,
            completed_date TEXT,
            estimated_cost DOUBLE,
            revised_cost DOUBLE,
            existing_use TEXT,
            proposed_use TEXT,
            existing_units INTEGER,
            proposed_units INTEGER,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            zipcode TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            block TEXT,
            lot TEXT,
            adu TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY,
            reference_number TEXT,
            reference_number_type TEXT,
            inspector TEXT,
            scheduled_date TEXT,
            result TEXT,
            inspection_description TEXT,
            block TEXT,
            lot TEXT,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            zipcode TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            dataset_id TEXT PRIMARY KEY,
            dataset_name TEXT,
            last_fetched TEXT,
            records_fetched INTEGER,
            last_record_count INTEGER
        )
    """)

    # Create indexes
    _create_indexes(conn)


def _create_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create indexes on key join columns."""
    indexes = [
        ("idx_contacts_permit", "contacts", "permit_number"),
        ("idx_contacts_pts_agent", "contacts", "pts_agent_id"),
        ("idx_contacts_license", "contacts", "license_number"),
        ("idx_contacts_sf_biz", "contacts", "sf_business_license"),
        ("idx_contacts_entity", "contacts", "entity_id"),
        ("idx_contacts_role", "contacts", "role"),
        ("idx_contacts_name", "contacts", "name"),
        ("idx_inspections_ref", "inspections", "reference_number"),
        ("idx_inspections_inspector", "inspections", "inspector"),
        ("idx_inspections_block_lot", "inspections", "block, lot"),
        ("idx_permits_neighborhood", "permits", "neighborhood"),
        ("idx_permits_block_lot", "permits", "block, lot"),
        ("idx_relationships_a", "relationships", "entity_id_a"),
        ("idx_relationships_b", "relationships", "entity_id_b"),
        ("idx_entities_name", "entities", "canonical_name"),
        ("idx_entities_license", "entities", "license_number"),
        ("idx_entities_pts", "entities", "pts_agent_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
        except duckdb.CatalogException:
            pass  # Index already exists
