"""Tool: property_lookup — Look up SF property information by address or block/lot."""

from src.soda_client import SODAClient
from src.formatters import format_property

# Property Tax Rolls — historical assessed values, property characteristics, zoning
# NOTE: i8ew-h6z7 (Property Information Map) is NOT a data API — it's an interactive map.
# Using wv5m-vpq2 (Assessor Historical Secured Property Tax Rolls) instead.
ENDPOINT_ID = "wv5m-vpq2"


async def property_lookup(
    address: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    tax_year: str | None = None,
) -> str:
    """Look up property information for a San Francisco parcel.

    Args:
        address: Street address to search (e.g., '123 MAIN ST')
        block: Assessor block number (e.g., '3512')
        lot: Assessor lot number (e.g., '001')
        tax_year: Tax roll year (e.g., '2024'). Defaults to most recent.

    Returns:
        Property details including assessed value, zoning, characteristics,
        and neighborhood information.
    """
    conditions = []

    if block and lot:
        conditions.append(f"block='{_escape(block)}' AND lot='{_escape(lot)}'")
    elif address:
        conditions.append(
            f"upper(property_location) LIKE '%{_escape(address.upper())}%'"
        )
    else:
        return "Please provide either an address or block/lot numbers."

    if tax_year:
        conditions.append(f"closed_roll_year='{_escape(tax_year)}'")
    else:
        # Get the most recent year by ordering
        pass

    where = " AND ".join(conditions) if conditions else None

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            order="closed_roll_year DESC",
            limit=5,
        )
        if not results:
            search_desc = (
                f"block {block}, lot {lot}" if block and lot else f"address '{address}'"
            )
            return f"No property found matching {search_desc}."
        return format_property(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
