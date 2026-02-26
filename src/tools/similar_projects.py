"""Tool: similar_projects — Find completed permits similar to user's project.

Progressive widening strategy:
1. Exact: same permit_type_definition + neighborhood + cost within 50%
2. Widen cost to 100%
3. Widen to same supervisor_district
"""
import logging
from datetime import date as _date

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)


def _build_where(
    permit_type: str,
    neighborhood: str | None,
    estimated_cost: float | None,
    cost_pct: float,
    supervisor_district: str | None,
    use_district: bool,
) -> tuple[str, list]:
    """Build WHERE clause with given filter level.

    Args:
        permit_type: Permit type keyword (ILIKE match)
        neighborhood: Neighborhood name (exact match) — ignored when use_district=True
        estimated_cost: User's estimated cost
        cost_pct: Cost bracket tolerance (e.g., 0.5 = 50%, 1.0 = 100%)
        supervisor_district: Supervisor district number (fallback geo filter)
        use_district: If True, replace neighborhood with supervisor_district filter
    """
    ph = "%s" if BACKEND == "postgres" else "?"
    conditions = [
        "completed_date IS NOT NULL",
        "issued_date IS NOT NULL",
        "filed_date IS NOT NULL",
        "estimated_cost > 0",
        f"permit_type_definition ILIKE {ph}",
    ]
    params: list = [f"%{permit_type}%"]

    if use_district and supervisor_district:
        conditions.append(f"supervisor_district = {ph}")
        params.append(supervisor_district)
    elif not use_district and neighborhood:
        conditions.append(f"neighborhood = {ph}")
        params.append(neighborhood)

    if estimated_cost and estimated_cost > 0:
        lower = estimated_cost * (1 - cost_pct)
        upper = estimated_cost * (1 + cost_pct)
        conditions.append(f"estimated_cost BETWEEN {ph} AND {ph}")
        params.extend([lower, upper])

    where = " AND ".join(conditions)
    return where, params


def _query_permits(conn, where: str, params: list, limit: int) -> list[tuple]:
    """Execute the permit query and return rows."""
    sql = f"""
        SELECT
            permit_number,
            permit_type_definition,
            neighborhood,
            supervisor_district,
            estimated_cost,
            revised_cost,
            filed_date,
            issued_date,
            completed_date,
            street_number,
            street_name
        FROM permits
        WHERE {where}
        ORDER BY filed_date DESC
        LIMIT {limit}
    """
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    else:
        return conn.execute(sql, params).fetchall()


def _query_routing_path(conn, permit_number: str) -> list[str]:
    """Get the list of stations visited for a permit from the addenda table."""
    ph = "%s" if BACKEND == "postgres" else "?"
    sql = f"""
        SELECT DISTINCT station
        FROM addenda
        WHERE application_number = {ph}
            AND station IS NOT NULL
            AND station != ''
        ORDER BY station
    """
    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, [permit_number])
                rows = cur.fetchall()
        else:
            rows = conn.execute(sql, [permit_number]).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.debug("Routing path query failed for %s: %s", permit_number, e)
        return []


def _compute_days(date1_str: str | None, date2_str: str | None) -> int | None:
    """Compute days between two date strings. Returns None if either is missing."""
    if not date1_str or not date2_str:
        return None
    try:
        d1 = _date.fromisoformat(str(date1_str)[:10])
        d2 = _date.fromisoformat(str(date2_str)[:10])
        diff = (d2 - d1).days
        return diff if diff >= 0 else None
    except (ValueError, TypeError):
        return None


