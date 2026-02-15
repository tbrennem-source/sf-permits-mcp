"""Property analysis — cross-dataset SODA report for a single property.

Runs concurrent queries across 5 SF open data datasets to build a
comprehensive property profile: permits, complaints, violations,
inspections, and property tax records.

Usage:
    python -m scripts.analyze_property --address "ROBIN HOOD" --block 2920 --lot 020
    python -m scripts.analyze_property --complaint 202429366
    python -m scripts.analyze_property --block 2920 --lot 020 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.soda_client import SODAClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Dataset endpoints
PERMITS_ENDPOINT = "i98e-djp9"
COMPLAINTS_ENDPOINT = "gm2e-bten"
VIOLATIONS_ENDPOINT = "nbtm-fbw5"
INSPECTIONS_ENDPOINT = "vckc-dh2h"
PROPERTY_TAX_ENDPOINT = "wv5m-vpq2"  # Assessor-Recorder Secured Roll
CONTACTS_ENDPOINT = "3pee-9qhc"

# Max records per query
PAGE_SIZE = 50


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")


def _build_where(
    dataset: str,
    address: str | None,
    block: str | None,
    lot: str | None,
    complaint_number: str | None = None,
) -> str | None:
    """Build WHERE clause for a given dataset using the correct field names."""
    conditions = []

    if complaint_number:
        if dataset in ("complaints", "violations"):
            conditions.append(f"complaint_number='{_escape(complaint_number)}'")
        elif dataset == "inspections":
            conditions.append(
                f"reference_number='{_escape(complaint_number)}' "
                f"AND reference_number_type='complaint'"
            )
        # For permits and property_tax, fall through to block/lot if available

    if block:
        conditions.append(f"block='{_escape(block)}'")
    if lot:
        conditions.append(f"lot='{_escape(lot)}'")

    if address and not (block and lot):
        # Field name differs per dataset
        if dataset == "inspections":
            conditions.append(f"upper(avs_street_name) LIKE '%{_escape(address.upper())}%'")
        elif dataset == "property_tax":
            conditions.append(f"upper(property_location) LIKE '%{_escape(address.upper())}%'")
        else:
            conditions.append(f"upper(street_name) LIKE '%{_escape(address.upper())}%'")

    return " AND ".join(conditions) if conditions else None


async def _query_dataset(
    client: SODAClient,
    endpoint: str,
    where: str | None,
    order: str,
    limit: int = PAGE_SIZE,
) -> list[dict]:
    """Query a single dataset, returning empty list on error."""
    if not where:
        return []
    try:
        return await client.query(
            endpoint_id=endpoint,
            where=where,
            order=order,
            limit=limit,
        )
    except Exception as e:
        logger.warning("Query failed for %s: %s", endpoint, e)
        return []


async def _fetch_contacts(
    client: SODAClient,
    permit_numbers: list[str],
    limit: int = 15,
) -> list[dict]:
    """Fetch contacts for a list of permit numbers."""
    if not permit_numbers:
        return []
    # Build OR condition for up to 15 permit numbers
    nums = permit_numbers[:limit]
    or_parts = [f"permit_number='{_escape(n)}'" for n in nums]
    where = " OR ".join(or_parts)
    try:
        return await client.query(
            endpoint_id=CONTACTS_ENDPOINT,
            where=where,
            limit=limit * 5,  # multiple contacts per permit
        )
    except Exception as e:
        logger.warning("Contact query failed: %s", e)
        return []


async def analyze_property(
    address: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    complaint_number: str | None = None,
) -> dict:
    """Run concurrent SODA queries across 5 datasets + contacts.

    Returns a dict with keys: permits, complaints, violations, inspections,
    property_tax, contacts, summary.
    """
    client = SODAClient()
    try:
        # Build WHERE clauses per dataset
        where_permits = _build_where("permits", address, block, lot)
        where_complaints = _build_where("complaints", address, block, lot, complaint_number)
        where_violations = _build_where("violations", address, block, lot, complaint_number)
        where_inspections = _build_where("inspections", address, block, lot, complaint_number)
        where_tax = _build_where("property_tax", address, block, lot)

        # Run all 5 queries concurrently
        permits, complaints, violations, inspections, tax = await asyncio.gather(
            _query_dataset(client, PERMITS_ENDPOINT, where_permits, "filed_date DESC"),
            _query_dataset(client, COMPLAINTS_ENDPOINT, where_complaints, "date_filed DESC"),
            _query_dataset(client, VIOLATIONS_ENDPOINT, where_violations, "date_filed DESC"),
            _query_dataset(client, INSPECTIONS_ENDPOINT, where_inspections, "scheduled_date DESC"),
            _query_dataset(client, PROPERTY_TAX_ENDPOINT, where_tax, "closed_roll_year DESC", limit=5),
        )

        # Fetch contacts for found permits
        permit_numbers = [p.get("permit_number") for p in permits if p.get("permit_number")]
        contacts = await _fetch_contacts(client, permit_numbers)

    finally:
        await client.close()

    # Build summary
    summary = {
        "permits_found": len(permits),
        "complaints_found": len(complaints),
        "violations_found": len(violations),
        "inspections_found": len(inspections),
        "property_records": len(tax),
        "contacts_found": len(contacts),
        "open_complaints": sum(
            1 for c in complaints
            if c.get("status", "").lower() in ("open", "active")
        ),
        "open_violations": sum(
            1 for v in violations
            if v.get("status", "").lower() in ("open", "active")
        ),
    }

    return {
        "permits": permits,
        "complaints": complaints,
        "violations": violations,
        "inspections": inspections,
        "property_tax": tax,
        "contacts": contacts,
        "summary": summary,
    }


def format_report(data: dict) -> str:
    """Format the property analysis as a human-readable report."""
    s = data["summary"]
    lines = [
        "=" * 60,
        "PROPERTY ANALYSIS REPORT",
        "=" * 60,
        "",
        f"Permits:      {s['permits_found']}",
        f"Complaints:   {s['complaints_found']} ({s['open_complaints']} open)",
        f"Violations:   {s['violations_found']} ({s['open_violations']} open)",
        f"Inspections:  {s['inspections_found']}",
        f"Tax Records:  {s['property_records']}",
        f"Contacts:     {s['contacts_found']}",
        "",
    ]

    # Property tax section
    if data["property_tax"]:
        lines.append("-" * 40)
        lines.append("PROPERTY INFO (Tax Roll)")
        lines.append("-" * 40)
        for t in data["property_tax"][:2]:
            lines.append(f"  Location: {t.get('property_location', 'N/A')}")
            lines.append(f"  Use: {t.get('use_definition', 'N/A')}")
            lines.append(f"  Year Built: {t.get('year_property_built', 'N/A')}")
            lines.append(f"  Lot Area: {t.get('lot_area', 'N/A')} sq ft")
            land = t.get("assessed_land_value", "")
            if land:
                try:
                    lines.append(f"  Assessed Land: ${float(land):,.0f}")
                except (ValueError, TypeError):
                    pass
            lines.append("")

    # Recent permits
    if data["permits"]:
        lines.append("-" * 40)
        lines.append(f"PERMITS (showing {min(len(data['permits']), 10)} of {s['permits_found']})")
        lines.append("-" * 40)
        for p in data["permits"][:10]:
            filed = (p.get("filed_date") or "")[:10]
            desc = (p.get("description") or "")[:80]
            lines.append(
                f"  {p.get('permit_number', '?')} | {p.get('status', '?')} | "
                f"Filed: {filed} | {desc}"
            )
        lines.append("")

    # Complaints
    if data["complaints"]:
        lines.append("-" * 40)
        lines.append(f"COMPLAINTS ({s['complaints_found']} total, {s['open_complaints']} open)")
        lines.append("-" * 40)
        for c in data["complaints"][:10]:
            date_filed = (c.get("date_filed") or "")[:10]
            desc = (c.get("complaint_description") or "")[:80]
            lines.append(
                f"  {c.get('complaint_number', '?')} | {c.get('status', '?')} | "
                f"Filed: {date_filed} | {desc}"
            )
        lines.append("")

    # Violations
    if data["violations"]:
        lines.append("-" * 40)
        lines.append(f"VIOLATIONS ({s['violations_found']} total, {s['open_violations']} open)")
        lines.append("-" * 40)
        for v in data["violations"][:10]:
            date_filed = (v.get("date_filed") or "")[:10]
            desc = (v.get("nov_item_description") or "")[:80]
            lines.append(
                f"  {v.get('complaint_number', '?')}-{v.get('item_sequence_number', '?')} | "
                f"{v.get('status', '?')} | Filed: {date_filed} | {desc}"
            )
        lines.append("")

    # Inspections
    if data["inspections"]:
        lines.append("-" * 40)
        lines.append(f"INSPECTIONS (showing {min(len(data['inspections']), 10)} of {s['inspections_found']})")
        lines.append("-" * 40)
        for i in data["inspections"][:10]:
            sched = (i.get("scheduled_date") or "")[:10]
            desc = (i.get("inspection_type_description") or "")[:60]
            lines.append(
                f"  {i.get('reference_number', '?')} | {i.get('status', '?')} | "
                f"{sched} | {i.get('inspector', '?')} | {desc}"
            )
        lines.append("")

    # Contacts
    if data["contacts"]:
        lines.append("-" * 40)
        lines.append(f"PROJECT CONTACTS ({s['contacts_found']})")
        lines.append("-" * 40)
        seen = set()
        for ct in data["contacts"][:15]:
            name = ct.get("applicant_name") or ct.get("name", "Unknown")
            role = ct.get("applicant_type") or ct.get("role", "")
            key = f"{name}|{role}"
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {name} ({role}) — Permit {ct.get('permit_number', '?')}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Cross-dataset property analysis")
    parser.add_argument("--address", type=str, help="Street name (e.g., 'ROBIN HOOD')")
    parser.add_argument("--block", type=str, help="Assessor block number")
    parser.add_argument("--lot", type=str, help="Assessor lot number")
    parser.add_argument("--complaint", type=str, help="Complaint number")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not any([args.address, args.block, args.complaint]):
        parser.error("At least one of --address, --block, or --complaint is required")

    data = asyncio.run(analyze_property(
        address=args.address,
        block=args.block,
        lot=args.lot,
        complaint_number=args.complaint,
    ))

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(format_report(data))


if __name__ == "__main__":
    main()
