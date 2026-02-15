"""Nightly delta fetch: detect permit changes via SODA API.

Queries SODA for permits whose status_date is more recent than our last run,
compares against current DB state, and inserts diffs into permit_changes.

Usage:
    python -m scripts.nightly_changes                  # Normal run
    python -m scripts.nightly_changes --lookback 3     # Check last 3 days
    python -m scripts.nightly_changes --dry-run        # Preview only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_connection, BACKEND, query, query_one, execute_write, init_user_schema
from src.soda_client import SODAClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BUILDING_PERMITS_ENDPOINT = "i98e-djp9"
INSPECTIONS_ENDPOINT = "vckc-dh2h"
PAGE_SIZE = 10_000


def _parse_date(text: str | None) -> date | None:
    """Parse a TEXT date to a Python date."""
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


async def fetch_recent_permits(client: SODAClient, since_date: str) -> list[dict]:
    """Fetch permits changed since `since_date` from SODA API."""
    all_records: list[dict] = []
    offset = 0
    while True:
        records = await client.query(
            endpoint_id=BUILDING_PERMITS_ENDPOINT,
            where=f"status_date > '{since_date}T00:00:00.000'",
            order="status_date DESC",
            limit=PAGE_SIZE,
            offset=offset,
        )
        if not records:
            break
        all_records.extend(records)
        if len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_records


def detect_changes(soda_records: list[dict], dry_run: bool = False) -> int:
    """Compare SODA records against DB and insert diffs into permit_changes."""
    if BACKEND == "duckdb":
        init_user_schema()

    ph = "%s" if BACKEND == "postgres" else "?"
    today = date.today()
    inserted = 0

    # For DuckDB manual IDs
    change_id_counter = 0
    if BACKEND == "duckdb":
        id_row = query("SELECT COALESCE(MAX(change_id), 0) FROM permit_changes")
        if id_row:
            change_id_counter = id_row[0][0]

    for record in soda_records:
        permit_number = record.get("permit_number")
        if not permit_number:
            continue

        new_status = record.get("status", "")
        new_status_date = record.get("status_date", "")

        # Lookup current state in our DB
        current = query_one(
            "SELECT status, status_date, permit_type_definition, "
            "street_number, street_name, neighborhood, block, lot "
            f"FROM permits WHERE permit_number = {ph}",
            (permit_number,),
        )

        if current is None:
            # New permit — not in our DB
            change_type = "new_permit"
            old_status = None
            old_status_date = None
            permit_type = record.get("permit_type_definition", "")
            street_number = record.get("street_number", "")
            street_name = record.get("avs_street_name") or record.get("street_name", "")
            neighborhood = record.get("analysis_neighborhood") or record.get("neighborhood", "")
            block_val = record.get("block", "")
            lot_val = record.get("lot", "")
            is_new = True
        else:
            (old_status_db, old_status_date_db, permit_type,
             street_number, street_name, neighborhood, block_val, lot_val) = current

            # Skip if status hasn't actually changed
            if old_status_db == new_status and old_status_date_db == new_status_date:
                continue

            change_type = "status_change"
            old_status = old_status_db
            old_status_date = old_status_date_db
            is_new = False

        if dry_run:
            action = "NEW" if is_new else f"{old_status} -> {new_status}"
            logger.info("  %s: %s (%s)", permit_number, action, new_status_date)
            inserted += 1
            continue

        change_id_counter += 1

        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO permit_changes "
                "(permit_number, change_date, old_status, new_status, "
                "old_status_date, new_status_date, change_type, is_new_permit, "
                "source, permit_type, street_number, street_name, "
                "neighborhood, block, lot) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (permit_number, today, old_status, new_status,
                 old_status_date, new_status_date, change_type, is_new,
                 "nightly", permit_type, street_number, street_name,
                 neighborhood, block_val, lot_val),
            )
        else:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO permit_changes "
                    "(change_id, permit_number, change_date, old_status, new_status, "
                    "old_status_date, new_status_date, change_type, is_new_permit, "
                    "source, permit_type, street_number, street_name, "
                    "neighborhood, block, lot) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (change_id_counter, permit_number, today, old_status, new_status,
                     old_status_date, new_status_date, change_type, is_new,
                     "nightly", permit_type, street_number, street_name,
                     neighborhood, block_val, lot_val),
                )
            finally:
                conn.close()

        # Update permits table with fresh data (upsert)
        if not is_new:
            execute_write(
                f"UPDATE permits SET status = {ph}, status_date = {ph} "
                f"WHERE permit_number = {ph}",
                (new_status, new_status_date, permit_number),
            )

        inserted += 1

    return inserted


async def run_nightly(lookback_days: int = 1, dry_run: bool = False) -> dict:
    """Main entry point for nightly delta fetch."""
    since = date.today() - timedelta(days=lookback_days)
    since_str = since.isoformat()

    logger.info("Fetching permits changed since %s (lookback=%d days)", since_str, lookback_days)

    client = SODAClient()
    try:
        records = await fetch_recent_permits(client, since_str)
    finally:
        await client.close()

    logger.info("SODA returned %d permit records", len(records))

    if dry_run:
        logger.info("DRY RUN — previewing changes:")

    inserted = detect_changes(records, dry_run=dry_run)

    logger.info(
        "%s: %d changes %s from %d SODA records",
        "DRY RUN" if dry_run else "DONE",
        inserted,
        "detected" if dry_run else "inserted",
        len(records),
    )

    return {
        "since": since_str,
        "soda_records": len(records),
        "changes_inserted": inserted,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="Nightly permit change detection")
    parser.add_argument("--lookback", type=int, default=1, help="Days to look back (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()

    result = asyncio.run(run_nightly(lookback_days=args.lookback, dry_run=args.dry_run))
    logger.info("Result: %s", result)


if __name__ == "__main__":
    main()