def _build_project_dict(row: tuple, routing_path: list[str]) -> dict:
    """Convert a DB row tuple into a project dict."""
    (
        permit_number, permit_type_def, neighborhood, supervisor_district,
        estimated_cost, revised_cost, filed_date, issued_date, completed_date,
        street_number, street_name,
    ) = row

    # Compute duration fields
    days_to_issuance = _compute_days(filed_date, issued_date)
    days_to_completion = _compute_days(issued_date, completed_date)

    # Cost change percentage
    cost_change_pct = None
    if revised_cost and estimated_cost and estimated_cost > 0:
        cost_change_pct = round((revised_cost - estimated_cost) / estimated_cost * 100, 1)

    # Build address string
    parts = [p for p in [street_number, street_name] if p]
    address = " ".join(parts) if parts else None

    return {
        "permit_number": permit_number,
        "permit_type_definition": permit_type_def,
        "neighborhood": neighborhood,
        "supervisor_district": supervisor_district,
        "estimated_cost": estimated_cost,
        "revised_cost": revised_cost,
        "filed_date": str(filed_date) if filed_date else None,
        "issued_date": str(issued_date) if issued_date else None,
        "completed_date": str(completed_date) if completed_date else None,
        "days_to_issuance": days_to_issuance,
        "days_to_completion": days_to_completion,
        "cost_change_pct": cost_change_pct,
        "address": address,
        "routing_path": routing_path,
    }


def _format_markdown(matches: list[dict], permit_type: str, neighborhood: str | None,
                     estimated_cost: float | None, widened_to: str | None,
                     total_searched: int) -> str:
    """Format similar projects as markdown."""
    lines = ["# Similar Completed Projects\n"]
    lines.append(f"**Permit Type:** {permit_type}")
    if neighborhood:
        lines.append(f"**Neighborhood:** {neighborhood}")
    if estimated_cost:
        lines.append(f"**Estimated Cost:** ${estimated_cost:,.0f}")
    if widened_to:
        lines.append(f"*Note: Search widened to {widened_to} for sufficient results.*")
    lines.append("")

    if not matches:
        lines.append("No similar completed projects found for this combination.")
        lines.append("Try broadening your search criteria.")
        return "\n".join(lines)

    lines.append(f"Found **{len(matches)}** similar completed project(s):\n")

    for i, p in enumerate(matches, 1):
        lines.append(f"## {i}. {p['address'] or p['permit_number']}")
        lines.append(f"**Permit:** {p['permit_number']} · **Type:** {p['permit_type_definition']}")
        if p['neighborhood']:
            lines.append(f"**Neighborhood:** {p['neighborhood']}")
        if p['estimated_cost']:
            lines.append(f"**Cost:** ${p['estimated_cost']:,.0f}")
            if p['cost_change_pct'] is not None:
                direction = "increased" if p['cost_change_pct'] > 0 else "decreased"
                lines.append(f"**Cost Change:** {direction} {abs(p['cost_change_pct']):.1f}%")
        if p['days_to_issuance'] is not None:
            lines.append(f"**Days to Issuance:** {p['days_to_issuance']}")
        if p['days_to_completion'] is not None:
            lines.append(f"**Days to Completion:** {p['days_to_completion']}")
        if p['routing_path']:
            lines.append(f"**Route:** {' → '.join(p['routing_path'])}")
        lines.append("")

    return "\n".join(lines)


