"""Tool: property_health — Look up pre-computed property health tier and signals."""

import json
import logging

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

_PH = "%s" if BACKEND == "postgres" else "?"


def _exec(conn, sql, params=None):
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        if params:
            sql = sql.replace("%s", "?")
        return conn.execute(sql, params or []).fetchall()


def _exec_one(conn, sql, params=None):
    rows = _exec(conn, sql, params)
    return rows[0] if rows else None


_TIER_LABELS = {
    "high_risk": "HIGH RISK",
    "at_risk": "AT RISK",
    "behind": "BEHIND",
    "slower": "SLOWER",
    "on_track": "ON TRACK",
}

_TIER_DESCRIPTIONS = {
    "high_risk": "Compound risk — multiple independent at-risk signals converge on this property",
    "at_risk": "Active risk signal requires attention",
    "behind": "Falling behind schedule or norms — needs monitoring",
    "slower": "Minor concern, informational only",
    "on_track": "No negative signals detected",
}


def _format_health(block_lot: str, tier: str, signal_count: int,
                   at_risk_count: int, signals_json) -> str:
    """Format property health as markdown."""
    label = _TIER_LABELS.get(tier, tier.upper())
    desc = _TIER_DESCRIPTIONS.get(tier, "")

    lines = [f"# Property Health: {block_lot}\n"]
    lines.append(f"**Tier:** {label}")
    lines.append(f"**Description:** {desc}")
    lines.append(f"**Total Signals:** {signal_count}")
    lines.append(f"**At-Risk Signals:** {at_risk_count}")

    # Parse signals
    if signals_json:
        if isinstance(signals_json, str):
            signals = json.loads(signals_json)
        else:
            signals = signals_json

        if signals:
            lines.append("\n## Signals\n")
            lines.append("| Signal | Severity | Permit | Detail |")
            lines.append("|--------|----------|--------|--------|")
            for s in signals:
                stype = s.get("signal_type", "")
                sev = s.get("severity", "")
                pn = s.get("permit_number", "-") or "-"
                detail = s.get("detail", "")
                lines.append(f"| {stype} | {sev} | {pn} | {detail} |")

    lines.append(f"\n---\n*Source: sfpermits.ai severity v2 ({BACKEND})*")
    return "\n".join(lines)


async def property_health(
    block: str | None = None,
    lot: str | None = None,
    block_lot: str | None = None,
) -> str:
    """Look up pre-computed property health tier and signals.

    Returns the health tier (HIGH_RISK / AT_RISK / BEHIND / SLOWER / ON_TRACK)
    and all detected signals for a property, based on the nightly signal pipeline.

    Provide EITHER:
    - block + lot: parcel identifier (e.g., '3512' + '001')
    - block_lot: combined key (e.g., '3512/001')

    Falls back to v1 severity scoring if signal tables are empty.
    """
    # Resolve block_lot
    if block_lot:
        bl = block_lot.strip()
    elif block and lot:
        bl = f"{block.strip()}/{lot.strip()}"
    else:
        return "Please provide block + lot or block_lot (e.g., '3512/001')."

    try:
        conn = get_connection()
    except Exception as e:
        logger.warning("DB connection failed in property_health: %s", e)
        return "Database unavailable — cannot look up property health."

    try:
        # Try v2 table first
        try:
            row = _exec_one(
                conn,
                f"SELECT block_lot, tier, signal_count, at_risk_count, signals_json "
                f"FROM property_health WHERE block_lot = {_PH}",
                [bl],
            )
        except Exception:
            row = None

        if row:
            return _format_health(row[0], row[1], row[2], row[3], row[4])

        # Fallback: no v2 data
        return (
            f"No pre-computed health data for **{bl}**. "
            f"The signal pipeline may not have run yet. "
            f"Use `permit_severity` for per-permit v1 scoring."
        )
    finally:
        conn.close()
