"""Ingestion pipeline: fetch SF permit data from SODA API into local DuckDB.

Usage:
    python -m src.ingest              # Full ingestion (all datasets)
    python -m src.ingest --contacts   # Only contact datasets
    python -m src.ingest --permits    # Only building permits
    python -m src.ingest --inspections # Only building inspections
"""

import asyncio
import time
import sys
import os
from datetime import datetime, timezone

from src.soda_client import SODAClient
from src.db import get_connection, init_schema

# Dataset configs
DATASETS = {
    "building_contacts": {
        "endpoint_id": "3pee-9qhc",
        "name": "Building Permits Contacts",
        "source": "building",
    },
    "electrical_contacts": {
        "endpoint_id": "fdm7-jqqf",
        "name": "Electrical Permits Contacts",
        "source": "electrical",
    },
    "plumbing_contacts": {
        "endpoint_id": "k6kv-9kix",
        "name": "Plumbing Permits Contacts",
        "source": "plumbing",
    },
    "building_permits": {
        "endpoint_id": "i98e-djp9",
        "name": "Building Permits",
    },
    "building_inspections": {
        "endpoint_id": "vckc-dh2h",
        "name": "Building Inspections",
    },
}

PAGE_SIZE = 10_000

# Role normalization map for building contacts
ROLE_MAP = {
    "contractor": "contractor",
    "authorized agent-others": "agent",
    "architect": "architect",
    "engineer": "engineer",
    "lessee": "owner",
    "payor": "other",
    "pmt consultant/expediter": "consultant",
    "designer": "designer",
    "project contact": "other",
    "attorney": "other",
    "subcontractor": "contractor",
}

# Contact type normalization for electrical contacts
ELECTRICAL_ROLE_MAP = {
    "Contractor": "contractor",
    "contractor": "contractor",
    "Owner": "owner",
    "owner": "owner",
    "Others": "other",
    "others": "other",
}


def _normalize_role(role: str | None, source: str) -> str:
    """Normalize role/contact_type to canonical type."""
    if not role:
        if source == "plumbing":
            return "contractor"  # All plumbing contacts are implicitly contractors
        return "other"
    role_lower = role.lower().strip()
    if source == "building":
        return ROLE_MAP.get(role_lower, "other")
    elif source == "electrical":
        return ELECTRICAL_ROLE_MAP.get(role, ELECTRICAL_ROLE_MAP.get(role_lower, "other"))
    elif source == "plumbing":
        return "contractor"
    return "other"


