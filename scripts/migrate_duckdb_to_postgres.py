#!/usr/bin/env python3
"""Migrate DuckDB data to PostgreSQL (Railway).

Option A: straight copy of existing DuckDB tables.
Keeps all columns as-is, minimal transformation.

Usage:
    export DATABASE_URL="postgresql://user:pass@host:port/railway"
    python scripts/migrate_duckdb_to_postgres.py

Or with explicit paths:
    python scripts/migrate_duckdb_to_postgres.py --duckdb data/sf_permits.duckdb

Date-filtered (fits in 500MB Railway volume):
    python scripts/migrate_duckdb_to_postgres.py --since 2018-01-01
"""

import argparse
import os
import sys
import time
from pathlib import Path

import duckdb
import psycopg2
from psycopg2.extras import execute_values

# Default paths
DEFAULT_DUCKDB = str(Path(__file__).parent.parent / "data" / "sf_permits.duckdb")
BATCH_SIZE = 10_000


def get_pg_conn(database_url: str):
    """Create a Postgres connection."""
    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    return conn


def create_schema(pg_conn):
    """Run the schema SQL to create tables."""
    schema_file = Path(__file__).parent / "postgres_schema.sql"
    sql = schema_file.read_text()
    with pg_conn.cursor() as cur:
        cur.execute(sql)
    pg_conn.commit()
    print("✅ Schema created")


