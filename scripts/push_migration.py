#!/usr/bin/env python3
"""Push DuckDB bulk data to production Postgres via HTTP migration endpoints.

Since Railway's pgvector-db is only reachable from inside Railway's network,
this script pushes data through the deployed Flask app's /cron/migrate-* endpoints.

Usage:
    export CRON_SECRET="your-cron-secret"
    python scripts/push_migration.py

    # Or with explicit options:
    python scripts/push_migration.py --duckdb data/sf_permits.duckdb --base-url https://sfpermits-ai-production.up.railway.app

    # Schema only (no data):
    python scripts/push_migration.py --schema-only

    # Single table:
    python scripts/push_migration.py --table permits
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import duckdb
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DUCKDB = str(Path(__file__).parent.parent / "data" / "sf_permits.duckdb")
DEFAULT_BASE_URL = "https://sfpermits-ai-production.up.railway.app"
BATCH_SIZE = 5000
REQUEST_TIMEOUT = 120  # seconds per batch

# Table definitions (column lists match scripts/migrate_duckdb_to_postgres.py)
TABLES = [
    {
        "name": "permits",
        "columns": [
            "permit_number", "permit_type", "permit_type_definition", "status",
            "status_date", "description", "filed_date", "issued_date",
            "approved_date", "completed_date", "estimated_cost", "revised_cost",
            "existing_use", "proposed_use", "existing_units", "proposed_units",
            "street_number", "street_name", "street_suffix", "zipcode",
            "neighborhood", "supervisor_district", "block", "lot", "adu", "data_as_of",
        ],
    },
    {
        "name": "contacts",
        "columns": [
            "id", "source", "permit_number", "role", "name", "first_name",
            "last_name", "firm_name", "pts_agent_id", "license_number",
            "sf_business_license", "phone", "address", "city", "state",
            "zipcode", "is_applicant", "from_date", "entity_id", "data_as_of",
        ],
    },
    {
        "name": "entities",
        "columns": [
            "entity_id", "canonical_name", "canonical_firm", "entity_type",
            "pts_agent_id", "license_number", "sf_business_license",
            "resolution_method", "resolution_confidence", "contact_count",
            "permit_count", "source_datasets",
        ],
    },
    {
        "name": "relationships",
        "columns": [
            "entity_id_a", "entity_id_b", "shared_permits", "permit_numbers",
            "permit_types", "date_range_start", "date_range_end",
            "total_estimated_cost", "neighborhoods",
        ],
    },
    {
        "name": "inspections",
        "columns": [
            "id", "reference_number", "reference_number_type", "inspector",
            "scheduled_date", "result", "inspection_description", "block",
            "lot", "street_number", "street_name", "street_suffix",
            "neighborhood", "supervisor_district", "zipcode", "data_as_of",
        ],
    },
    {
        "name": "timeline_stats",
        "columns": [
            "permit_number", "permit_type_definition", "review_path",
            "neighborhood", "estimated_cost", "revised_cost", "cost_bracket",
            "filed", "issued", "completed", "days_to_issuance",
            "days_to_completion", "supervisor_district",
        ],
    },
    {
        "name": "ingest_log",
        "columns": [
            "dataset_id", "dataset_name", "last_fetched",
            "records_fetched", "last_record_count",
        ],
    },
]


def _convert_row(row):
    """Convert DuckDB row values to JSON-safe types."""
    result = []
    for val in row:
        if val is None:
            result.append(None)
        elif isinstance(val, (int, float, str, bool)):
            result.append(val)
        else:
            # date, datetime, decimal, etc. → string
            result.append(str(val))
    return result


def create_schema(base_url: str, secret: str) -> bool:
    """POST to /cron/migrate-schema to create tables."""
    print("Creating schema...")
    resp = requests.post(
        f"{base_url}/cron/migrate-schema",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=60,
    )
    data = resp.json()
    if data.get("ok"):
        print(f"  Schema created. Tables: {', '.join(data.get('tables', []))}")
        return True
    else:
        print(f"  Schema creation failed: {data.get('error')}")
        return False


def push_table(duck_conn, base_url: str, secret: str, table_def: dict) -> int:
    """Read a table from DuckDB and push it in batches to the migration endpoint."""
    name = table_def["name"]
    columns = table_def["columns"]

    # Read all rows
    sql = f"SELECT {', '.join(columns)} FROM {name}"
    rows = duck_conn.execute(sql).fetchall()
    total = len(rows)

    if total == 0:
        print(f"  {name}: 0 rows (skipping)")
        return 0

    print(f"  {name}: {total:,} rows to migrate...")
    start = time.time()
    migrated = 0
    errors = 0

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        # Convert to JSON-safe format
        json_rows = [_convert_row(r) for r in batch]

        payload = {
            "table": name,
            "columns": columns,
            "rows": json_rows,
            "truncate": (i == 0),  # TRUNCATE on first batch only
        }

        try:
            resp = requests.post(
                f"{base_url}/cron/migrate-data",
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload),
                timeout=REQUEST_TIMEOUT,
            )
            data = resp.json()
            if data.get("ok"):
                migrated += data.get("rows_inserted", len(batch))
            else:
                print(f"    Batch error at row {i}: {data.get('error')}")
                errors += 1
                if errors >= 3:
                    print(f"    Too many errors, stopping {name}")
                    break
        except requests.Timeout:
            print(f"    Timeout at row {i}, retrying...")
            # Retry once
            try:
                resp = requests.post(
                    f"{base_url}/cron/migrate-data",
                    headers={
                        "Authorization": f"Bearer {secret}",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=REQUEST_TIMEOUT * 2,
                )
                data = resp.json()
                if data.get("ok"):
                    migrated += data.get("rows_inserted", len(batch))
                else:
                    errors += 1
            except Exception as e:
                print(f"    Retry failed: {e}")
                errors += 1
        except Exception as e:
            print(f"    Error at row {i}: {e}")
            errors += 1

        # Progress
        done = min(i + BATCH_SIZE, total)
        elapsed = time.time() - start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"    {done:,}/{total:,} ({done*100//total}%) "
              f"- {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining", end="\r")

    elapsed = time.time() - start
    status = "OK" if errors == 0 else f"WARN ({errors} errors)"
    print(f"\n  {name}: {migrated:,}/{total:,} rows in {elapsed:.1f}s [{status}]")
    return migrated


def verify(base_url: str) -> dict:
    """Check /health endpoint for table row counts."""
    resp = requests.get(f"{base_url}/health", timeout=30)
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Push DuckDB bulk data to production Postgres via HTTP"
    )
    parser.add_argument("--duckdb", default=DEFAULT_DUCKDB,
                        help="Path to DuckDB file")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", DEFAULT_BASE_URL),
                        help="Production app URL")
    parser.add_argument("--cron-secret", default=os.environ.get("CRON_SECRET"),
                        help="CRON_SECRET for auth")
    parser.add_argument("--schema-only", action="store_true",
                        help="Only create schema, don't push data")
    parser.add_argument("--table", default=None,
                        help="Migrate a single table (e.g., 'permits')")
    args = parser.parse_args()

    if not args.cron_secret:
        print("Set CRON_SECRET env var or pass --cron-secret")
        sys.exit(1)

    if not Path(args.duckdb).exists():
        print(f"DuckDB file not found: {args.duckdb}")
        sys.exit(1)

    print(f"DuckDB: {args.duckdb}")
    print(f"Target: {args.base_url}")
    print()

    # Step 1: Create schema
    if not create_schema(args.base_url, args.cron_secret):
        sys.exit(1)

    if args.schema_only:
        print("\nSchema-only mode — done.")
        sys.exit(0)

    # Step 2: Push data
    duck_conn = duckdb.connect(args.duckdb, read_only=True)
    total_start = time.time()
    total_rows = 0

    tables_to_migrate = TABLES
    if args.table:
        tables_to_migrate = [t for t in TABLES if t["name"] == args.table]
        if not tables_to_migrate:
            print(f"Unknown table: {args.table}")
            print(f"Available: {', '.join(t['name'] for t in TABLES)}")
            sys.exit(1)

    print(f"\nMigrating {len(tables_to_migrate)} tables...")

    for table_def in tables_to_migrate:
        rows = push_table(duck_conn, args.base_url, args.cron_secret, table_def)
        total_rows += rows

    duck_conn.close()

    total_elapsed = time.time() - total_start
    print(f"\nMigration complete: {total_rows:,} rows in {total_elapsed:.0f}s")

    # Step 3: Verify
    print("\nVerifying via /health...")
    health = verify(args.base_url)
    tables = health.get("tables", {})
    print(f"  DB connected: {health.get('db_connected')}")
    bulk_tables = ["permits", "contacts", "entities", "relationships",
                   "inspections", "timeline_stats", "ingest_log"]
    for t in bulk_tables:
        count = tables.get(t, "NOT FOUND")
        print(f"  {t}: {count:,}" if isinstance(count, int) else f"  {t}: {count}")


if __name__ == "__main__":
    main()
