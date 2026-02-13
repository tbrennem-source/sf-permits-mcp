"""Tool: permit_stats — Get aggregate statistics on SF building permits."""

from src.soda_client import SODAClient
from src.formatters import format_stats

ENDPOINT_ID = "i98e-djp9"  # Building Permits

# Map human-friendly group names to SoQL fields
GROUP_MAP = {
    "neighborhood": "neighborhoods_analysis_boundaries",
    "type": "permit_type_definition",
    "status": "status",
    "month": "date_trunc_ym(filed_date)",
    "year": "date_trunc_y(filed_date)",
}


async def permit_stats(
    group_by: str = "neighborhood",
    date_from: str | None = None,
    date_to: str | None = None,
    neighborhood: str | None = None,
    permit_type: str | None = None,
) -> str:
    """Get aggregate statistics on SF building permits.

    Args:
        group_by: How to aggregate — 'neighborhood', 'type', 'status', 'month', 'year'
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        neighborhood: Filter to specific neighborhood
        permit_type: Filter to specific permit type

    Returns:
        Aggregated counts, average costs, and total costs.
    """
    group_field = GROUP_MAP.get(group_by)
    if not group_field:
        valid = ", ".join(f"'{k}'" for k in GROUP_MAP)
        return f"Invalid group_by value '{group_by}'. Valid options: {valid}"

    select = (
        f"{group_field} as category, "
        f"count(*) as total, "
        f"avg(cast(estimated_cost as number)) as avg_cost, "
        f"sum(cast(estimated_cost as number)) as total_cost"
    )

    conditions = []
    if date_from:
        conditions.append(f"filed_date >= '{_escape(date_from)}'")
    if date_to:
        conditions.append(f"filed_date <= '{_escape(date_to)}'")
    if neighborhood:
        conditions.append(
            f"neighborhoods_analysis_boundaries='{_escape(neighborhood)}'"
        )
    if permit_type:
        conditions.append(f"permit_type_definition='{_escape(permit_type)}'")

    where = " AND ".join(conditions) if conditions else None

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            select=select,
            where=where,
            group=group_field,
            order="total DESC",
            limit=50,
        )
        return format_stats(results, group_by)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