def migrate_table(duck_conn, pg_conn, table_name: str, select_sql: str,
                  insert_sql: str, columns: list[str]):
    """Migrate a single table from DuckDB to Postgres."""
    start = time.time()
    rows = duck_conn.execute(select_sql).fetchall()
    total = len(rows)
    print(f"  Migrating {table_name}: {total:,} rows...")

    # Truncate first (idempotent re-runs)
    with pg_conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table_name} CASCADE")

    # Bulk insert
    placeholders = ", ".join(["%s"] * len(columns))
    cols = ", ".join(columns)
    template = f"({placeholders})"

    with pg_conn.cursor() as cur:
        for i in range(0, total, BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            # Convert tuples to lists for execute_values
            execute_values(
                cur,
                f"INSERT INTO {table_name} ({cols}) VALUES %s",
                batch,
                template=template,
                page_size=BATCH_SIZE,
            )
            done = min(i + BATCH_SIZE, total)
            if done % 100_000 == 0 or done == total:
                print(f"    {done:,} / {total:,}")
    pg_conn.commit()

    elapsed = time.time() - start
    print(f"  ✅ {table_name}: {total:,} rows in {elapsed:.1f}s")
    return total


def verify_counts(duck_conn, pg_conn, tables: list[str]):
    """Verify row counts match between DuckDB and Postgres."""
    print("\n📊 Verification:")
    all_match = True
    for table in tables:
        duck_count = duck_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        with pg_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = cur.fetchone()[0]
        match = "✅" if duck_count == pg_count else "❌"
        if duck_count != pg_count:
            all_match = False
        print(f"  {match} {table}: DuckDB={duck_count:,}  Postgres={pg_count:,}")
    return all_match


def verify_pg_counts(pg_conn, tables: list[str]):
    """Print row counts for all Postgres tables."""
    print("\n📊 Postgres row counts:")
    for table in tables:
        with pg_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
        print(f"  {table}: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Migrate DuckDB to PostgreSQL")
    parser.add_argument("--duckdb", default=DEFAULT_DUCKDB, help="Path to DuckDB file")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"),
                        help="PostgreSQL connection URL")
    parser.add_argument("--schema-only", action="store_true",
                        help="Only create schema, don't migrate data")
    parser.add_argument("--since", default=None,
                        help="Only migrate data from this date forward (YYYY-MM-DD). "
                             "Useful for fitting in smaller volumes (e.g., --since 2018-01-01 for 500MB).")
    args = parser.parse_args()

    if not args.database_url:
        print("❌ Set DATABASE_URL or pass --database-url")
        sys.exit(1)

    if not Path(args.duckdb).exists():
        print(f"❌ DuckDB file not found: {args.duckdb}")
        sys.exit(1)

    print(f"DuckDB: {args.duckdb}")
    print(f"Postgres: {args.database_url.split('@')[1] if '@' in args.database_url else '(local)'}")
    if args.since:
        print(f"Date filter: >= {args.since}")
    print()

    duck_conn = duckdb.connect(args.duckdb, read_only=True)
    pg_conn = get_pg_conn(args.database_url)

    # Step 1: Create schema
    create_schema(pg_conn)

    if args.schema_only:
        print("\n🏗️ Schema-only mode — skipping data migration")
        duck_conn.close()
        pg_conn.close()
        return

    # Build date filter clauses
    since = args.since  # e.g. "2018-01-01"

    # Step 2: Migrate each table
    print("\n📦 Migrating data...")

    # --- permits ---
    PERMITS_COLS = [
        "permit_number", "permit_type", "permit_type_definition", "status",
        "status_date", "description", "filed_date", "issued_date",
        "approved_date", "completed_date", "estimated_cost", "revised_cost",
        "existing_use", "proposed_use", "existing_units", "proposed_units",
        "street_number", "street_name", "street_suffix", "zipcode",
        "neighborhood", "supervisor_district", "block", "lot", "adu", "data_as_of",
    ]
    permits_where = ""
    if since:
        permits_where = f" WHERE filed_date IS NOT NULL AND filed_date::DATE >= '{since}'"
    migrate_table(
        duck_conn, pg_conn, "permits",
        f"SELECT {', '.join(PERMITS_COLS)} FROM permits{permits_where}",
        None,  # handled inline
        PERMITS_COLS,
    )

    # --- contacts (join to filtered permits if --since) ---
    CONTACTS_COLS = [
        "id", "source", "permit_number", "role", "name", "first_name",
        "last_name", "firm_name", "pts_agent_id", "license_number",
        "sf_business_license", "phone", "address", "city", "state",
        "zipcode", "is_applicant", "from_date", "entity_id", "data_as_of",
    ]
    if since:
        contacts_sql = f"""
            SELECT {', '.join(['c.' + c for c in CONTACTS_COLS])}
            FROM contacts c
            WHERE c.permit_number IN (
                SELECT permit_number FROM permits
                WHERE filed_date IS NOT NULL AND filed_date::DATE >= '{since}'
            )
        """
    else:
        contacts_sql = f"SELECT {', '.join(CONTACTS_COLS)} FROM contacts"
    migrate_table(
        duck_conn, pg_conn, "contacts",
        contacts_sql,
        None,
        CONTACTS_COLS,
    )

    # --- entities (all entities referenced by filtered contacts, or all) ---
    ENTITIES_COLS = [
        "entity_id", "canonical_name", "canonical_firm", "entity_type",
        "pts_agent_id", "license_number", "sf_business_license",
        "resolution_method", "resolution_confidence", "contact_count",
        "permit_count", "source_datasets",
    ]
    if since:
        entities_sql = f"""
            SELECT {', '.join(['e.' + c for c in ENTITIES_COLS])}
            FROM entities e
            WHERE e.entity_id IN (
                SELECT DISTINCT c.entity_id FROM contacts c
                WHERE c.entity_id IS NOT NULL
                AND c.permit_number IN (
                    SELECT permit_number FROM permits
                    WHERE filed_date IS NOT NULL AND filed_date::DATE >= '{since}'
                )
            )
        """
    else:
        entities_sql = f"SELECT {', '.join(ENTITIES_COLS)} FROM entities"
    migrate_table(
        duck_conn, pg_conn, "entities",
        entities_sql,
        None,
        ENTITIES_COLS,
    )

    # --- relationships (between filtered entities, or all) ---
    REL_COLS = [
        "entity_id_a", "entity_id_b", "shared_permits", "permit_numbers",
        "permit_types", "date_range_start", "date_range_end",
        "total_estimated_cost", "neighborhoods",
    ]
    if since:
        # Include relationships where both entities are in our filtered set
        rel_sql = f"""
            SELECT {', '.join(['r.' + c for c in REL_COLS])}
            FROM relationships r
            WHERE r.entity_id_a IN (
                SELECT DISTINCT c.entity_id FROM contacts c
                WHERE c.entity_id IS NOT NULL
                AND c.permit_number IN (
                    SELECT permit_number FROM permits
                    WHERE filed_date IS NOT NULL AND filed_date::DATE >= '{since}'
                )
            )
        """
    else:
        rel_sql = f"SELECT {', '.join(REL_COLS)} FROM relationships"
    migrate_table(
        duck_conn, pg_conn, "relationships",
        rel_sql,
        None,
        REL_COLS,
    )

    # --- inspections ---
    INSPECTIONS_COLS = [
        "id", "reference_number", "reference_number_type", "inspector",
        "scheduled_date", "result", "inspection_description", "block",
        "lot", "street_number", "street_name", "street_suffix",
        "neighborhood", "supervisor_district", "zipcode", "data_as_of",
    ]
    insp_where = ""
    if since:
        insp_where = f" WHERE scheduled_date IS NOT NULL AND scheduled_date::DATE >= '{since}'"
    migrate_table(
        duck_conn, pg_conn, "inspections",
        f"SELECT {', '.join(INSPECTIONS_COLS)} FROM inspections{insp_where}",
        None,
        INSPECTIONS_COLS,
    )

    # --- ingest_log (always all) ---
    INGEST_COLS = [
        "dataset_id", "dataset_name", "last_fetched",
        "records_fetched", "last_record_count",
    ]
    migrate_table(
        duck_conn, pg_conn, "ingest_log",
        f"SELECT {', '.join(INGEST_COLS)} FROM ingest_log",
        None,
        INGEST_COLS,
    )

    # --- timeline_stats ---
    TS_COLS = [
        "permit_number", "permit_type_definition", "review_path",
        "neighborhood", "estimated_cost", "revised_cost", "cost_bracket",
        "filed", "issued", "completed", "days_to_issuance",
        "days_to_completion", "supervisor_district",
    ]
    ts_where = ""
    if since:
        ts_where = f" WHERE filed >= '{since}'"
    migrate_table(
        duck_conn, pg_conn, "timeline_stats",
        f"SELECT {', '.join(TS_COLS)} FROM timeline_stats{ts_where}",
        None,
        TS_COLS,
    )

    # Step 3: Verify
    tables = ["permits", "contacts", "entities", "relationships",
              "inspections", "ingest_log", "timeline_stats"]

    if since:
        # Can't compare exact counts with date filter, just show what we loaded
        verify_pg_counts(pg_conn, tables)
        # Check DB size
        with pg_conn.cursor() as cur:
            cur.execute("SELECT pg_size_pretty(pg_database_size('railway'))")
            db_size = cur.fetchone()[0]
        print(f"\n📦 Total Postgres DB size: {db_size}")
        print(f"\n🎉 Migration complete! (filtered: >= {since})")
    else:
        all_ok = verify_counts(duck_conn, pg_conn, tables)
        if all_ok:
            print("\n🎉 Migration complete! All row counts match.")
        else:
            print("\n⚠️ Migration complete but some row counts differ!")
            sys.exit(1)

    duck_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
