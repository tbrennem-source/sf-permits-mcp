"""Tool: search_permits — Search SF building permits with filters."""

from src.soda_client import SODAClient
from src.formatters import format_permit_list

ENDPOINT_ID = "i98e-djp9"  # Building Permits


async def search_permits(
    neighborhood: str | None = None,
    permit_type: str | None = None,
    status: str | None = None,
    min_cost: float | None = None,
    max_cost: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    address: str | None = None,
    description_search: str | None = None,
    limit: int = 20,
) -> str:
    """Search SF building permits with filters.

    Args:
        neighborhood: Filter by neighborhood (e.g., 'Mission', 'SoMa', 'Castro/Upper Market')
        permit_type: Filter by type (e.g., 'additions alterations or repairs',
                     'new construction', 'demolitions', 'otc alterations')
        status: Filter by status (e.g., 'issued', 'complete', 'filed', 'approved', 'expired')
        min_cost: Minimum estimated cost
        max_cost: Maximum estimated cost
        date_from: Filed after this date (YYYY-MM-DD)
        date_to: Filed before this date (YYYY-MM-DD)
        address: Search by street name (e.g., 'MARKET', 'VALENCIA')
        description_search: Full-text search in permit description (e.g., 'solar', 'kitchen remodel')
        limit: Max results (default 20, max 200)

    Returns:
        Formatted list of matching permits with key fields.
    """
    conditions = []
    if neighborhood:
        conditions.append(
            f"neighborhoods_analysis_boundaries='{_escape(neighborhood)}'"
        )
    if permit_type:
        conditions.append(f"permit_type_definition='{_escape(permit_type)}'")
    if status:
        conditions.append(f"status='{_escape(status)}'")
    if min_cost is not None:
        # estimated_cost is stored as text in SODA — cast to number for comparison
        conditions.append(f"cast(estimated_cost as number) >= {float(min_cost)}")
    if max_cost is not None:
        conditions.append(f"cast(estimated_cost as number) <= {float(max_cost)}")
    if date_from:
        conditions.append(f"filed_date >= '{_escape(date_from)}'")
    if date_to:
        conditions.append(f"filed_date <= '{_escape(date_to)}'")
    if address:
        conditions.append(f"upper(street_name) LIKE '%{_escape(address.upper())}%'")

    where = " AND ".join(conditions) if conditions else None
    q = description_search  # $q for full-text search

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            q=q,
            order="filed_date DESC",
            limit=min(limit, 200),
        )
        return format_permit_list(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping to prevent injection."""
    return value.replace("'", "''").replace("\\", "\\\\")
