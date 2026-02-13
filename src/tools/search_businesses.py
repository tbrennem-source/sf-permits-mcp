"""Tool: search_businesses — Search registered business locations in SF."""

from src.soda_client import SODAClient
from src.formatters import format_business_list

ENDPOINT_ID = "g8m3-pdis"  # Registered Business Locations


async def search_businesses(
    business_name: str | None = None,
    address: str | None = None,
    zip_code: str | None = None,
    active_only: bool = True,
    limit: int = 20,
) -> str:
    """Search registered business locations in San Francisco.

    Args:
        business_name: Search by business name (DBA or ownership name)
        address: Search by street address
        zip_code: Filter by zip code
        active_only: Only show active businesses (default True)
        limit: Max results (default 20, max 100)

    Returns:
        List of matching businesses with location and registration details.
    """
    conditions = []
    q = None

    if business_name:
        # Use full-text search for name matching
        q = business_name

    if address:
        conditions.append(
            f"upper(full_business_address) LIKE '%{_escape(address.upper())}%'"
        )

    if zip_code:
        conditions.append(f"business_zip='{_escape(zip_code)}'")

    if active_only:
        # Active businesses have no location_end_date
        conditions.append("location_end_date IS NULL")

    where = " AND ".join(conditions) if conditions else None

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            q=q,
            order="dba_start_date DESC",
            limit=min(limit, 100),
        )
        return format_business_list(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
