"""Tool: search_complaints — Search DBI complaints via SODA API."""

from src.soda_client import SODAClient
from src.formatters import format_complaint_list

ENDPOINT_ID = "gm2e-bten"  # DBI Complaints (326K records)


async def search_complaints(
    complaint_number: str | None = None,
    address: str | None = None,
    street_number: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    description_search: str | None = None,
    limit: int = 20,
) -> str:
    """Search DBI building complaints filed against properties.

    Args:
        complaint_number: Specific complaint number (e.g., '202429366')
        address: Search by street name (e.g., 'ROBIN HOOD', 'MARKET')
        street_number: Street number to narrow address search (e.g., '125')
        block: Assessor block number (e.g., '2920')
        lot: Assessor lot number (e.g., '020')
        status: Complaint status (e.g., 'open', 'abated', 'closed')
        date_from: Filed after this date (YYYY-MM-DD)
        date_to: Filed before this date (YYYY-MM-DD)
        description_search: Full-text search in complaint description
        limit: Max results (default 20, max 200)

    Returns:
        Formatted list of matching complaints with key fields.
    """
    conditions = []
    if complaint_number:
        conditions.append(f"complaint_number='{_escape(complaint_number)}'")
    if address:
        conditions.append(f"upper(street_name) LIKE '%{_escape(address.upper())}%'")
    if street_number:
        conditions.append(f"street_number='{_escape(street_number)}'")
    if block:
        conditions.append(f"block='{_escape(block)}'")
    if lot:
        conditions.append(f"lot='{_escape(lot)}'")
    if status:
        conditions.append(f"upper(status) LIKE '%{_escape(status.upper())}%'")
    if date_from:
        conditions.append(f"date_filed >= '{_escape(date_from)}'")
    if date_to:
        conditions.append(f"date_filed <= '{_escape(date_to)}'")

    where = " AND ".join(conditions) if conditions else None
    q = description_search

    fetch_limit = min(limit, 200)

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            q=q,
            order="date_filed DESC",
            limit=fetch_limit,
        )
        return format_complaint_list(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping to prevent injection."""
    return value.replace("'", "''").replace("\\", "\\\\")
