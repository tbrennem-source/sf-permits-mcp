"""Push local DuckDB data to production Postgres via /cron/migrate-data endpoint.

Usage:
    python scripts/push_to_prod.py --table violations
    python scripts/push_to_prod.py --table complaints
    python scripts/push_to_prod.py --table businesses
    python scripts/push_to_prod.py --table addenda
    python scripts/push_to_prod.py --all
"""

import argparse
import duckdb
import httpx
import json
import time
import sys

PROD_URL = "https://sfpermits-ai-production.up.railway.app/cron/migrate-data"
DB_PATH = "data/sf_permits.duckdb"
BATCH_SIZE = 5000  # rows per HTTP request

# Column definitions matching postgres_schema.sql
TABLE_COLUMNS = {
    "addenda": [
        "id", "primary_key", "application_number", "addenda_number", "step",
        "station", "arrive", "assign_date", "start_date", "finish_date",
        "approved_date", "plan_checked_by", "review_results", "hold_description",
        "addenda_status", "department", "title", "data_as_of",
    ],
    "violations": [
        "id", "complaint_number", "item_sequence_number", "date_filed",
        "block", "lot", "street_number", "street_name", "street_suffix",
        "unit", "status", "receiving_division", "assigned_division",
        "nov_category_description", "item", "nov_item_description",
        "neighborhood", "supervisor_district", "zipcode", "data_as_of",
    ],
    "complaints": [
        "id", "complaint_number", "date_filed", "date_abated",
        "block", "lot", "parcel_number", "street_number", "street_name",
        "street_suffix", "unit", "zip_code", "complaint_description",
        "status", "nov_type", "receiving_division", "assigned_division",
        "data_as_of",
    ],
    "businesses": [
        "id", "certificate_number", "ttxid", "ownership_name", "dba_name",
        "full_business_address", "city", "state", "business_zip",
        "dba_start_date", "dba_end_date", "location_start_date",
        "location_end_date", "parking_tax", "transient_occupancy_tax",
        "data_as_of",
    ],
}


def push_table(table: str, cron_secret: str):
    """Read all rows from DuckDB and push to prod in batches."""
    columns = TABLE_COLUMNS[table]
    cols_sql = ", ".join(columns)

    conn = duckdb.connect(DB_PATH, read_only=True)
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"\n=== Pushing {table}: {total:,} rows ===")

    if total == 0:
        print(f"  No data in {table}, skipping.")
        conn.close()
        return

    client = httpx.Client(timeout=120.0)
    headers = {"Authorization": f"Bearer {cron_secret}"}

    offset = 0
    first_batch = True
    start_time = time.time()

    while offset < total:
        rows = conn.execute(
            f"SELECT {cols_sql} FROM {table} LIMIT {BATCH_SIZE} OFFSET {offset}"
        ).fetchall()

        if not rows:
            break

        # Convert to list of lists (JSON-serializable)
        row_data = []
        for row in rows:
            row_data.append([
                v if v is None or isinstance(v, (str, int, float, bool))
                else str(v)
                for v in row
            ])

        payload = {
            "table": table,
            "columns": columns,
            "rows": row_data,
            "truncate": first_batch,
        }

        try:
            resp = client.post(PROD_URL, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                print(f"  ERROR at offset {offset}: {result.get('error')}")
                sys.exit(1)
        except httpx.HTTPStatusError as e:
            print(f"  HTTP {e.response.status_code} at offset {offset}: {e.response.text[:200]}")
            sys.exit(1)
        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            sys.exit(1)

        offset += len(rows)
        elapsed = time.time() - start_time
        rate = offset / elapsed if elapsed > 0 else 0
        pct = offset * 100 / total
        print(f"  Pushed {offset:,}/{total:,} ({pct:.0f}%) — {rate:.0f} rows/sec — {elapsed:.1f}s")
        first_batch = False

    elapsed = time.time() - start_time
    print(f"  Done: {offset:,} rows in {elapsed:.1f}s")
    conn.close()
    client.close()


def main():
    parser = argparse.ArgumentParser(description="Push DuckDB data to prod Postgres")
    parser.add_argument("--table", choices=list(TABLE_COLUMNS.keys()), help="Table to push")
    parser.add_argument("--all", action="store_true", help="Push all 4 tables")
    parser.add_argument("--secret", help="CRON_SECRET (or set CRON_SECRET env var)")
    args = parser.parse_args()

    import os
    cron_secret = args.secret or os.environ.get("CRON_SECRET")
    if not cron_secret:
        print("ERROR: Provide --secret or set CRON_SECRET env var")
        sys.exit(1)

    tables = list(TABLE_COLUMNS.keys()) if args.all else [args.table] if args.table else []
    if not tables:
        print("ERROR: Specify --table or --all")
        sys.exit(1)

    overall_start = time.time()
    for table in tables:
        push_table(table, cron_secret)

    elapsed = time.time() - overall_start
    print(f"\n=== All done in {elapsed:.1f}s ===")


if __name__ == "__main__":
    main()
