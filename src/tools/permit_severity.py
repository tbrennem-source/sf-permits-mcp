"""Tool: permit_severity — Score a permit's severity on a data-driven 0-100 scale."""

import logging

from src.db import get_connection, BACKEND
from src.severity import PermitInput, score_permit

logger = logging.getLogger(__name__)

# Placeholder style: %s for Postgres, ? for DuckDB
_PH = "%s" if BACKEND == "postgres" else "?"

# Dimension display labels
_DIMENSION_LABELS = {
    "inspection_activity": "Inspection Activity",
    "age_staleness": "Age / Staleness",
    "expiration_proximity": "Expiration Proximity",
    "cost_tier": "Cost Tier",
    "category_risk": "Category Risk",
}


def _exec(conn, sql, params=None):
    """Execute SQL and return all rows."""
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


def _exec_one(conn, sql, params=None):
    """Execute SQL and return first row, or None."""
    rows = _exec(conn, sql, params)
    return rows[0] if rows else None


# Column order matches `SELECT * FROM permits`
_PERMIT_COLS = [
    "permit_number", "permit_type", "permit_type_definition", "status",
    "status_date", "description", "filed_date", "issued_date", "approved_date",
    "completed_date", "estimated_cost", "revised_cost", "existing_use",
    "proposed_use", "existing_units", "proposed_units", "street_number",
    "street_name", "street_suffix", "zipcode", "neighborhood",
    "supervisor_district", "block", "lot", "adu", "data_as_of",
]


def _row_to_dict(row) -> dict:
    """Convert a tuple row to a dict."""
    return {_PERMIT_COLS[i]: row[i] for i in range(min(len(_PERMIT_COLS), len(row)))}


def _find_permit(conn, permit_number=None, street_number=None,
                 street_name=None, block=None, lot=None) -> dict | None:
    """Find a single permit by the first available identifier."""
    if permit_number:
        sql = f"SELECT * FROM permits WHERE permit_number = {_PH} LIMIT 1"
        row = _exec_one(conn, sql, [permit_number.strip()])
        if row:
            return _row_to_dict(row)
        return None

    if street_number and street_name:
        sql = f"""
            SELECT * FROM permits
            WHERE street_number = {_PH}
              AND UPPER(street_name) = UPPER({_PH})
            ORDER BY filed_date DESC
            LIMIT 1
        """
        row = _exec_one(conn, sql, [street_number.strip(), street_name.strip()])
        if row:
            return _row_to_dict(row)
        return None

    if block and lot:
        sql = f"""
            SELECT * FROM permits
            WHERE block = {_PH} AND lot = {_PH}
            ORDER BY filed_date DESC
            LIMIT 1
        """
        row = _exec_one(conn, sql, [block.strip(), lot.strip()])
        if row:
            return _row_to_dict(row)

    return None


def _get_inspection_count(conn, permit_number: str) -> int:
    """Count inspections for a permit."""
    sql = f"SELECT COUNT(*) FROM inspections WHERE reference_number = {_PH}"
    row = _exec_one(conn, sql, [permit_number])
    return int(row[0]) if row else 0