def _normalize_building_contact(record: dict, row_id: int) -> tuple:
    """Normalize a building contacts record to unified schema."""
    first_name = (record.get("first_name") or "").strip()
    last_name = (record.get("last_name") or "").strip()
    name_parts = [first_name, last_name]
    name = " ".join(p for p in name_parts if p).strip() or None

    return (
        row_id,
        "building",
        record.get("permit_number", ""),
        _normalize_role(record.get("role"), "building"),
        name,
        first_name or None,
        last_name or None,
        (record.get("firm_name") or "").strip() or None,
        (record.get("pts_agent_id") or "").strip() or None,
        (record.get("license1") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        None,  # phone not in building contacts
        (record.get("agent_address") or "").strip() or None,
        (record.get("city") or "").strip() or None,
        (record.get("state") or "").strip() or None,
        (record.get("agent_zipcode") or "").strip() or None,
        record.get("is_applicant"),
        record.get("from_date"),
        None,  # entity_id (populated later)
        record.get("data_as_of"),
    )


def _normalize_electrical_contact(record: dict, row_id: int) -> tuple:
    """Normalize an electrical contacts record to unified schema."""
    company = (record.get("company_name") or "").strip() or None
    address_parts = [
        record.get("street_number", ""),
        record.get("street", ""),
        record.get("street_suffix", ""),
    ]
    address = " ".join(p for p in address_parts if (p or "").strip()).strip() or None

    return (
        row_id,
        "electrical",
        record.get("permit_number", ""),
        _normalize_role(record.get("contact_type"), "electrical"),
        company,  # company_name used as name
        None,  # no first_name
        None,  # no last_name
        company,  # company_name serves as firm_name too
        None,  # no pts_agent_id
        (record.get("license_number") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        (record.get("phone") or "").strip() or None,
        address,
        None,  # no city field
        (record.get("state") or "").strip() or None,
        (record.get("zipcode") or "").strip() or None,
        record.get("is_applicant"),
        None,  # no from_date
        None,  # entity_id
        record.get("data_as_of"),
    )


def _normalize_plumbing_contact(record: dict, row_id: int) -> tuple:
    """Normalize a plumbing contacts record to unified schema."""
    firm = (record.get("firm_name") or "").strip() or None

    return (
        row_id,
        "plumbing",
        record.get("permit_number", ""),
        "contractor",  # all plumbing contacts are contractors
        firm,  # firm_name used as name
        None,  # no first_name
        None,  # no last_name
        firm,
        None,  # no pts_agent_id
        (record.get("license_number") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        (record.get("phone") or "").strip() or None,
        (record.get("address") or "").strip() or None,
        (record.get("city") or "").strip() or None,
        (record.get("state") or "").strip() or None,
        (record.get("zipcode") or "").strip() or None,
        record.get("is_applicant"),
        None,  # no from_date
        None,  # entity_id
        record.get("data_as_of"),
    )


def _normalize_permit(record: dict) -> tuple:
    """Normalize a building permit record."""
    cost = None
    raw_cost = record.get("estimated_cost")
    if raw_cost:
        try:
            cost = float(raw_cost)
        except (ValueError, TypeError):
            pass

    revised_cost = None
    raw_revised = record.get("revised_cost")
    if raw_revised:
        try:
            revised_cost = float(raw_revised)
        except (ValueError, TypeError):
            pass

    existing_units = None
    raw_eu = record.get("existing_units")
    if raw_eu:
        try:
            existing_units = int(float(raw_eu))
        except (ValueError, TypeError):
            pass

    proposed_units = None
    raw_pu = record.get("proposed_units")
    if raw_pu:
        try:
            proposed_units = int(float(raw_pu))
        except (ValueError, TypeError):
            pass

    return (
        record.get("permit_number", ""),
        record.get("permit_type"),
        record.get("permit_type_definition"),
        record.get("status"),
        record.get("status_date"),
        record.get("description"),
        record.get("filed_date"),
        record.get("issued_date"),
        record.get("approved_date"),
        record.get("completed_date"),
        cost,
        revised_cost,
        record.get("existing_use"),
        record.get("proposed_use"),
        existing_units,
        proposed_units,
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zipcode"),
        record.get("neighborhoods_analysis_boundaries"),
        record.get("supervisor_district"),
        record.get("block"),
        record.get("lot"),
        record.get("adu"),
        record.get("data_as_of"),
    )


def _normalize_addenda(record: dict, row_id: int) -> tuple:
    """Normalize a building permit addenda routing record."""
    addenda_number = None
    raw_an = record.get("addenda_number")
    if raw_an:
        try:
            addenda_number = int(float(raw_an))
        except (ValueError, TypeError):
            pass

    step = None
    raw_step = record.get("step")
    if raw_step:
        try:
            step = int(float(raw_step))
        except (ValueError, TypeError):
            pass

    return (
        row_id,
        record.get("primary_key"),
        record.get("application_number", ""),
        addenda_number,
        step,
        (record.get("station") or "").strip() or None,
        record.get("arrive"),
        record.get("assign_date"),
        record.get("start_date"),
        record.get("finish_date"),
        record.get("approved_date"),
        (record.get("plan_checked_by") or "").strip() or None,
        (record.get("review_results") or "").strip() or None,
        (record.get("hold_description") or "").strip() or None,
        (record.get("addenda_status") or "").strip() or None,
        (record.get("department") or "").strip() or None,
        (record.get("title") or "").strip() or None,
        record.get("data_as_of"),
    )


def _normalize_inspection(record: dict, row_id: int) -> tuple:
    """Normalize a building inspection record."""
    return (
        row_id,
        record.get("reference_number"),
        record.get("reference_number_type"),
        (record.get("inspector") or "").strip() or None,
        record.get("scheduled_date"),
        record.get("result"),
        record.get("inspection_description"),
        record.get("block"),
        record.get("lot"),
        record.get("street_number"),
        record.get("avs_street_name"),
        record.get("avs_street_sfx"),
        record.get("analysis_neighborhood"),
        record.get("supervisor_district"),
        record.get("zip_code"),
        record.get("data_as_of"),
    )


async def _fetch_all_pages(
    client: SODAClient,
    endpoint_id: str,
    dataset_name: str,
    order: str = ":id",
) -> list[dict]:
    """Fetch all records from a SODA endpoint with pagination."""
    all_records = []
    offset = 0
    start = time.time()

    # Get total count first
    total = await client.count(endpoint_id)
    print(f"  {dataset_name}: {total:,} total records to fetch")

    max_retries = 3
    while True:
        page = None
        for attempt in range(max_retries):
            try:
                page = await client.query(
                    endpoint_id=endpoint_id,
                    limit=PAGE_SIZE,
                    offset=offset,
                    order=order,
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retry {attempt + 1}/{max_retries} after error: {e}. Waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    raise
        if not page:
            break

        all_records.extend(page)
        offset += len(page)
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        print(
            f"  Fetched {offset:,}/{total:,} records "
            f"({offset * 100 // total}%) — "
            f"{rate:,.0f} records/sec — "
            f"{elapsed:.1f}s elapsed",
            flush=True,
        )

        if len(page) < PAGE_SIZE:
            break

    elapsed = time.time() - start
    print(f"  Done: {len(all_records):,} records in {elapsed:.1f}s")
    return all_records


async def ingest_contacts(conn, client: SODAClient) -> int:
    """Ingest all three contact datasets into unified contacts table."""
    print("\n=== Ingesting Contact Datasets ===")

    # Clear existing contacts
    conn.execute("DELETE FROM contacts")

    row_id = 0
    total = 0

    # Building contacts
    print("\n[1/3] Building Permits Contacts (3pee-9qhc)")
    records = await _fetch_all_pages(
        client, "3pee-9qhc", "Building Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_building_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} building contact records")

    # Update ingest log
    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "3pee-9qhc",
            "Building Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    # Electrical contacts
    print("\n[2/3] Electrical Permits Contacts (fdm7-jqqf)")
    records = await _fetch_all_pages(
        client, "fdm7-jqqf", "Electrical Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_electrical_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} electrical contact records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "fdm7-jqqf",
            "Electrical Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    # Plumbing contacts
    print("\n[3/3] Plumbing Permits Contacts (k6kv-9kix)")
    records = await _fetch_all_pages(
        client, "k6kv-9kix", "Plumbing Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_plumbing_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} plumbing contact records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "k6kv-9kix",
            "Plumbing Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    print(f"\n  Total contacts loaded: {total:,}")
    return total


async def ingest_permits(conn, client: SODAClient) -> int:
    """Ingest building permits into permits table."""
    print("\n=== Ingesting Building Permits ===")

    conn.execute("DELETE FROM permits")

    records = await _fetch_all_pages(
        client, "i98e-djp9", "Building Permits"
    )

    batch = [_normalize_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "i98e-djp9",
            "Building Permits",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_inspections(conn, client: SODAClient) -> int:
    """Ingest building inspections into inspections table."""
    print("\n=== Ingesting Building Inspections ===")

    conn.execute("DELETE FROM inspections")

    records = await _fetch_all_pages(
        client, "vckc-dh2h", "Building Inspections"
    )

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_inspection(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} inspection records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "vckc-dh2h",
            "Building Inspections",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_addenda(conn, client: SODAClient) -> int:
    """Ingest building permit addenda + routing into addenda table."""
    print("\n=== Ingesting Building Permit Addenda + Routing ===")

    conn.execute("DELETE FROM addenda")

    records = await _fetch_all_pages(
        client, "87xy-gk8d", "Building Permit Addenda + Routing"
    )

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_addenda(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO addenda VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} addenda routing records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "87xy-gk8d",
            "Building Permit Addenda + Routing",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def run_ingestion(
    contacts: bool = True,
    permits: bool = True,
    inspections: bool = True,
    addenda: bool = True,
    db_path: str | None = None,
) -> dict:
    """Run the full ingestion pipeline.

    Returns dict with counts of records ingested per dataset.
    """
    start = time.time()
    conn = get_connection(db_path)
    init_schema(conn)

    client = SODAClient()
    results = {}

    try:
        if contacts:
            results["contacts"] = await ingest_contacts(conn, client)
        if permits:
            results["permits"] = await ingest_permits(conn, client)
        if inspections:
            results["inspections"] = await ingest_inspections(conn, client)
        if addenda:
            results["addenda"] = await ingest_addenda(conn, client)
    finally:
        await client.close()

    elapsed = time.time() - start
    total = sum(results.values())
    print(f"\n{'=' * 60}")
    print(f"Ingestion complete: {total:,} total records in {elapsed:.1f}s")
    for k, v in results.items():
        print(f"  {k}: {v:,}")
    print(f"{'=' * 60}")

    conn.close()
    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest SF permit data into DuckDB")
    parser.add_argument("--contacts", action="store_true", help="Only ingest contacts")
    parser.add_argument("--permits", action="store_true", help="Only ingest permits")
    parser.add_argument("--inspections", action="store_true", help="Only ingest inspections")
    parser.add_argument("--addenda", action="store_true", help="Only ingest addenda routing")
    parser.add_argument("--db", type=str, help="Custom database path")
    args = parser.parse_args()

    # If no specific flag, ingest everything
    do_all = not (args.contacts or args.permits or args.inspections or args.addenda)

    asyncio.run(
        run_ingestion(
            contacts=do_all or args.contacts,
            permits=do_all or args.permits,
            inspections=do_all or args.inspections,
            addenda=do_all or args.addenda,
            db_path=args.db,
        )
    )


if __name__ == "__main__":
    main()
