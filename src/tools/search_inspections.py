"""Tool: search_inspections — Search building inspections via SODA API."""

from src.soda_client import SODAClient
from src.formatters import format_inspection_list

ENDPOINT_ID = "vckc-dh2h"  # Building Inspections (671K records)


async def search_inspections(
    permit_number: str | None = None,
    complaint_number: str | None = None,
    address: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    inspector: str | None = None,
    result: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    description_search: str | None = None,
    limit: int = 50,
) -> str:
    """Search DBI building inspection records.

    Args:
        permit_number: Filter by permit number
        complaint_number: Filter by complaint number
        address: Search by street name (uses avs_street_name field; e.g., 'ROBIN HOOD')
        block: Assessor block number (e.g., '2920')
        lot: Assessor lot number (e.g., '020')
        inspector: Inspector name (partial match)
        result: Inspection result (e.g., 'approved', 'disapproved', 'not applicable')
        date_from: Scheduled after this date (YYYY-MM-DD)
        date_to: Scheduled before this date (YYYY-MM-DD)
        description_search: Full-text search in inspection description
        limit: Max results (default 50, max 200)

    Returns:
        Formatted list of matching inspections with key fields.
    """
    conditions = []
    if permit_number:
        conditions.append(
            f"reference_number='{_escape(permit_number)}' "
            f"AND reference_number_type='permit'"
        )
    if complaint_number:
        conditions.append(
            f"reference_number='{_escape(complaint_number)}' "
            f"AND reference_number_type='complaint'"
        )
    if address:
        # NOTE: inspections dataset uses avs_street_name, NOT street_name
        conditions.append(
            f"upper(avs_street_name)='{_escape(address.upper())}'"
        )
    if block:
        conditions.append(f"block='{_escape(block)}'")
    if lot:
        conditions.append(f"lot='{_escape(lot)}'")
    if inspector:
        conditions.append(
            f"upper(inspector) LIKE '%{_escape(inspector.upper())}%'"
        )
    if result:
        conditions.append(
            f"upper(inspection_type_description) LIKE '%{_escape(result.upper())}%' "
            f"OR upper(status) LIKE '%{_escape(result.upper())}%'"
        )
    if date_from:
        conditions.append(f"scheduled_date >= '{_escape(date_from)}'")
    if date_to:
        conditions.append(f"scheduled_date <= '{_escape(date_to)}'")

    where = " AND ".join(conditions) if conditions else None
    q = description_search

    fetch_limit = min(limit, 200)

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            q=q,
            order="scheduled_date DESC",
            limit=fetch_limit,
        )
        return format_inspection_list(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping to prevent injection."""
    return value.replace("'", "''").replace("\\", "\\\\")
