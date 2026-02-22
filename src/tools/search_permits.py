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
        # estimated_cost is text in SODA — use estimated_cost IS NOT NULL
        # to pre-filter, then apply numeric filtering client-side
        conditions.append("estimated_cost IS NOT NULL")
    if max_cost is not None and min_cost is None:
        conditions.append("estimated_cost IS NOT NULL")
    if date_from:
        conditions.append(f"filed_date >= '{_escape(date_from)}'")
    if date_to:
        conditions.append(f"filed_date <= '{_escape(date_to)}'")
    if address:
        conditions.append(f"upper(street_name)='{_escape(address.upper())}'")

    where = " AND ".join(conditions) if conditions else None
    q = description_search  # $q for full-text search

    # If cost filtering, fetch more results to filter client-side
    fetch_limit = min(limit, 200)
    if min_cost is not None or max_cost is not None:
        fetch_limit = min(limit * 5, 1000)  # Over-fetch for client-side filtering

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            q=q,
            order="filed_date DESC",
            limit=fetch_limit,
        )

        # Client-side cost filtering (estimated_cost is text in SODA)
        if min_cost is not None or max_cost is not None:
            results = _filter_by_cost(results, min_cost, max_cost)
            results = results[: min(limit, 200)]

        return format_permit_list(results)
    finally:
        await client.close()


def _filter_by_cost(
    results: list[dict],
    min_cost: float | None,
    max_cost: float | None,
) -> list[dict]:
    """Filter permits by cost client-side (estimated_cost is text in SODA)."""
    filtered = []
    for r in results:
        try:
            cost = float(r.get("estimated_cost", 0) or 0)
        except (ValueError, TypeError):
            continue
        if min_cost is not None and cost < min_cost:
            continue
        if max_cost is not None and cost > max_cost:
            continue
        filtered.append(r)
    return filtered


def _escape(value: str) -> str:
    """Basic SoQL string escaping to prevent injection."""
    return value.replace("'", "''").replace("\\", "\\\\")
