"""Tool: search_violations — Search Notices of Violation via SODA API."""

from src.soda_client import SODAClient
from src.formatters import format_violation_list

ENDPOINT_ID = "nbtm-fbw5"  # Notices of Violation (509K records)


async def search_violations(
    complaint_number: str | None = None,
    address: str | None = None,
    street_number: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    status: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    description_search: str | None = None,
    limit: int = 20,
) -> str:
    """Search DBI Notices of Violation (NOVs) issued against properties.

    Args:
        complaint_number: Complaint number that generated the NOV (e.g., '202429366')
        address: Search by street name (e.g., 'ROBIN HOOD', 'MARKET')
        street_number: Street number to narrow address search (e.g., '125')
        block: Assessor block number (e.g., '2920')
        lot: Assessor lot number (e.g., '040')
        status: NOV status (e.g., 'open', 'closed', 'complied')
        category: NOV category (e.g., 'building', 'electrical', 'plumbing')
        date_from: Filed after this date (YYYY-MM-DD)
        date_to: Filed before this date (YYYY-MM-DD)
        description_search: Full-text search in violation description
        limit: Max results (default 20, max 200)

    Returns:
        Formatted list of matching violations with key fields.
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
    if category:
        conditions.append(
            f"upper(nov_category_description) LIKE '%{_escape(category.upper())}%'"
        )
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
        return format_violation_list(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping to prevent injection."""
    return value.replace("'", "''").replace("\\", "\\\\")
