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

    # estimated_cost is text in SODA — can't use avg()/sum() server-side.
    # Get counts from SODA, then compute cost stats client-side.
    select = f"{group_field} as category, count(*) as total"

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
        # Get counts grouped by category
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            select=select,
            where=where,
            group=group_field,
            order="total DESC",
            limit=50,
        )

        # For cost stats, fetch raw records with cost data for top categories
        # (limited to avoid excessive API calls)
        if results:
            cost_conditions = list(conditions) if conditions else []
            cost_conditions.append("estimated_cost IS NOT NULL")
            cost_where = " AND ".join(cost_conditions)

            cost_records = await client.query(
                endpoint_id=ENDPOINT_ID,
                select=f"{group_field} as category, estimated_cost",
                where=cost_where,
                limit=5000,
            )

            # Compute avg and total cost per category client-side
            cost_by_category: dict[str, list[float]] = {}
            for r in cost_records:
                cat = r.get("category", "")
                try:
                    cost = float(r.get("estimated_cost", 0) or 0)
                    if cost > 0:
                        cost_by_category.setdefault(cat, []).append(cost)
                except (ValueError, TypeError):
                    continue

            for row in results:
                cat = row.get("category", "")
                costs = cost_by_category.get(cat, [])
                if costs:
                    row["avg_cost"] = str(sum(costs) / len(costs))
                    row["total_cost"] = str(sum(costs))

        return format_stats(results, group_by)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