def _format_result(result, permit_dict: dict, inspection_count: int) -> str:
    """Format SeverityResult as markdown."""
    pn = permit_dict.get("permit_number", "Unknown")
    lines = [f"# Permit Severity Score: {pn}\n"]

    # Score + Tier header
    lines.append(f"**Score:** {result.score}/100 — **{result.tier}**")
    lines.append(f"**Category:** {result.category}")
    lines.append(f"**Explanation:** {result.explanation}")

    # Dimension breakdown table
    lines.append("\n## Dimension Breakdown\n")
    lines.append("| Dimension | Score | Weight | Contribution |")
    lines.append("|-----------|-------|--------|-------------|")
    for name, dim in result.dimensions.items():
        label = _DIMENSION_LABELS.get(name, name)
        score = dim["score"]
        weight = dim["weight"]
        contribution = round(score * weight, 1)
        marker = " **<<**" if name == result.top_driver else ""
        lines.append(f"| {label} | {score:.0f}/100 | {weight:.0%} | {contribution:.1f}{marker} |")

    # Recommendations based on tier
    lines.append("\n## Recommendations\n")
    if result.tier == "CRITICAL":
        lines.append("- **Immediate action required** — verify permit status with DBI")
        lines.append("- Check for expired permit renewal options (extension application)")
        lines.append("- Verify construction activity matches permit scope")
        lines.append("- Consider contacting assigned inspector")
    elif result.tier == "HIGH":
        lines.append("- Schedule follow-up within 2 weeks")
        lines.append("- Verify inspection schedule is current")
        lines.append("- Check for pending plan review corrections")
    elif result.tier == "MEDIUM":
        lines.append("- Monitor at next monthly review")
        lines.append("- Ensure inspection milestones are being met")
    elif result.tier == "LOW":
        lines.append("- No urgent action — include in quarterly review")
    else:
        lines.append("- Permit is on track — no action needed")

    # Permit context
    lines.append("\n## Permit Context\n")
    lines.append(f"**Status:** {permit_dict.get('status', 'Unknown')}")
    if permit_dict.get("description"):
        desc = permit_dict["description"][:200]
        lines.append(f"**Description:** {desc}")
    if permit_dict.get("filed_date"):
        lines.append(f"**Filed:** {permit_dict['filed_date']}")
    if permit_dict.get("issued_date"):
        lines.append(f"**Issued:** {permit_dict['issued_date']}")
    cost = permit_dict.get("revised_cost") or permit_dict.get("estimated_cost")
    if cost:
        lines.append(f"**Cost:** ${float(cost):,.0f}")
    lines.append(f"**Inspections:** {inspection_count}")

    # Confidence + source
    lines.append(f"\n**Confidence:** {result.confidence}")
    lines.append(f"\n---\n*Source: sfpermits.ai severity model v1 ({BACKEND})*")

    return "\n".join(lines)


async def permit_severity(
    permit_number: str | None = None,
    street_number: str | None = None,
    street_name: str | None = None,
    block: str | None = None,
    lot: str | None = None,
) -> str:
    """Score a permit's severity on a data-driven 0-100 scale.

    Analyzes 5 dimensions to produce a severity score and tier (CRITICAL/HIGH/MEDIUM/LOW/GREEN):
    - Inspection Activity: has inspections vs. expected for category
    - Age/Staleness: days filed + days since last activity
    - Expiration Proximity: Table B countdown
    - Cost Tier: higher cost = higher impact if abandoned
    - Category Risk: life-safety categories score higher

    Provide ONE of:
    - permit_number: exact permit number (e.g., '202301015555')
    - street_number + street_name: address (e.g., '123' + 'Main')
    - block + lot: parcel identifier (e.g., '3512' + '001')

    Returns severity score, tier, dimension breakdown, and recommendations.
    """
    has_permit = bool(permit_number and permit_number.strip())
    has_address = bool(street_number and street_number.strip()
                       and street_name and street_name.strip())
    has_parcel = bool(block and block.strip() and lot and lot.strip())

    if not has_permit and not has_address and not has_parcel:
        return ("Please provide a permit number, address (street number + street name), "
                "or parcel (block + lot).")

    try:
        conn = get_connection()
    except Exception as e:
        logger.warning("DB connection failed in permit_severity: %s", e)
        return "Database unavailable — cannot score permit severity."

    try:
        permit_dict = _find_permit(
            conn,
            permit_number=permit_number if has_permit else None,
            street_number=street_number if has_address else None,
            street_name=street_name if has_address else None,
            block=block if has_parcel else None,
            lot=lot if has_parcel else None,
        )

        if not permit_dict:
            search = ""
            if has_permit:
                search = f"permit number **{permit_number.strip()}**"
            elif has_address:
                search = f"**{street_number.strip()} {street_name.strip()}**"
            else:
                search = f"**Block {block.strip()}, Lot {lot.strip()}**"
            return f"No permit found matching {search}."

        pn = permit_dict["permit_number"]
        inspection_count = _get_inspection_count(conn, pn)
        permit_input = PermitInput.from_dict(permit_dict, inspection_count=inspection_count)
        result = score_permit(permit_input)

        return _format_result(result, permit_dict, inspection_count)

    finally:
        conn.close()
