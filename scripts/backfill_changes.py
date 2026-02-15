"""Backfill permit_changes from existing permits table date fields.

Reconstructs historical status transitions by extracting change events
from filed_date, approved_date, issued_date, completed_date, and current
status + status_date.  All rows are marked with source='backfill'.

Usage:
    python -m scripts.backfill_changes              # Full backfill
    python -m scripts.backfill_changes --dry-run     # Count only, no writes
    python -m scripts.backfill_changes --limit 1000  # Process first N permits
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
from datetime import date

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_connection, BACKEND, query, execute_write, init_user_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Ordered status transitions — each date field implies a known transition.
# (date_field, new_status, inferred_old_status)
TRANSITIONS = [
    ("filed_date",     "filed",     None),
    ("approved_date",  "approved",  "filed"),
    ("issued_date",    "issued",    "approved"),
    ("completed_date", "completed", "issued"),
]

BATCH_SIZE = 5000


def _parse_date(text: str | None) -> date | None:
    """Parse a TEXT date field to a Python date.  Returns None on failure."""
    if not text:
        return None
    try:
        # ISO format: "2024-01-15T00:00:00.000" or "2024-01-15"
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


def _backfill_duckdb_fast(conn, limit: int | None = None, dry_run: bool = False) -> int:
    """DuckDB fast path: pure SQL INSERT...SELECT using UNION ALL.

    DuckDB can process millions of rows natively in seconds.
    Each transition (filed, approved, issued, completed) becomes a SELECT
    that UNIONs into one big INSERT.
    """
    limit_clause = f" LIMIT {int(limit)}" if limit else ""

    # Build a CTE for the source permits, then UNION ALL four selects
    # one per transition type.
    union_parts = []
    for date_field, new_status, old_status in TRANSITIONS:
        old_expr = f"'{old_status}'" if old_status else "NULL"
        change_type = "'status_change'" if old_status else "'new_permit'"
        is_new = "FALSE" if old_status else "TRUE"
        union_parts.append(f"""
            SELECT
                permit_number,
                TRY_CAST(LEFT({date_field}, 10) AS DATE) AS change_date,
                {old_expr} AS old_status,
                '{new_status}' AS new_status,
                {date_field} AS old_status_date,
                {date_field} AS new_status_date,
                {change_type} AS change_type,
                {is_new} AS is_new_permit,
                'backfill' AS source,
                permit_type_definition AS permit_type,
                street_number,
                street_name,
                neighborhood,
                block,
                lot
            FROM src
            WHERE {date_field} IS NOT NULL
              AND TRY_CAST(LEFT({date_field}, 10) AS DATE) IS NOT NULL
        """)

    union_sql = " UNION ALL ".join(union_parts)
    full_sql = f"""
        WITH src AS (SELECT * FROM permits{limit_clause})
        {union_sql}
    """

    if dry_run:
        count_sql = f"SELECT COUNT(*) FROM ({full_sql})"
        result = conn.execute(count_sql).fetchone()
        total = result[0] if result else 0
        logger.info("DRY RUN: would insert %d change rows", total)
        return total

    # Clear previous backfill
    conn.execute("DELETE FROM permit_changes WHERE source = 'backfill'")
    logger.info("Cleared previous backfill rows")

    # Insert with auto-generated IDs via a sequence trick
    # First get max existing change_id
    max_id = conn.execute("SELECT COALESCE(MAX(change_id), 0) FROM permit_changes").fetchone()[0]

    insert_sql = f"""
        INSERT INTO permit_changes
            (change_id, permit_number, change_date, old_status, new_status,
             old_status_date, new_status_date, change_type, is_new_permit,
             source, permit_type, street_number, street_name,
             neighborhood, block, lot)
        SELECT
            {max_id} + ROW_NUMBER() OVER () AS change_id,
            permit_number, change_date, old_status, new_status,
            old_status_date, new_status_date, change_type, is_new_permit,
            source, permit_type, street_number, street_name,
            neighborhood, block, lot
        FROM ({full_sql}) sub
        ORDER BY change_date
    """

    conn.execute(insert_sql)
    count_result = conn.execute(
        "SELECT COUNT(*) FROM permit_changes WHERE source = 'backfill'"
    ).fetchone()
    inserted = count_result[0] if count_result else 0
    logger.info("Backfill complete: %d change rows inserted", inserted)
    return inserted


def backfill(limit: int | None = None, dry_run: bool = False) -> int:
    """Run the backfill.  Returns count of change rows inserted."""

    # Ensure permit_changes table exists (DuckDB dev mode)
    if BACKEND == "duckdb":
        init_user_schema()

    # DuckDB fast path: pure SQL, no Python row iteration
    if BACKEND == "duckdb":
        conn = get_connection()
        try:
            return _backfill_duckdb_fast(conn, limit, dry_run)
        finally:
            conn.close()

    # Postgres path: Python row iteration with psycopg2 execute_values
    return _backfill_postgres(limit, dry_run)


def _backfill_postgres(limit: int | None = None, dry_run: bool = False) -> int:
    """Postgres path: iterate rows in Python, batch insert with execute_values."""

    limit_clause = f" LIMIT {int(limit)}" if limit else ""
    sql = (
        "SELECT permit_number, status, status_date, filed_date, approved_date, "
        "issued_date, completed_date, permit_type_definition, street_number, "
        f"street_name, neighborhood, block, lot FROM permits{limit_clause}"
    )
    rows = query(sql)
    logger.info("Fetched %d permits to process", len(rows))

    if dry_run:
        total = 0
        for row in rows:
            for date_field, _, _ in TRANSITIONS:
                col_idx = ["permit_number", "status", "status_date", "filed_date",
                           "approved_date", "issued_date", "completed_date",
                           "permit_type_definition", "street_number", "street_name",
                           "neighborhood", "block", "lot"].index(date_field)
                if _parse_date(row[col_idx]):
                    total += 1
        logger.info("DRY RUN: would insert %d change rows", total)
        return total

    execute_write("DELETE FROM permit_changes WHERE source = %s", ("backfill",))
    logger.info("Cleared previous backfill rows")

    inserted = 0
    batch = []

    for row in rows:
        (permit_number, status, status_date, filed_date, approved_date,
         issued_date, completed_date, permit_type, street_number,
         street_name, neighborhood, block, lot) = row

        for date_field, new_status, old_status in TRANSITIONS:
            date_val_text = {
                "filed_date": filed_date,
                "approved_date": approved_date,
                "issued_date": issued_date,
                "completed_date": completed_date,
            }[date_field]

            parsed = _parse_date(date_val_text)
            if not parsed:
                continue

            batch.append((
                permit_number,
                parsed,
                old_status,
                new_status,
                date_val_text,
                date_val_text,
                "status_change" if old_status else "new_permit",
                old_status is None,
                "backfill",
                permit_type,
                street_number,
                street_name,
                neighborhood,
                block,
                lot,
            ))

            if len(batch) >= BATCH_SIZE:
                inserted += _flush_batch_postgres(batch)
                logger.info("Inserted %d rows so far...", inserted)
                batch = []

    if batch:
        inserted += _flush_batch_postgres(batch)

    logger.info("Backfill complete: %d change rows inserted", inserted)
    return inserted


def _flush_batch_postgres(batch: list[tuple]) -> int:
    """Insert a batch of change rows (Postgres only)."""
    conn = get_connection()
    try:
        from psycopg2.extras import execute_values
        sql = """
            INSERT INTO permit_changes
            (permit_number, change_date, old_status, new_status,
             old_status_date, new_status_date, change_type, is_new_permit,
             source, permit_type, street_number, street_name,
             neighborhood, block, lot)
            VALUES %s
        """
        with conn.cursor() as cur:
            execute_values(cur, sql, batch, page_size=BATCH_SIZE)
            conn.commit()
        return len(batch)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill permit_changes from date fields")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no writes")
    parser.add_argument("--limit", type=int, default=None, help="Process first N permits")
    args = parser.parse_args()

    count = backfill(limit=args.limit, dry_run=args.dry_run)
    logger.info("Total: %d rows %s", count, "(dry run)" if args.dry_run else "inserted")


if __name__ == "__main__":
    main()