async def similar_projects(
    permit_type: str,
    neighborhood: str | None = None,
    estimated_cost: float | None = None,
    supervisor_district: str | None = None,
    limit: int = 5,
    return_structured: bool = False,
) -> "str | tuple[str, dict]":
    """Find completed permits similar to the user's project.

    Uses progressive widening to find completed permits matching:
    - permit type (ILIKE match against permit_type_definition)
    - neighborhood
    - cost bracket (within 50%, then 100%)
    - supervisor_district (fallback)

    Each result enriched with routing path from addenda table.
    Returns methodology dict per Sprint 58 contract.

    Args:
        permit_type: Permit type keyword (e.g., 'alterations', 'new construction')
        neighborhood: SF neighborhood name (optional)
        estimated_cost: Project estimated cost in dollars (optional)
        supervisor_district: SF supervisor district number (optional, used as fallback)
        limit: Number of results to return (default 5)
        return_structured: If True, returns (str, dict) tuple

    Returns:
        Formatted markdown string, or (str, dict) if return_structured=True.
    """
    matches: list[dict] = []
    total_searched = 0
    widened_to: str | None = None
    db_available = False

    try:
        conn = get_connection()
        try:
            db_available = True

            # Step 1: Exact — type + neighborhood + cost within 50%
            where, params = _build_where(
                permit_type=permit_type,
                neighborhood=neighborhood,
                estimated_cost=estimated_cost,
                cost_pct=0.5,
                supervisor_district=supervisor_district,
                use_district=False,
            )
            rows = _query_permits(conn, where, params, limit)
            total_searched += limit  # approximate

            if rows:
                for row in rows:
                    routing = _query_routing_path(conn, row[0])
                    matches.append(_build_project_dict(row, routing))

            # Step 2: Widen cost to 100% (if fewer than limit results)
            if len(matches) < limit and estimated_cost:
                widened_to = "100% cost bracket"
                where2, params2 = _build_where(
                    permit_type=permit_type,
                    neighborhood=neighborhood,
                    estimated_cost=estimated_cost,
                    cost_pct=1.0,
                    supervisor_district=supervisor_district,
                    use_district=False,
                )
                # Exclude already-found permit numbers
                found_nums = {m["permit_number"] for m in matches}
                rows2 = _query_permits(conn, where2, params2, limit * 3)
                total_searched += limit * 3
                for row in rows2:
                    if row[0] not in found_nums and len(matches) < limit:
                        routing = _query_routing_path(conn, row[0])
                        matches.append(_build_project_dict(row, routing))
                        found_nums.add(row[0])

            # Step 3: Widen to supervisor_district if still under limit
            if len(matches) < limit and (supervisor_district or neighborhood):
                widened_to = "supervisor district"
                found_nums = {m["permit_number"] for m in matches}
                # If we only have neighborhood, try without geo filter at all
                where3, params3 = _build_where(
                    permit_type=permit_type,
                    neighborhood=None,
                    estimated_cost=estimated_cost,
                    cost_pct=1.0,
                    supervisor_district=supervisor_district,
                    use_district=bool(supervisor_district),
                )
                rows3 = _query_permits(conn, where3, params3, limit * 5)
                total_searched += limit * 5
                for row in rows3:
                    if row[0] not in found_nums and len(matches) < limit:
                        routing = _query_routing_path(conn, row[0])
                        matches.append(_build_project_dict(row, routing))
                        found_nums.add(row[0])

        finally:
            conn.close()

    except Exception as e:
        logger.warning("similar_projects DB error: %s", e)
        db_available = False

    # Build methodology dict (Sprint 58 contract)
    today_iso = _date.today().isoformat()
    confidence = (
        "high" if len(matches) >= 3
        else "medium" if len(matches) > 0
        else "low"
    )

    formula_steps = [
        f"Step 1: permit_type_definition ILIKE '%{permit_type}%'"
        + (f" AND neighborhood = '{neighborhood}'" if neighborhood else "")
        + (f" AND estimated_cost WITHIN 50%" if estimated_cost else ""),
        "Step 2 (if < limit): widen cost bracket to 100%",
        "Step 3 (if still < limit): drop neighborhood, use supervisor_district or remove geo filter",
        "Each result enriched with routing path from addenda table",
    ]

    coverage_gaps = []
    if not db_available:
        coverage_gaps.append("Database unavailable — no historical permit data")
    if widened_to:
        coverage_gaps.append(f"Search widened to {widened_to} for sufficient results")
    if not matches:
        coverage_gaps.append("No matching completed permits found")

    methodology = {
        "tool": "similar_projects",
        "headline": f"{len(matches)} similar completed project{'s' if len(matches) != 1 else ''} found",
        "formula_steps": formula_steps,
        "data_sources": ["permits table (1.1M+ records)", "addenda routing (3.9M records)"],
        "sample_size": total_searched,
        "data_freshness": today_iso,
        "confidence": confidence,
        "coverage_gaps": coverage_gaps,
        "projects": matches,
        "methodology": {
            "model": "similar-project-matching",
            "formula": "Progressive widening: type + neighborhood + cost bracket",
            "data_source": "permits + addenda tables",
            "recency": "Completed permits only (completed_date IS NOT NULL)",
            "data_freshness": today_iso,
            "confidence": confidence,
            "coverage_gaps": coverage_gaps,
        },
    }

    md = _format_markdown(
        matches=matches,
        permit_type=permit_type,
        neighborhood=neighborhood,
        estimated_cost=estimated_cost,
        widened_to=widened_to,
        total_searched=total_searched,
    )

    if return_structured:
        return md, methodology

    return md
